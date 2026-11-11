"""Build the analysis datasets for Charleston County in data/processed/:
structures.parquet  every NSI structure with its effective FEMA flood zone and BFE (own overlay of the NFHL), jurisdiction, census tract, SVI and 1886 ShakeMap PGA
county.gpkg          county outline, jurisdictions, tracts with NRI and SVI, flood zones (dissolved by class), water, roads
"""
import json
import sys
import xml.etree.ElementTree as ET
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:32617"  # UTM 17N, metres


def zone_class(z, sub):
    z = z.upper() if isinstance(z, str) else ""
    sub = sub.upper() if isinstance(sub, str) else ""
    if z.startswith("V"):
        return "VE"
    if z in ("A", "AE", "AH", "AO", "A99", "AR") or z.startswith("A"):
        return "A"
    if z == "X" and "0.2 PCT" in sub:
        return "X500"
    if z == "D":
        return "D"
    if z == "OPEN WATER":
        return "WATER"
    return "X"


def main():
    # county and jurisdictions
    cty = gpd.read_file(f"zip://{RAW/'counties_us.zip'}")
    cty = cty[cty.GEOID == "45019"].to_crs(CRS)
    places = gpd.read_file(f"zip://{RAW/'places_sc.zip'}").to_crs(CRS)
    places = places[places.CLASSFP.str.startswith("C")]  # incorporated places only
    inter = gpd.overlay(places[["NAME", "GEOID", "geometry"]], cty[["geometry"]], how="intersection")
    inter = inter[inter.area > 2e5]
    tr = gpd.read_file(f"zip://{RAW/'tracts_sc.zip'}")
    tr = tr[tr.COUNTYFP == "019"].to_crs(CRS)
    # NRI and SVI attributes
    nri = gpd.read_file(RAW / "nri_tracts_45019.geojson").drop(columns="geometry")
    tr = tr.merge(nri, left_on="GEOID", right_on="TRACTFIPS", how="left")
    svi = pd.read_csv(RAW / "svi_sc_2022.csv", dtype={"FIPS": str})
    svi = svi[svi.STCNTY.astype(str) == "45019"][["FIPS", "RPL_THEMES", "RPL_THEME1", "RPL_THEME2", "RPL_THEME3", "RPL_THEME4", "E_TOTPOP"]]
    tr = tr.merge(svi, left_on="GEOID", right_on="FIPS", how="left")
    for c in ("RPL_THEMES", "RPL_THEME1", "RPL_THEME2", "RPL_THEME3", "RPL_THEME4"):
        tr[c] = tr[c].where(tr[c] >= 0)
    # flood zones
    fz = gpd.read_file(RAW / "nfhl_zones_45019.geojson").to_crs(CRS)
    fz["zclass"] = [zone_class(a, b) for a, b in zip(fz.FLD_ZONE, fz.ZONE_SUBTY)]
    fz["bfe"] = fz.STATIC_BFE.where(fz.STATIC_BFE > -9000)
    fz = gpd.clip(fz, cty.geometry.iloc[0])
    # structures
    nsi = json.loads((RAW / "nsi_45019.geojson").read_text())
    df = pd.DataFrame([f["properties"] for f in nsi["features"]])
    st = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.x, df.y), crs=4326).to_crs(CRS)
    st = st.rename(columns={"firmzone": "nsi_firmzone", "static_bfe": "nsi_bfe"})
    j = gpd.sjoin(st[["fd_id", "geometry"]], fz[["zclass", "FLD_ZONE", "bfe", "geometry"]], how="left", predicate="within")
    # a point on a shared edge can match two polygons: keep the most hazardous class and the highest BFE
    order = {"VE": 0, "A": 1, "X500": 2, "D": 3, "X": 4, "WATER": 5}
    j["rank"] = j.zclass.map(order).fillna(9)
    j = j.sort_values(["fd_id", "rank", "bfe"], ascending=[True, True, False]).drop_duplicates("fd_id")
    st = st.merge(j[["fd_id", "zclass", "FLD_ZONE", "bfe"]], on="fd_id", how="left")
    st["zclass"] = st.zclass.fillna("X")
    jp = gpd.sjoin(st[["fd_id", "geometry"]], inter[["NAME", "geometry"]], how="left", predicate="within").drop_duplicates("fd_id")
    st = st.merge(jp[["fd_id", "NAME"]].rename(columns={"NAME": "jurisdiction"}), on="fd_id", how="left")
    st["jurisdiction"] = st.jurisdiction.fillna("Unincorporated Charleston County")
    jt = gpd.sjoin(st[["fd_id", "geometry"]], tr[["GEOID", "RPL_THEMES", "geometry"]], how="left", predicate="within").drop_duplicates("fd_id")
    st = st.merge(jt[["fd_id", "GEOID", "RPL_THEMES"]].rename(columns={"GEOID": "tract", "RPL_THEMES": "svi"}), on="fd_id", how="left")
    # attributes for the loss models
    st["occ_base"] = st.occtype.str.split("-").str[0]
    st["stories"] = st.num_story.clip(1, 60).astype(int)
    st["basement"] = st.occtype.str.contains("WB", na=False) | (st.found_type == "B")
    st["vzone"] = st.zclass == "VE"
    st["ffe_ft"] = st.ground_elv + st.found_ht
    st["depth_1pct_ft"] = st.bfe - st.ffe_ft
    st["pop_night"] = st.pop2amu65 + st.pop2amo65
    st["pop_day"] = st.pop2pmu65 + st.pop2pmo65
    st["value_total"] = st.val_struct + st.val_cont
    # ShakeMap 1886 (grid.xml): nearest grid node
    root = ET.parse(RAW / "shakemap_1886_grid.xml").getroot()
    ns = {"s": root.tag.split("}")[0].strip("{")}
    fields = [f.get("name") for f in root.findall("s:grid_field", ns)]
    g = np.loadtxt(root.find("s:grid_data", ns).text.strip().splitlines())
    G = pd.DataFrame(g, columns=fields)
    from scipy.spatial import cKDTree
    ll = st.to_crs(4326)
    k = cKDTree(G[["LON", "LAT"]].to_numpy()).query(np.c_[ll.geometry.x, ll.geometry.y])[1]
    st["pga_g"] = G.PGA.to_numpy()[k] / 100.0  # percent g to g
    st["mmi"] = G.MMI.to_numpy()[k]
    st["psa03_g"] = G["PSA03"].to_numpy()[k] / 100.0 if "PSA03" in G else np.nan
    st["psa10_g"] = G["PSA10"].to_numpy()[k] / 100.0 if "PSA10" in G else np.nan
    st.to_parquet(PROC / "structures.parquet")
    # layers for maps
    fzd = fz[fz.zclass.isin(["VE", "A", "X500"])].dissolve("zclass").reset_index()[["zclass", "geometry"]]
    water = gpd.read_file(f"zip://{RAW/'areawater_45019.zip'}").to_crs(CRS)
    roads = gpd.read_file(f"zip://{RAW/'roads_sc.zip'}").to_crs(CRS)
    roads = gpd.clip(roads[roads.MTFCC.isin(["S1100", "S1200"])], cty.geometry.iloc[0].buffer(3000))
    out = PROC / "county.gpkg"
    if out.exists():
        out.unlink()
    cty.to_file(out, layer="county")
    land = gpd.read_file(f"zip://{RAW/'counties_cb_500k.zip'}")
    land[land.GEOID == "45019"].to_crs(CRS).to_file(out, layer="land")
    inter.to_file(out, layer="jurisdictions")
    tr.to_file(out, layer="tracts")
    fzd.to_file(out, layer="flood_zones")
    water[water.AWATER > 0].to_file(out, layer="water")
    roads.to_file(out, layer="roads")
    sm = G[["LON", "LAT", "PGA", "MMI"]]
    sm.to_parquet(PROC / "shakemap_1886_grid.parquet")
    print("structures", len(st), "| zones", st.zclass.value_counts().to_dict())
    print("NSI zone vs NFHL overlay agreement (VE/A/other):", float((st.nsi_firmzone.fillna("").str[:1].replace({"": "X"}).map(lambda z: "V" if z == "V" else ("A" if z == "A" else "O")) == st.zclass.map(lambda z: "V" if z == "VE" else ("A" if z == "A" else "O"))).mean()))


if __name__ == "__main__":
    main()
