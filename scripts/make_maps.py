"""Risk assessment maps and figures (outputs/maps/plate_XX_*.png) from the tables and processed data.
Usage: python scripts/make_maps.py [plate number|all]"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap, LinearSegmentedColormap

from riskx.plates import ACCENT, INK, MUTED, Plate, north, scalebar

RAW, PROC, TAB = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs" / "tables"
G = PROC / "county.gpkg"
KICK = "Charleston County, SC  ·  Hazard Mitigation Plan risk assessment"
SRC = ("Sources: FEMA National Risk Index (Dec 2025); FEMA National Flood Hazard Layer; USACE National Structure Inventory; OpenFEMA (declarations, NFIP claims, multiple-loss properties, HMA); "
       "NOAA NCEI Storm Events; USGS ComCat and ShakeMap (1886 Charleston earthquake); CDC/ATSDR SVI 2022; Census TIGER/Line 2023. Hazus damage functions: Hazus Flood v6.1 and Hazus Earthquake v6.1 via the NHERI SimCenter "
       "Damage and Loss Model Library. Coordinate system: UTM zone 17N. Prepared for planning; not for regulatory flood determinations.")
L = {}


def layers():
    if not L:
        for k in ("county", "land", "jurisdictions", "tracts", "flood_zones", "water", "roads"):
            L[k] = gpd.read_file(G, layer=k)
        L["st"] = pd.read_parquet(PROC / "structures_results.parquet")
        xy = gpd.GeoSeries(gpd.points_from_xy(L["st"].x, L["st"].y), crs=4326).to_crs(L["county"].crs)
        L["st"]["X"], L["st"]["Y"] = xy.x.values, xy.y.values
    return L


def T(name):
    return pd.read_csv(TAB / f"{name}.csv")


def basemap(ax, water=True, roads=True, juris=True, land="#F4F2EE"):
    lay = layers()
    lay["land"].plot(ax=ax, color=land, edgecolor="none", zorder=0)
    if water:
        lay["water"].plot(ax=ax, color="#C9DCE8", edgecolor="none", zorder=1)
    if roads:
        lay["roads"].plot(ax=ax, color="#A7ADB5", lw=0.45, zorder=6)
    if juris:
        lay["jurisdictions"].boundary.plot(ax=ax, color="#4B535C", lw=0.45, zorder=7)
    lay["land"].boundary.plot(ax=ax, color=INK, lw=0.8, zorder=8)
    x0, y0, x1, y1 = lay["land"].total_bounds
    ax.set_xlim(x0 - 2000, x1 + 2000); ax.set_ylim(y0 - 2000, y1 + 2000)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.set_xlabel(""); ax.set_ylabel("")
    ax.set_facecolor("#DCE7EF")
    for s in ax.spines.values():
        s.set_color("#9AA1AA")


def map_axes(p):
    return p.ax(0.6, 0.9, 9.5, p.top - 1.15)


def finish(ax):
    scalebar(ax, 10); north(ax)


def label_places(ax, names=("Charleston", "North Charleston", "Mount Pleasant", "Isle of Palms", "Folly Beach", "Kiawah Island", "McClellanville", "Hollywood", "Awendaw", "James Island")):
    j = layers()["jurisdictions"]
    for _, r in j[j.NAME.isin(names)].iterrows():
        c = r.geometry.representative_point()
        ax.text(c.x, c.y, r.NAME, fontsize=6.6, color=INK, ha="center", va="center", zorder=12,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))


def bn(v):
    return f"${v / 1e9:,.1f} B" if v >= 1e9 else f"${v / 1e6:,.0f} M"


SX, SW = 10.45, 4.95


# ------------------------------------------------------------------------- plates
def p01():
    lay = layers()
    st = lay["st"]
    nri = T("01_nri_hazard_ranking")
    p = Plate(1, KICK, "Planning area: Charleston County and its jurisdictions", "Seventeen incorporated municipalities (wholly or partly in the county) and the unincorporated county, every structure in the National Structure Inventory, and the major roads", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "Jurisdictions and building stock", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax)
    j = lay["jurisdictions"]
    cols = plt.get_cmap("tab20")(np.linspace(0, 1, len(j)))
    j.plot(ax=ax, color=cols, alpha=0.28, edgecolor="none", zorder=2)
    ax.scatter(st.X, st.Y, s=0.05, c="#4B535C", alpha=0.35, linewidths=0, zorder=3)
    label_places(ax)
    finish(ax)
    c = gpd.read_file(RAW / "nri_counties_sc.geojson")
    r = c[c.STCOFIPS == "45019"].iloc[0]
    p.panel_title(SX, p.top - 0.3, "B", "Planning area at a glance", w=SW)
    y = p.tiles(SX, p.top - 0.65, SW, [(f"{int(r.POPULATION):,}", "residents (NRI, 2020 Census basis)"), (f"{len(st):,}", "structures in the NSI"), (bn(st.val_struct.sum()), "structure replacement value")])
    jt = st.groupby("jurisdiction").agg(n=("fd_id", "count"), v=("value_total", "sum")).sort_values("n", ascending=False)
    p.panel_title(SX, y - 0.15, "C", "Structures by jurisdiction", w=SW)
    b = p.ax(SX + 1.9, y - 0.4 - 0.19 * len(jt), SW - 2.0, 0.19 * len(jt))
    b.barh(range(len(jt))[::-1], jt.n, color=ACCENT)
    b.set_yticks(range(len(jt))[::-1]); b.set_yticklabels(jt.index, fontsize=7)
    for i, v in zip(range(len(jt))[::-1], jt.n):
        b.text(v, i, f" {v:,}", va="center", fontsize=6.5, color=MUTED)
    b.set_xlim(0, jt.n.max() * 1.25); b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.notes(SX, y - 0.6 - 0.19 * len(jt), SW, [("Current plan", "The Charleston County multi-jurisdictional hazard mitigation plan was approved 2024-03-20 and expires 2029-03-19 (OpenFEMA plan status). This analysis is built to support the next update's risk assessment.")])
    p.save("plate_01_planning_area.png")


def p02():
    lay = layers()
    tr = lay["tracts"].copy()
    nri = T("01_nri_hazard_ranking").head(10)
    p = Plate(2, KICK, "Overall risk: FEMA National Risk Index by census tract", "Composite risk combines expected annual loss from 18 natural hazards with social vulnerability and community resilience; the county ranks first of 46 in South Carolina", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "National Risk Index rating by census tract", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax, juris=False, roads=False)
    order = ["Very Low", "Relatively Low", "Relatively Moderate", "Relatively High", "Very High"]
    pal = ["#2C7BB6", "#ABD9E9", "#FFFFBF", "#FDAE61", "#D7191C"]
    tr["rk"] = tr.RISK_RATNG.map({k: i for i, k in enumerate(order)})
    for i, k in enumerate(order):
        tr[tr.rk == i].plot(ax=ax, color=pal[i], edgecolor="white", lw=0.3, zorder=2)
    tr[tr.rk.isna()].plot(ax=ax, color="#E3E3E3", edgecolor="white", lw=0.3, zorder=2)
    lay["water"].plot(ax=ax, color="#C9DCE8", edgecolor="none", zorder=3)
    lay["jurisdictions"].boundary.plot(ax=ax, color="#4B535C", lw=0.4, zorder=7)
    label_places(ax)
    finish(ax)
    y = p.legend(SX, p.top - 0.35, SW, [("patch", c, k) for c, k in zip(pal, order)] + [("patch", "#E3E3E3", "No rating")], title="Risk index rating (national percentiles)")
    sc = T("02_nri_sc_county_ranking")
    ch = sc[sc.STCOFIPS == 45019].iloc[0] if sc.STCOFIPS.dtype != object else sc[sc.STCOFIPS == "45019"].iloc[0]
    y = p.tiles(SX, y - 0.1, SW, [(f"{ch.RISK_SCORE:.1f}", f"county risk score ({ch.RISK_RATNG})"), (f"#{int(ch.rank_in_sc)}", "of 46 SC counties"), (bn(ch.EAL_VALT), "expected annual loss, all hazards")])
    p.panel_title(SX, y - 0.1, "B", "Expected annual loss by hazard (top 10)", w=SW)
    b = p.ax(SX + 1.45, y - 0.45 - 2.5, SW - 1.6, 2.5)
    b.barh(range(len(nri))[::-1], nri.expected_annual_loss / 1e6, color=ACCENT)
    b.set_yticks(range(len(nri))[::-1]); b.set_yticklabels(nri.hazard, fontsize=7.4)
    for i, v in zip(range(len(nri))[::-1], nri.expected_annual_loss / 1e6):
        b.text(v, i, f" ${v:,.1f} M", va="center", fontsize=6.6, color=MUTED)
    b.set_xlim(0, nri.expected_annual_loss.max() / 1e6 * 1.3); b.set_xlabel("$ million per year", fontsize=7, color=MUTED); b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    top = nri.iloc[0]
    p.notes(SX, y - 3.35, SW, [("Reading it", f"{top.hazard} dominates with {top.share_of_eal * 100:.0f}% of the county's expected annual loss, then {nri.iloc[1].hazard.lower()} and {nri.iloc[2].hazard.lower()}. Tract ratings are national percentiles, so most of the county rates high against the nation.")])
    p.save("plate_02_nri_composite_risk.png")


def p03():
    lay = layers()
    tr = lay["tracts"]
    p = Plate(3, KICK, "Expected annual loss by hazard and census tract", "National Risk Index expected annual loss (buildings, population equivalence and agriculture), dollars per year, for the six hazards with the largest county totals", SRC)
    nri = T("01_nri_hazard_ranking").head(6)
    pref = {v: k for k, v in __import__("run_analysis").NRI_HAZ.items()} if False else {"Hurricane": "HRCN", "Coastal flooding": "CFLD", "Riverine flooding": "RFLD", "Earthquake": "ERQK", "Tornado": "TRND",
                                                                                         "Heat wave": "HWAV", "Strong wind": "SWND", "Hail": "HAIL", "Lightning": "LTNG", "Wildfire": "WFIR", "Drought": "DRGT",
                                                                                         "Winter weather": "WNTW", "Ice storm": "ISTM", "Cold wave": "CWAV", "Tsunami": "TSUN", "Landslide": "LNDS"}
    gap_x, w = 0.25, (14.8 - 2 * 0.25) / 3
    row_h = (p.top - 0.95 - 0.25) / 2          # each row: title 0.3, map, colorbar 0.55
    for i, (_, r) in enumerate(nri.iterrows()):
        cx = 0.6 + (i % 3) * (w + gap_x)
        top = p.top - 0.25 - (i // 3) * row_h
        p.bg.text(cx, top - 0.05, r.hazard, fontsize=10, color=INK, fontweight="bold", va="top")
        p.bg.text(cx + w, top - 0.07, f"county {bn(r.expected_annual_loss)} per year", fontsize=8.2, color=MUTED, va="top", ha="right")
        map_h = row_h - 0.3 - 0.75
        ax = p.ax(cx, top - 0.32 - map_h, w, map_h)
        basemap(ax, juris=False, roads=False)
        col = f"{pref.get(r.hazard, 'HRCN')}_EALT"
        v = tr[col].clip(lower=0)
        vmax = float(np.nanpercentile(v, 98)) or 1.0
        cmap = LinearSegmentedColormap.from_list("e", ["#FFF4E0", "#FDB863", "#E66101", "#7F2704"])
        tr.assign(v=v).plot(ax=ax, column="v", cmap=cmap, vmin=0, vmax=vmax, edgecolor="white", lw=0.2, zorder=2)
        lay["water"].plot(ax=ax, color="#C9DCE8", edgecolor="none", zorder=3)
        lay["land"].boundary.plot(ax=ax, color=INK, lw=0.6, zorder=8)
        nice = [0, vmax / 2e3, vmax / 1e3]
        p.colorbar(cx + 0.6, top - 0.32 - map_h - 0.27, w - 1.2, cmap, 0, vmax / 1e3, "$ thousand per tract per year", ticks=[round(t, -1 if t > 50 else 0) for t in nice])
    p.save("plate_03_nri_eal_by_hazard.png")


def p04():
    d = T("03_disaster_declarations")
    s = T("04_storm_events_summary")
    cy = T("05_nfip_claims_by_year")
    ev = T("07_nfip_top_flood_events")
    p = Plate(4, KICK, "Hazard history: declarations, storm events and flood insurance claims", "What has already happened in the county: every federal disaster declaration, 30 years of NOAA storm reports and every NFIP claim", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", f"FEMA disaster declarations ({len(d)})", w=7.2)
    a = p.ax(1.75, p.top - 3.35, 5.95, 2.75)
    d["year"] = pd.to_datetime(d.declarationDate).dt.year
    cats = d.incidentType.value_counts().index.tolist()
    cmap = plt.get_cmap("tab10")
    for i, c in enumerate(cats):
        m = d.incidentType == c
        a.scatter(d.year[m], np.full(m.sum(), i), s=46, color=cmap(i), edgecolors="white", lw=0.5, zorder=3)
    a.set_yticks(range(len(cats))); a.set_yticklabels(cats, fontsize=7.5); a.tick_params(labelsize=7.5, colors=MUTED); a.spines[["top", "right"]].set_visible(False); a.grid(axis="x", color="#EEE")
    a.set_ylim(-0.6, len(cats) - 0.4)
    p.panel_title(8.2, p.top - 0.3, "B", "NOAA Storm Events: property damage by event type", w=7.2)
    b = p.ax(10.25, p.top - 3.35, 4.65, 2.75)
    s2 = s[s.property_damage > 0].head(10)
    b.barh(range(len(s2))[::-1], s2.property_damage / 1e6, color=ACCENT)
    for i_, v_ in zip(range(len(s2))[::-1], s2.property_damage / 1e6):
        b.text(v_, i_, f" ${v_:,.1f} M", va="center", fontsize=6.8, color=MUTED)
    b.set_xlim(0, s2.property_damage.max() / 1e6 * 1.25)
    b.set_yticks(range(len(s2))[::-1]); b.set_yticklabels([f"{t} ({n})" for t, n in zip(s2.EVENT_TYPE, s2.events)], fontsize=7.2)
    b.set_xlabel("$ million reported (nominal); events in brackets", fontsize=7, color=MUTED); b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.panel_title(0.6, p.top - 3.85, "C", "NFIP claims paid by year of loss", w=7.2)
    c = p.ax(1.25, 1.15, 6.45, p.top - 5.2)
    c.bar(cy.yearOfLoss, cy.paid / 1e6, color=ACCENT, width=0.8)
    big = cy.set_index("yearOfLoss").paid / 1e6
    c.annotate("1989  Hurricane Hugo", (1989, big.get(1989, 0)), xytext=(1992, big.max() * 0.92), fontsize=7.5, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    c.annotate("2015 to 2017  October 2015 flood,\nMatthew and Irma", (2016, big.get(2016, 0) + 3), xytext=(1996, big.max() * 0.45), fontsize=7.5, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    c.set_ylabel("$ million paid (nominal)", fontsize=7.5, color=MUTED); c.tick_params(labelsize=7.5, colors=MUTED); c.spines[["top", "right"]].set_visible(False)
    p.panel_title(8.2, p.top - 3.85, "D", "Largest NFIP flood events", w=7.2)
    y = p.top - 4.3
    p.bg.text(8.2, y, "Event", fontsize=7.6, color=MUTED, fontweight="bold"); p.bg.text(13.4, y, "Claims", fontsize=7.6, color=MUTED, fontweight="bold", ha="right"); p.bg.text(15.4, y, "Paid", fontsize=7.6, color=MUTED, fontweight="bold", ha="right")
    for _, r in ev.head(9).iterrows():
        y -= 0.24
        p.bg.text(8.2, y, str(r.floodEvent)[:48], fontsize=7.6, color=INK); p.bg.text(13.4, y, f"{int(r.claims):,}", fontsize=7.6, ha="right"); p.bg.text(15.4, y, bn(r.paid), fontsize=7.6, ha="right")
    nc = T("05_nfip_claims_by_year")
    p.notes(8.2, y - 0.35, 7.2, [("Totals", f"{int(nc.claims.sum()):,} NFIP claims and {bn(nc.paid.sum())} paid since {int(nc.yearOfLoss.min())}; {int(s.events.sum()):,} storm reports, {int(s.deaths.sum())} deaths and {int(s.injuries.sum())} injuries since 1996.")])
    p.save("plate_04_hazard_history.png")


def p05():
    lay = layers()
    st = lay["st"]
    ex = T("13_flood_exposure_by_jurisdiction")
    p = Plate(5, KICK, "Flood hazard areas and the buildings in them", "Effective FEMA flood zones (FIRMs effective 2021-01-29) with every structure inside the special flood hazard area (SFHA = A and VE zones)", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "FEMA flood zones and exposed structures", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax, roads=False)
    fz = lay["flood_zones"]
    pal = {"VE": "#B3261E", "A": "#4A90C2", "X500": "#F2C14E"}
    for k in ("X500", "A", "VE"):
        fz[fz.zclass == k].plot(ax=ax, color=pal[k], alpha=0.55, edgecolor="none", zorder=2)
    s = st[st.zclass.isin(["VE", "A"])]
    ax.scatter(s.X, s.Y, s=0.08, c=INK, alpha=0.5, linewidths=0, zorder=5)
    label_places(ax); finish(ax)
    y = p.legend(SX, p.top - 0.35, SW, [("patch", pal["VE"], "Coastal high hazard (VE)"), ("patch", pal["A"], "1% annual chance (A, AE, AO)"), ("patch", pal["X500"], "0.2% annual chance (shaded X)"), ("dot", INK, "structure in the SFHA")], title="Flood zone")
    sf = st.zclass.isin(["VE", "A"])
    y = p.tiles(SX, y - 0.05, SW, [(f"{int(sf.sum()):,}", f"structures in the SFHA ({sf.mean() * 100:.0f}% of all)"), (bn(st.value_total[sf].sum()), "structure and contents value in the SFHA"), (f"{int(st.pop_night[sf].sum()):,}", "night-time residents in the SFHA")])
    p.panel_title(SX, y - 0.1, "B", "Structures in the SFHA by jurisdiction", w=SW)
    e = ex.sort_values("sfha_structures", ascending=False).head(12)
    b = p.ax(SX + 1.9, y - 0.45 - 0.2 * len(e), SW - 2.0, 0.2 * len(e))
    b.barh(range(len(e))[::-1], e.structures_A, color=pal["A"], label="A")
    b.barh(range(len(e))[::-1], e.structures_VE, left=e.structures_A, color=pal["VE"], label="VE")
    for i, (v, sh) in zip(range(len(e))[::-1], zip(e.sfha_structures, e.sfha_share_of_structures)):
        b.text(v, i, f" {int(v):,} ({sh * 100:.0f}%)", va="center", fontsize=6.5, color=MUTED)
    b.set_yticks(range(len(e))[::-1]); b.set_yticklabels(e.jurisdiction, fontsize=7); b.set_xlim(0, e.sfha_structures.max() * 1.45)
    b.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1e3:.0f}k")); b.set_xlabel("structures (share of the jurisdiction's structures)", fontsize=7, color=MUTED)
    b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.notes(SX, y - 0.75 - 0.2 * len(e), SW, [("Check", "Flood zones are this study's own overlay of the effective NFHL on the NSI points; the zone agrees with the NSI's own flood-zone attribute for 99.1% of structures.")])
    p.save("plate_05_flood_hazard_exposure.png")


def hexmap(ax, st, col, cmap, vmax, gs=70, vmin=0):
    m = st[col] > 0
    return ax.hexbin(st.X[m], st.Y[m], C=st[col][m], reduce_C_function=np.sum, gridsize=gs, cmap=cmap, vmin=vmin, vmax=vmax, mincnt=1, linewidths=0.1, edgecolors="white", zorder=4)


def p06():
    lay = layers()
    st = lay["st"]
    sc = T("17_hazus_flood_scenarios")
    j = T("18_hazus_flood_by_jurisdiction")
    p = Plate(6, KICK, "Hazus flood loss: the 1% annual chance flood", "Building and contents loss from Hazus depth-damage functions, with water depth in each structure from the effective base flood elevations and its first-floor elevation", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "Hazus loss, summed in 1 km hexagons", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax)
    cm = LinearSegmentedColormap.from_list("l", ["#FDE9C8", "#F4A259", "#D1495B", "#6B0F1A"])
    hexmap(ax, st, "flood_loss", cm, 5e7)
    label_places(ax); finish(ax)
    base = sc.iloc[0]
    y = p.colorbar(SX, p.top - 0.45, SW, cm, 0, 50, "Loss per hexagon, $ million", ticks=[0, 10, 20, 30, 40, 50], fmt="{:.0f}")
    y = p.tiles(SX, y, SW, [(bn(base.total_loss), "building and contents loss"), (f"{int(base.structures_flooded_above_first_floor):,}", "structures with water above the first floor"), (f"{int(base.displaced_night_population):,}", "residents in those structures")])
    p.panel_title(SX, y - 0.1, "B", "Loss by jurisdiction", w=SW)
    jj = j[j.total_loss > 1e6].head(9)
    b = p.ax(SX + 1.9, y - 0.45 - 0.21 * len(jj), SW - 2.0, 0.21 * len(jj))
    b.barh(range(len(jj))[::-1], jj.building_loss / 1e6, color="#D1495B", label="building")
    b.barh(range(len(jj))[::-1], jj.contents_loss / 1e6, left=jj.building_loss / 1e6, color="#F4A259", label="contents")
    b.set_yticks(range(len(jj))[::-1]); b.set_yticklabels(jj.jurisdiction, fontsize=7); b.legend(fontsize=6.5, frameon=False, loc="lower right")
    b.set_xlabel("$ million", fontsize=7, color=MUTED); b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.notes(SX, y - 0.95 - 0.21 * len(jj), SW, [
        ("Method", "Depth above the first floor = BFE minus first-floor elevation. First floors are NSI ground elevation plus foundation height, raised for post-FIRM buildings to the BFE plus the 2 ft median freeboard measured on 6,377 NFIP-rated buildings in the county (plate 12). Curves: FIA for homes, USACE Galveston averages for other occupancies."),
        ("Range", f"With the NSI's default foundation heights for every building the same flood costs {bn(sc.iloc[-1].total_loss)}: an upper bound."),
    ], fs=7.9)
    p.save("plate_06_hazus_flood_1pct.png")


def p07():
    lay = layers()
    st = lay["st"].copy()
    sc = T("17_hazus_flood_scenarios")
    p = Plate(7, KICK, "Sea-level rise: the same flood on higher water", "Hazus loss for the 1% annual chance flood with 1, 2 and 3 ft added to every base flood elevation (NOAA projections for Charleston put about 1 to 2 ft of rise within the plan's long-range horizon)", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "Added loss with 2 ft of sea-level rise, 1 km hexagons", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax)
    st["added"] = (st.flood_loss_slr2 - st.flood_loss).clip(lower=0)
    cm = LinearSegmentedColormap.from_list("l", ["#E6F0F7", "#7FB2D5", "#2E6A9E", "#0E2A47"])
    hexmap(ax, st, "added", cm, 5e7)
    label_places(ax); finish(ax)
    y = p.colorbar(SX, p.top - 0.45, SW, cm, 0, 50, "Added loss per hexagon, $ million", ticks=[0, 10, 20, 30, 40, 50], fmt="{:.0f}")
    s = sc.iloc[:4]
    p.panel_title(SX, y - 0.05, "B", "Loss and flooded structures by scenario", w=SW)
    b = p.ax(SX + 0.5, y - 0.45 - 2.3, SW - 0.7, 2.3)
    xl = ["today", "+1 ft", "+2 ft", "+3 ft"]
    b.bar(xl, s.total_loss / 1e9, color=["#7FB2D5", "#4F8DBF", "#2E6A9E", "#0E2A47"])
    for i, (v, n) in enumerate(zip(s.total_loss / 1e9, s.structures_flooded_above_first_floor)):
        b.text(i, v, f"${v:,.1f} B\n{n:,} flooded", ha="center", va="bottom", fontsize=7, color=INK)
    b.set_ylim(0, s.total_loss.max() / 1e9 * 1.3); b.set_ylabel("$ billion", fontsize=7.5, color=MUTED); b.tick_params(labelsize=7.5, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.notes(SX, y - 3.2, SW, [("Reading it", f"Two feet of rise turns a {bn(s.total_loss.iloc[0])} flood into {bn(s.total_loss.iloc[2])}. Post-FIRM buildings sit about 2 ft above today's BFE, which is why the jump is steepest between +2 and +3 ft: the freeboard is used up."),
                              ("Undercount", "The rise is added only inside today's SFHA. Higher water also floods land outside it (today's 0.2% zone holds about 41,000 structures), so these losses are a lower bound for each scenario.")], fs=8.0)
    p.save("plate_07_sea_level_rise.png")


def p08():
    lay = layers()
    st = lay["st"]
    sm = pd.read_parquet(PROC / "shakemap_1886_grid.parquet")
    ex = T("24_eq_shaking_exposure")
    p = Plate(8, KICK, "Earthquake: the 1886 Charleston earthquake as today's scenario", "USGS ShakeMap for the M7.0 1886 event (ground motion inferred from felt-intensity reports), sampled at every structure", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "Peak ground acceleration (g)", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax, water=False, roads=False)
    g = gpd.GeoSeries(gpd.points_from_xy(sm.LON, sm.LAT), crs=4326).to_crs(lay["county"].crs)
    x0, y0, x1, y1 = lay["county"].total_bounds
    m = (g.x > x0 - 5000) & (g.x < x1 + 5000) & (g.y > y0 - 5000) & (g.y < y1 + 5000)
    cm = plt.get_cmap("magma_r")
    tri = ax.tricontourf(g.x[m], g.y[m], sm.PGA[m] / 100, levels=np.arange(0.1, 1.21, 0.1), cmap=cm, alpha=0.75, zorder=1)
    cs = ax.tricontour(g.x[m], g.y[m], sm.MMI[m], levels=[7, 8, 9], colors=INK, linewidths=0.6, zorder=6)
    ax.clabel(cs, fmt=lambda v: f"MMI {int(v)}", fontsize=6.5)
    from shapely.geometry import box as sbox
    outside = gpd.GeoSeries([sbox(*ax.get_xlim()[:1], ax.get_ylim()[0], ax.get_xlim()[1], ax.get_ylim()[1]).difference(lay["land"].union_all())], crs=lay["land"].crs) if False else None
    xl, yl = ax.get_xlim(), ax.get_ylim()
    outside = gpd.GeoSeries([sbox(xl[0], yl[0], xl[1], yl[1]).difference(lay["land"].union_all())], crs=lay["land"].crs)
    outside.plot(ax=ax, color="#EEF2F5", alpha=0.9, edgecolor="none", zorder=6.5)
    lay["land"].plot(ax=ax, color="none", edgecolor=INK, lw=0.9, zorder=8)
    lay["water"].plot(ax=ax, color="#C9DCE8", edgecolor="none", alpha=0.8, zorder=2)
    lay["jurisdictions"].boundary.plot(ax=ax, color="#4B535C", lw=0.4, zorder=7)
    info = json.loads((RAW / "shakemap_1886_info.json").read_text())
    try:
        lat, lon = float(info["input"]["event_information"]["latitude"]), float(info["input"]["event_information"]["longitude"])
        e = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(lay["county"].crs)
        ax.plot(e.x, e.y, "*", ms=16, color="#F2C14E", mec=INK, zorder=15)
    except Exception:
        pass
    label_places(ax); finish(ax)
    y = p.colorbar(SX, p.top - 0.45, SW, cm, 0.1, 1.2, "Peak ground acceleration, g", ticks=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2], fmt="{:.1f}")
    y = p.tiles(SX, y, SW, [(f"{st.pga_g.median():.2f} g", "median PGA at structures"), (f"{(st.mmi >= 8).mean() * 100:.0f}%", "of structures at MMI 8 or more"), (f"{int(st.pop_night[st.mmi >= 8].sum()):,}", "night-time residents at MMI 8 or more")])
    p.panel_title(SX, y - 0.1, "B", "Structures by shaking intensity", w=SW)
    b = p.ax(SX + 0.5, y - 0.45 - 1.9, SW - 0.7, 1.9)
    b.bar(ex.MMI.astype(str), ex.structures, color=[cm(v) for v in np.linspace(0.3, 0.9, len(ex))])
    for i_, v_ in enumerate(ex.structures):
        b.text(i_, v_, f"{int(v_):,}", ha="center", va="bottom", fontsize=7, color=INK)
    b.set_ylim(0, ex.structures.max() * 1.18); b.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1e3:.0f}k"))
    b.set_xlabel("Modified Mercalli Intensity", fontsize=7.5, color=MUTED); b.tick_params(labelsize=7.5, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.notes(SX, y - 2.75, SW, [("Why this scenario", "The 1886 earthquake is the largest historical earthquake in the southeastern United States, and its source is still active: USGS ComCat lists 79 earthquakes of magnitude 2 or more within 60 km of Summerville since 2000, in 21 different years (largest M3.6)."),
                              ("Limits", "Ground failure (liquefaction), which was widespread in 1886, is not modelled here; the ShakeMap already includes site amplification from its Vs30 model.")], fs=7.9)
    p.save("plate_08_earthquake_shaking.png")


def p09():
    lay = layers()
    st = lay["st"]
    s = T("21_hazus_eq_summary").iloc[0]
    sens = T("21b_hazus_eq_sensitivity")
    j = T("22_hazus_eq_by_jurisdiction")
    p = Plate(9, KICK, "Hazus earthquake damage and loss: 1886 scenario", "Hazus v6.1 equivalent-PGA fragility curves for each structure's model building type and design level, with Hazus repair-cost ratios", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "Building loss, summed in 1 km hexagons", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax)
    cm = LinearSegmentedColormap.from_list("l", ["#F1E6F4", "#B58AC4", "#7A3C96", "#3B0F55"])
    hexmap(ax, st, "eq_loss", cm, 3e8)
    label_places(ax); finish(ax)
    y = p.colorbar(SX, p.top - 0.45, SW, cm, 0, 300, "Loss per hexagon, $ million", ticks=[0, 100, 200, 300], fmt="{:.0f}")
    y = p.tiles(SX, y, SW, [(bn(s.building_loss), f"building loss ({s.loss_ratio * 100:.0f}% of value)"), (f"{int(s.expected_extensive + s.expected_complete):,}", "structures expected extensively or completely damaged"), (f"{int(s.expected_moderate):,}", "moderately damaged")])
    p.panel_title(SX, y - 0.1, "B", "Sensitivity of the loss", w=SW)
    b = p.ax(SX + 2.35, y - 0.45 - 1.35, SW - 2.45, 1.35)
    b.barh(range(len(sens))[::-1], sens.building_loss / 1e9, color=["#7A3C96", "#B58AC4", "#B58AC4", "#B58AC4"])
    b.set_yticks(range(len(sens))[::-1]); b.set_yticklabels(["base case", "design level +1 step", "PGA x 0.8", "PGA x 1.2"], fontsize=7)
    for i, v in zip(range(len(sens))[::-1], sens.building_loss / 1e9):
        b.text(v, i, f" ${v:,.0f} B", va="center", fontsize=6.8, color=MUTED)
    b.set_xlim(0, sens.building_loss.max() / 1e9 * 1.3); b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.panel_title(SX, y - 2.4, "C", "Expected structures by damage state", w=SW)
    ds = [("none", s.structures - s.expected_slight - s.expected_moderate - s.expected_extensive - s.expected_complete, "#E9E4EE"), ("slight", s.expected_slight, "#CDB6DA"),
          ("moderate", s.expected_moderate, "#A57BBE"), ("extensive", s.expected_extensive, "#7A3C96"), ("complete", s.expected_complete, "#3B0F55")]
    c_ = p.ax(SX, y - 3.1, SW, 0.32)
    left = 0
    for lab, v, col in ds:
        c_.barh(0, v, left=left, color=col, edgecolor="white", lw=0.6)
        if v / s.structures > 0.08:
            c_.text(left + v / 2, 0, f"{lab}\n{v / 1e3:,.0f}k", ha="center", va="center", fontsize=6.6, color="white" if lab in ("extensive", "complete", "moderate") else INK)
        left += v
    c_.set_xlim(0, s.structures); c_.axis("off")
    p.notes(SX, y - 3.35, SW, [
        ("Method", "Model building type from the NSI construction class (wood, masonry, concrete, steel, manufactured), stories and year; design level by year built (before 1975 Pre-Code, 1975 to 1999 Low-Code, 2000 on Moderate-Code). Unreinforced masonry is assumed for masonry before 1975."),
        ("Limits", "The equivalent-PGA curves are Hazus's simplified method (the full method uses spectral capacity curves). Loss is building repair only: no contents, casualties, debris, lifelines or liquefaction. Treat the result as an order of magnitude for planning; the sensitivity range is the honest spread."),
    ], fs=7.8)
    p.save("plate_09_hazus_earthquake_loss.png")


def p10():
    lay = layers()
    tr = lay["tracts"]
    st = lay["st"]
    sv = T("16_social_vulnerability_flood")
    p = Plate(10, KICK, "Social vulnerability and flood exposure", "CDC/ATSDR Social Vulnerability Index (2022, ranked within South Carolina) by census tract, with the special flood hazard area overlaid", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "Social Vulnerability Index and the SFHA", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax, juris=False, roads=False)
    bins = [0, 0.25, 0.5, 0.75, 1.0]
    pal = ["#E8EEF4", "#B7C9DC", "#7D9CC0", "#3A5F8F"]
    tr.plot(ax=ax, column="RPL_THEMES", cmap=ListedColormap(pal), norm=BoundaryNorm(bins, 4), edgecolor="white", lw=0.3, zorder=2, missing_kwds=dict(color="#E3E3E3"))
    fz = lay["flood_zones"]
    fz[fz.zclass.isin(["A", "VE"])].plot(ax=ax, facecolor="none", edgecolor="#B3261E", hatch="////", lw=0.0, alpha=0.5, zorder=3)
    lay["water"].plot(ax=ax, color="#C9DCE8", edgecolor="none", zorder=4)
    lay["jurisdictions"].boundary.plot(ax=ax, color="#4B535C", lw=0.4, zorder=7)
    label_places(ax); finish(ax)
    y = p.legend(SX, p.top - 0.35, SW, [("patch", c, l) for c, l in zip(pal, ["lowest quarter", "second", "third", "highest quarter (0.75+)"])] + [("patch", "#F3C9C6", "SFHA (hatched)")], title="SVI percentile within South Carolina")
    hi = sv[sv.high_svi.str.startswith("High") & (sv.sfha == "In SFHA")]
    allin = sv[sv.sfha == "In SFHA"]
    y = p.tiles(SX, y - 0.05, SW, [(f"{int(hi.structures.sum()):,}", "SFHA structures in high-SVI tracts"), (f"{hi.structures.sum() / allin.structures.sum() * 100:.0f}%", "of all SFHA structures"), (f"{int(hi.night_population.sum()):,}", "night-time residents of those structures")])
    t = tr[["NAMELSAD", "RPL_THEMES"]].copy()
    agg = st.groupby("tract").agg(sfha=("zclass", lambda z: int(z.isin(["VE", "A"]).sum())), loss=("flood_loss", "sum"))
    t = t.join(agg, on=tr.GEOID) if False else t.assign(sfha=tr.GEOID.map(agg.sfha), loss=tr.GEOID.map(agg.loss))
    t = t[t.RPL_THEMES >= 0.75].sort_values("loss", ascending=False).head(8)
    p.panel_title(SX, y - 0.1, "B", "High-SVI tracts with the largest Hazus flood loss", w=SW)
    yy = y - 0.5
    p.bg.text(SX, yy, "Tract", fontsize=7.4, color=MUTED, fontweight="bold"); p.bg.text(SX + 2.6, yy, "SVI", fontsize=7.4, color=MUTED, fontweight="bold", ha="right")
    p.bg.text(SX + 3.7, yy, "SFHA bldgs", fontsize=7.4, color=MUTED, fontweight="bold", ha="right"); p.bg.text(SX + SW, yy, "1% flood loss", fontsize=7.4, color=MUTED, fontweight="bold", ha="right")
    for _, r in t.iterrows():
        yy -= 0.22
        p.bg.text(SX, yy, r.NAMELSAD.replace("Census Tract", "Tract"), fontsize=7.4); p.bg.text(SX + 2.6, yy, f"{r.RPL_THEMES:.2f}", fontsize=7.4, ha="right")
        p.bg.text(SX + 3.7, yy, f"{int(r.sfha or 0):,}", fontsize=7.4, ha="right"); p.bg.text(SX + SW, yy, bn(r.loss or 0), fontsize=7.4, ha="right")
    p.notes(SX, yy - 0.35, SW, [("Why it matters", "Households in high-SVI tracts have fewer resources to prepare, evacuate and rebuild; the plan can weight mitigation actions (acquisition, elevation, outreach) toward these tracts.")], fs=8.0)
    p.save("plate_10_social_vulnerability.png")


def p11():
    lay = layers()
    tr = lay["tracts"].copy()
    c = pd.DataFrame(json.loads((RAW / "nfip_claims_45019.json").read_text()))
    for k in ("amountPaidOnBuildingClaim", "amountPaidOnContentsClaim", "amountPaidOnIncreasedCostOfComplianceClaim"):
        c[k] = pd.to_numeric(c[k], errors="coerce").fillna(0)
    c["paid"] = c.amountPaidOnBuildingClaim + c.amountPaidOnContentsClaim + c.amountPaidOnIncreasedCostOfComplianceClaim
    c["tract"] = c.censusGeoid.astype(str).str[:11]
    m = pd.DataFrame(json.loads((RAW / "nfip_multiple_loss_45019.json").read_text()))
    m["tract"] = m.censusBlockGroup.astype(str).str[:11]
    tr["paid"] = tr.GEOID.map(c.groupby("tract").paid.sum()).fillna(0)
    tr["rl"] = tr.GEOID.map(m.groupby("tract").id.count()).fillna(0)
    rl = T("08_repetitive_loss_by_community")
    p = Plate(11, KICK, "Where flood losses have already happened: NFIP claims and repetitive loss", "NFIP claim payments since 1978 and NFIP multiple-loss properties, by census tract", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "NFIP payments by census tract, with repetitive-loss properties", w=9.5)
    ax = p.ax(0.6, 0.9, 9.5, p.top - 1.5)
    basemap(ax, juris=False, roads=False)
    bins = [0, 1e6, 5e6, 2e7, 5e7, 1e9]
    pal = ["#FFF5EB", "#FDD0A2", "#FD8D3C", "#D94801", "#7F2704"]
    tr.plot(ax=ax, column="paid", cmap=ListedColormap(pal), norm=BoundaryNorm(bins, 5), edgecolor="white", lw=0.3, zorder=2)
    lay["water"].plot(ax=ax, color="#C9DCE8", edgecolor="none", zorder=3)
    cc = tr[tr.rl > 0].copy()
    cc["pt"] = cc.geometry.representative_point()
    ax.scatter(cc.pt.x, cc.pt.y, s=cc.rl * 1.6, color=ACCENT, alpha=0.65, edgecolors="white", lw=0.5, zorder=9)
    lay["jurisdictions"].boundary.plot(ax=ax, color="#4B535C", lw=0.4, zorder=7)
    label_places(ax); finish(ax)
    y = p.legend(SX, p.top - 0.35, SW, [("patch", c_, l) for c_, l in zip(pal, ["under $1 M", "$1 to 5 M", "$5 to 20 M", "$20 to 50 M", "$50 M or more"])] + [("dot", ACCENT, "multiple-loss properties (size = count)")], title="NFIP payments since 1978 (nominal)")
    y = p.tiles(SX, y - 0.05, SW, [(f"{len(c):,}", "NFIP claims"), (bn(c.paid.sum()), "paid"), (f"{len(m):,}", f"multiple-loss properties ({int(m.nfipSrl.sum())} severe; {int(m.mitigatedIndicator.sum())} mitigated)")])
    p.panel_title(SX, y - 0.1, "B", "Multiple-loss properties by community", w=SW)
    r2 = rl.head(10)
    b = p.ax(SX + 2.0, y - 0.45 - 0.21 * len(r2), SW - 2.1, 0.21 * len(r2))
    b.barh(range(len(r2))[::-1], r2.properties, color=ACCENT)
    b.barh(range(len(r2))[::-1], r2.severe_repetitive_loss, color="#B3261E")
    b.legend(["all multiple-loss", "severe repetitive loss"], fontsize=6.8, frameon=False, loc="lower right")
    b.set_yticks(range(len(r2))[::-1]); b.set_yticklabels([s.title().replace("*", "").replace(", City Of", "").replace(", Town Of", "") for s in r2.communityName], fontsize=7)
    b.tick_params(labelsize=7, colors=MUTED); b.spines[["top", "right"]].set_visible(False)
    p.notes(SX, y - 0.75 - 0.21 * len(r2), SW, [("Reading it", "Dark red bars are severe repetitive-loss properties within each community's total; these are the first candidates for acquisition or elevation under FEMA's Flood Mitigation Assistance program.")], fs=8)
    p.save("plate_11_nfip_repetitive_loss.png")


def p12():
    chk = T("26_first_floor_check_nfip")
    c = pd.DataFrame(json.loads((RAW / "nfip_claims_45019.json").read_text()))
    c["ed"] = pd.to_numeric(c.elevationDifference, errors="coerce")
    c = c[c.ed.between(-12, 12) & c.ratedFloodZone.fillna("").str[:1].isin(["A", "V"])]
    st = layers()["st"]
    s = st[st.zclass.isin(["A", "VE"]) & st.bfe.notna()]
    p = Plate(12, KICK, "Checking the flood model: first-floor elevations against NFIP records", "The Hazus flood loss depends on how high each first floor sits above the base flood elevation; NFIP elevation-rated buildings give an independent measure", SRC)
    p.panel_title(0.6, p.top - 0.3, "A", "First floor minus BFE (ft)", w=9.5)
    a = p.ax(1.1, 1.2, 8.9, p.top - 1.75)
    bins = np.arange(-12, 12.5, 1)
    a.hist(c.ed, bins=bins, density=True, alpha=0.85, color="#9AA1AA", label=f"NFIP elevation-rated buildings ({len(c):,})")
    a.hist((s.ffe_ft - s.bfe).clip(-12, 12), bins=bins, density=True, histtype="step", lw=2, color="#B3261E", label="NSI default foundation heights")
    a.hist((s.ffe_adj - s.bfe).clip(-12, 12), bins=bins, density=True, histtype="step", lw=2, color=ACCENT, label="adjusted (pre/post-FIRM), used for loss")
    a.axvline(0, color=INK, lw=0.8); a.text(0.2, a.get_ylim()[1] * 0.95, "BFE", fontsize=8)
    a.legend(fontsize=8, frameon=False); a.set_xlabel("first floor minus base flood elevation, ft", fontsize=8, color=MUTED); a.set_ylabel("share of buildings", fontsize=8, color=MUTED)
    a.tick_params(labelsize=8, colors=MUTED); a.spines[["top", "right"]].set_visible(False)
    r = chk.set_index("zone")
    y = p.tiles(SX, p.top - 0.45, SW, [(f"{r.loc['A', 'nfip_share_below_bfe'] * 100:.0f}%", "NFIP-rated A-zone buildings below BFE"), (f"{r.loc['A', 'nsi_default_share_below_bfe'] * 100:.0f}%", "NSI defaults below BFE"), (f"{r.loc['A', 'adjusted_share_below_bfe'] * 100:.0f}%", "adjusted, used for loss")])
    p.notes(SX, y - 0.05, SW, [
        ("What was wrong", "The NSI gives each building a default foundation height for its foundation type (slab 0.75 ft, crawlspace 2 ft, pier 5.25 ft). Against today's BFEs that leaves 68% of A-zone buildings below the BFE; NFIP elevation certificates show 10%."),
        ("The fix", "Every Charleston County community entered the NFIP with a FIRM in 1971, so buildings from 1975 on are taken to meet the ordinance: first floor at today's BFE plus the 2.0 ft median freeboard of post-FIRM, elevation-rated NFIP buildings in the county (6,377 claims). Older buildings keep the NSI value."),
        ("Remaining bias", "NFIP-rated buildings are insured and mostly post-FIRM, so they sit higher than the whole stock. The NSI year built is a block-group median, not the building's own year. Both are why the NSI-default loss is kept as an upper bound."),
    ], fs=8.1)
    p.save("plate_12_flood_model_check.png")


PLATES = {1: p01, 2: p02, 3: p03, 4: p04, 5: p05, 6: p06, 7: p07, 8: p08, 9: p09, 10: p10, 11: p11, 12: p12}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for k, fn in PLATES.items():
        if which in (str(k), "all"):
            fn()
