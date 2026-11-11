"""Download every public dataset the Charleston County risk assessment uses into data/raw/.

Sources (all public, no key):
  FEMA National Risk Index (tracts and counties), ArcGIS feature services published by FEMA
  FEMA National Flood Hazard Layer (flood hazard zones), hazards.fema.gov
  USACE National Structure Inventory (NSI), nsi.sec.usace.army.mil
  OpenFEMA: disaster declarations, NFIP redacted claims, Hazard Mitigation Assistance projects
  Census TIGER/Line 2023 tracts and counties; CDC/ATSDR Social Vulnerability Index 2022
  NOAA NCEI Storm Events database; USGS ComCat earthquakes and the 1886 Charleston ShakeMap
Usage: python scripts/fetch_data.py [all|nri|nfhl|openfema|census|storms|quakes]
"""
import gzip
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
STATE, COUNTY, FIPS = "45", "019", "45019"
BBOX = (-80.50, 32.48, -79.30, 33.22)  # Charleston County, lon/lat, generous
S = requests.Session()
S.headers["User-Agent"] = "risk-assessment-portfolio/1.0"


def get(url, **kw):
    for k in range(5):
        try:
            r = S.get(url, timeout=300, **kw)
            if r.status_code == 200:
                return r
            print("  HTTP", r.status_code, url[:120])
        except requests.RequestException as e:
            print("  retry", k, e)
        time.sleep(2 ** k)
    raise RuntimeError(url)


def arcgis_query(layer_url, where="1=1", geometry=None, out=None, page=1000):
    """Page through an ArcGIS REST layer as GeoJSON (WGS84)."""
    feats, off = [], 0
    while True:
        p = dict(where=where, outFields="*", f="geojson", outSR=4326, resultOffset=off, resultRecordCount=page, returnGeometry="true")
        if geometry:
            p.update(geometry=",".join(map(str, geometry)), geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects")
        r = get(layer_url + "/query", params=p).json()
        fs = r.get("features", [])
        feats += fs
        print(f"  {layer_url.split('/services/')[-1][:60]}: {len(feats)}", flush=True)
        if len(fs) < page and not r.get("exceededTransferLimit") and not r.get("properties", {}).get("exceededTransferLimit"):
            break
        off += len(fs)
        if not fs:
            break
    fc = dict(type="FeatureCollection", features=feats)
    if out:
        (RAW / out).write_text(json.dumps(fc))
    return fc


def nri():
    base = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services"
    arcgis_query(f"{base}/National_Risk_Index_Census_Tracts/FeatureServer/0", f"STCOFIPS='{FIPS}'", out="nri_tracts_45019.geojson", page=200)
    arcgis_query(f"{base}/National_Risk_Index_Counties/FeatureServer/0", f"STATEFIPS='{STATE}'", out="nri_counties_sc.geojson", page=100)
    t = get(f"{base}/National_Risk_Index_Hazard_Info_Table/FeatureServer/0/query", params=dict(where="1=1", outFields="*", f="json")).json()
    (RAW / "nri_hazard_info.json").write_text(json.dumps(t))


def nfhl():
    base = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
    arcgis_query(f"{base}/28", f"DFIRM_ID LIKE '{FIPS}%'", out="nfhl_zones_45019.geojson", page=100)
    arcgis_query(f"{base}/3", f"DFIRM_ID LIKE '{FIPS}%'", out="nfhl_panels_45019.geojson", page=100)


def nsi():
    p = RAW / "nsi_45019.geojson"
    if not p.exists():
        p.write_bytes(get(f"https://nsi.sec.usace.army.mil/nsiapi/structures?fips={FIPS}&fmt=fc").content)


def openfema():
    base = "https://www.fema.gov/api/open"

    def pull(path, flt, out, select=None):
        rows, skip = [], 0
        while True:
            p = {"$filter": flt, "$top": 10000, "$skip": skip, "$format": "json"}
            if select:
                p["$select"] = select
            r = get(f"{base}/{path}", params=p).json()
            key = [k for k in r if k != "metadata"][0]
            rows += r[key]
            print(f"  {path}: {len(rows)}", flush=True)
            if len(r[key]) < 10000:
                break
            skip += 10000
        (RAW / out).write_text(json.dumps(rows))

    pull("v2/DisasterDeclarationsSummaries", f"state eq 'SC' and fipsCountyCode eq '{COUNTY}'", "fema_declarations_45019.json")
    pull("v3/NfipClaims", f"countyCode eq '{FIPS}'", "nfip_claims_45019.json")
    pull("v1/NfipMultipleLossProperties", f"stateAbbreviation eq 'SC' and fipsCountyCode eq '{FIPS}'", "nfip_multiple_loss_45019.json")
    pull("v1/NfipCommunityStatusBook", "state eq 'SC'", "nfip_community_status_sc.json")
    pull("v1/HazardMitigationPlanStatuses", "stateAbbreviation eq 'SC'", "hm_plan_status_sc.json")
    pull("v2/HmaSubapplications", "subapplicantStateAbbreviation eq 'SC'", "hma_subapplications_sc.json")

def census():
    for name, url in (("tracts_sc.zip", "https://www2.census.gov/geo/tiger/TIGER2023/TRACT/tl_2023_45_tract.zip"),
                      ("counties_us.zip", "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"),
                      ("places_sc.zip", "https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_45_place.zip"),
                      ("areawater_45019.zip", "https://www2.census.gov/geo/tiger/TIGER2023/AREAWATER/tl_2023_45019_areawater.zip"),
                      ("roads_sc.zip", "https://www2.census.gov/geo/tiger/TIGER2023/PRISECROADS/tl_2023_45_prisecroads.zip"),
                      ("svi_sc_2022.csv", "https://svi.cdc.gov/Documents/Data/2022/csv/states/SouthCarolina.csv")):
        p = RAW / name
        if not p.exists():
            p.write_bytes(get(url).content)
            print(" ", name, p.stat().st_size)


def storms():
    base = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
    names = {}
    for name, y in re.findall(r'(StormEvents_details-ftp_v1\.0_d(\d{4})_c\d+\.csv\.gz)', get(base).text):
        names[y] = name  # the listing is sorted, so the last (newest) revision of each year wins
    import pandas as pd
    keep = []
    for y in sorted(names):
        if int(y) < 1996:
            continue
        df = pd.read_csv(io.BytesIO(get(base + names[y]).content), compression="gzip", low_memory=False)
        m = (df.STATE_FIPS == 45) & (((df.CZ_TYPE == "C") & (df.CZ_FIPS == 19)) | ((df.CZ_TYPE == "Z") & df.CZ_NAME.str.upper().str.contains("CHARLESTON", na=False)))
        keep.append(df[m])
        print("  storms", y, int(m.sum()), flush=True)
    pd.concat(keep).to_csv(RAW / "storm_events_45019.csv", index=False)


def quakes():
    r = get("https://earthquake.usgs.gov/fdsnws/event/1/query", params=dict(format="geojson", starttime="1690-01-01", latitude=32.9, longitude=-80.0, maxradiuskm=200, minmagnitude=2.0, orderby="time-asc"))
    (RAW / "usgs_quakes_200km.geojson").write_text(r.text)
    ev = get("https://earthquake.usgs.gov/fdsnws/event/1/query", params=dict(eventid="ushis251", format="geojson")).json()
    sm = ev["properties"]["products"]["shakemap"][0]["contents"]
    for k in ("download/grid.xml", "download/info.json", "download/cont_mmi.json", "download/cont_pga.json"):
        (RAW / ("shakemap_1886_" + k.split("/")[-1])).write_bytes(get(sm[k]["url"]).content)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("nri", nri), ("nfhl", nfhl), ("nsi", nsi), ("openfema", openfema), ("census", census), ("quakes", quakes), ("storms", storms)):
        if which in (name, "all"):
            print(name, flush=True)
            fn()
