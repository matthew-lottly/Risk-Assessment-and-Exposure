"""Risk assessment for the Charleston County hazard mitigation plan: hazard profile tables, exposure tables, Hazus flood and earthquake losses.
Writes outputs/tables/*.csv, outputs/tables/charleston_risk_assessment_tables.xlsx and data/processed/*.parquet used by the maps.
Usage: python scripts/run_analysis.py
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import geopandas as gpd
import numpy as np
import pandas as pd

from riskx import hazus as HZ

RAW, PROC, TAB = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs" / "tables"
TAB.mkdir(parents=True, exist_ok=True)
TABLES = {}
ZONE_LAB = {"VE": "Coastal high hazard (VE)", "A": "1% annual chance (A, AE, AO)", "X500": "0.2% annual chance (shaded X)", "X": "Outside mapped flood hazard (X)"}
OCC_LAB = {"RES": "Residential", "COM": "Commercial", "IND": "Industrial", "AGR": "Agricultural", "REL": "Religious", "GOV": "Government", "EDU": "Education"}
CRIT = {"COM6": "Hospitals", "RES6": "Nursing homes", "EDU1": "Schools", "EDU2": "Colleges and universities", "GOV1": "Government offices", "GOV2": "Emergency response (fire, police, EOC)"}
NRI_HAZ = {"AVLN": "Avalanche", "CFLD": "Coastal flooding", "CWAV": "Cold wave", "DRGT": "Drought", "ERQK": "Earthquake", "HAIL": "Hail", "HWAV": "Heat wave", "HRCN": "Hurricane",
           "ISTM": "Ice storm", "LNDS": "Landslide", "LTNG": "Lightning", "RFLD": "Riverine flooding", "SWND": "Strong wind", "TRND": "Tornado", "TSUN": "Tsunami", "VLCN": "Volcanic activity",
           "WFIR": "Wildfire", "WNTW": "Winter weather"}


def save(name, df, note=""):
    TABLES[name] = (df, note)
    df.to_csv(TAB / f"{name}.csv", index=False)


def money(x):
    """Storm Events damage strings (e.g. 25.00K, 1.5M) to dollars."""
    if not isinstance(x, str) or not x:
        return 0.0
    m = {"K": 1e3, "M": 1e6, "B": 1e9}
    x = x.strip().upper()
    return float(x[:-1] or 0) * m[x[-1]] if x[-1] in m else float(x)


def hazard_profile():
    c = gpd.read_file(RAW / "nri_counties_sc.geojson")
    r = c[c.STCOFIPS == "45019"].iloc[0]
    rows = []
    for p, name in NRI_HAZ.items():
        rows.append(dict(hazard=name, annualized_frequency=r.get(f"{p}_AFREQ"), expected_annual_loss=r.get(f"{p}_EALT"), eal_buildings=r.get(f"{p}_EALB"),
                         eal_population_equivalence=r.get(f"{p}_EALPE"), eal_agriculture=r.get(f"{p}_EALA"), eal_rating=r.get(f"{p}_EALR"), risk_score=r.get(f"{p}_RISKS"), risk_rating=r.get(f"{p}_RISKR")))
    t = pd.DataFrame(rows).sort_values("expected_annual_loss", ascending=False)
    t["share_of_eal"] = t.expected_annual_loss / t.expected_annual_loss.sum()
    save("01_nri_hazard_ranking", t, f"FEMA National Risk Index ({r.NRI_VER}), Charleston County. Composite risk score {r.RISK_SCORE:.1f} ({r.RISK_RATNG}); total EAL ${r.EAL_VALT/1e6:,.0f} M per year; social vulnerability {r.SOVI_RATNG}; community resilience {r.RESL_RATNG}.")
    sc = c[["COUNTY", "STCOFIPS", "POPULATION", "BUILDVALUE", "RISK_SCORE", "RISK_RATNG", "EAL_VALT", "SOVI_RATNG", "RESL_RATNG"]].sort_values("RISK_SCORE", ascending=False)
    sc["rank_in_sc"] = np.arange(1, len(sc) + 1)
    save("02_nri_sc_county_ranking", sc, "National Risk Index composite risk for all 46 South Carolina counties.")
    return r


def history():
    d = pd.DataFrame(json.loads((RAW / "fema_declarations_45019.json").read_text()))
    d = d.drop_duplicates("disasterNumber").sort_values("declarationDate")
    dd = d[["femaDeclarationString", "declarationType", "declarationDate", "incidentType", "declarationTitle", "incidentBeginDate", "incidentEndDate", "ihProgramDeclared", "paProgramDeclared", "hmProgramDeclared"]].copy()
    for k in ("declarationDate", "incidentBeginDate", "incidentEndDate"):
        dd[k] = dd[k].str[:10]
    save("03_disaster_declarations", dd, f"All FEMA disaster declarations that designated Charleston County ({len(dd)}), OpenFEMA.")
    s = pd.read_csv(RAW / "storm_events_45019.csv", low_memory=False)
    s["prop"] = s.DAMAGE_PROPERTY.map(money)
    s["crop"] = s.DAMAGE_CROPS.map(money)
    s["deaths"] = s.DEATHS_DIRECT.fillna(0) + s.DEATHS_INDIRECT.fillna(0)
    s["injuries"] = s.INJURIES_DIRECT.fillna(0) + s.INJURIES_INDIRECT.fillna(0)
    s["year"] = s.BEGIN_YEARMONTH // 100
    yrs = s.year.max() - s.year.min() + 1
    g = s.groupby("EVENT_TYPE").agg(events=("EVENT_ID", "count"), event_days=("BEGIN_DATE_TIME", lambda x: x.str[:10].nunique()), deaths=("deaths", "sum"), injuries=("injuries", "sum"),
                                     property_damage=("prop", "sum"), crop_damage=("crop", "sum"), first_year=("year", "min"), last_year=("year", "max")).reset_index()
    g["events_per_year"] = g.events / yrs
    g = g.sort_values("property_damage", ascending=False)
    save("04_storm_events_summary", g, f"NOAA NCEI Storm Events, Charleston County and its forecast zones, {s.year.min()} to {s.year.max()} ({yrs} years). Damage in nominal dollars as reported; not inflation-adjusted.")
    c = pd.DataFrame(json.loads((RAW / "nfip_claims_45019.json").read_text()))
    for k in ("amountPaidOnBuildingClaim", "amountPaidOnContentsClaim", "amountPaidOnIncreasedCostOfComplianceClaim"):
        c[k] = pd.to_numeric(c[k], errors="coerce").fillna(0)
    c["paid"] = c.amountPaidOnBuildingClaim + c.amountPaidOnContentsClaim + c.amountPaidOnIncreasedCostOfComplianceClaim
    cy = c.groupby("yearOfLoss").agg(claims=("id", "count"), paid=("paid", "sum")).reset_index()
    save("05_nfip_claims_by_year", cy, f"NFIP redacted claims, Charleston County: {len(c):,} claims, ${c.paid.sum()/1e6:,.1f} M paid (nominal), {int(c.yearOfLoss.min())} to {int(c.yearOfLoss.max())}.")
    c["zone"] = c.ratedFloodZone.fillna("unknown").str[:1].map({"V": "V zones", "A": "A zones", "X": "X zones", "B": "B/C (old maps)", "C": "B/C (old maps)", "D": "D"}).fillna("unknown")
    cz = c.groupby("zone").agg(claims=("id", "count"), paid=("paid", "sum")).reset_index()
    cz["share_of_claims"] = cz.claims / cz.claims.sum()
    save("06_nfip_claims_by_zone", cz, "Claims by rated flood zone: a large share outside the A and V zones shows flooding beyond the 1% annual chance floodplain.")
    ev = c.groupby("floodEvent").agg(claims=("id", "count"), paid=("paid", "sum")).reset_index().sort_values("paid", ascending=False).head(15)
    save("07_nfip_top_flood_events", ev, "The 15 named flood events with the largest NFIP payments in Charleston County.")
    m = pd.DataFrame(json.loads((RAW / "nfip_multiple_loss_45019.json").read_text()))
    mm = m.groupby("communityName").agg(properties=("id", "count"), repetitive_loss=("nfipRl", "sum"), severe_repetitive_loss=("nfipSrl", "sum"), mitigated=("mitigatedIndicator", "sum"),
                                        insured=("insuredIndicator", "sum"), total_losses=("totalLosses", "sum")).reset_index().sort_values("properties", ascending=False)
    save("08_repetitive_loss_by_community", mm, f"NFIP multiple-loss properties ({len(m):,}): repetitive loss (RL) and severe repetitive loss (SRL), with how many are mitigated.")
    q = gpd.read_file(RAW / "usgs_quakes_200km.geojson")
    q["time"] = pd.to_datetime(q.time, unit="ms").dt.date.astype(str)
    q = q[q.mag >= 3.0][["time", "mag", "place", "depth"]] if "depth" in q else q[q.mag >= 3.0][["time", "mag", "place"]]
    save("09_earthquakes_m3_200km", q.sort_values("mag", ascending=False), "USGS ComCat earthquakes of magnitude 3 or more within 200 km of Charleston, including the 1886 event.")
    h = pd.DataFrame(json.loads((RAW / "hma_subapplications_sc.json").read_text()))
    h = h[h.benefitingCounties.astype(str).str.contains("Charleston", na=False)]
    hh = h.groupby(["program", "primaryHazard"]).agg(subapplications=("id", "count"), total_amount=("totalSubapplicationAmount", "sum")).reset_index().sort_values("total_amount", ascending=False)
    save("10_hma_subapplications", hh, f"FEMA Hazard Mitigation Assistance subapplications benefiting Charleston County ({len(h)}), by program and hazard.")
    p = pd.DataFrame(json.loads((RAW / "hm_plan_status_sc.json").read_text()))
    p = p[p.countyName.astype(str).str.contains("Charleston")][["placeName", "jurisdictionType", "planTitle", "planStatus", "planApprovalDate", "planExpirationDate", "jurisdictionStatus"]]
    for k in ("planApprovalDate", "planExpirationDate"):
        p[k] = p[k].astype(str).str[:10]
    save("11_hm_plan_status", p, "Status of the current Charleston County multi-jurisdictional hazard mitigation plan (OpenFEMA).")
    cs = pd.DataFrame(json.loads((RAW / "nfip_community_status_sc.json").read_text()))
    cs = cs[cs.county.astype(str).str.upper().str.contains("CHARLESTON")][["communityIdNumber", "communityName", "initialFloodInsuranceRateMap", "currentlyEffectiveMapDate", "classRating", "participatingInNFIP"]]
    cs["initialFloodInsuranceRateMap"] = cs.initialFloodInsuranceRateMap.astype(str).str[:10]
    save("27_nfip_community_status", cs.rename(columns={"classRating": "crs_class"}), "NFIP participation, first FIRM date, effective map date and Community Rating System class of each community (OpenFEMA Community Status Book).")
    return s, c


def exposure(st):
    st = st.copy()
    st["occ_group"] = st.occ_base.str[:3].map(OCC_LAB).fillna("Other")
    inv = st.groupby("occ_group").agg(structures=("fd_id", "count"), structure_value=("val_struct", "sum"), content_value=("val_cont", "sum"), night_population=("pop_night", "sum")).reset_index()
    inv.loc[len(inv)] = ["Total", inv.structures.sum(), inv.structure_value.sum(), inv.content_value.sum(), inv.night_population.sum()]
    save("12_building_inventory", inv, "USACE National Structure Inventory, Charleston County: every structure, replacement values in 2022-era dollars as published by the NSI.")
    rows = []
    for (j, z), g in st.groupby(["jurisdiction", "zclass"]):
        rows.append(dict(jurisdiction=j, zone=z, structures=len(g), value=g.value_total.sum(), night_population=g.pop_night.sum()))
    e = pd.DataFrame(rows)
    tot = st.groupby("jurisdiction").agg(all_structures=("fd_id", "count"), all_value=("value_total", "sum"), all_pop=("pop_night", "sum"))
    w = e.pivot_table(index="jurisdiction", columns="zone", values=["structures", "value", "night_population"], fill_value=0)
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w.join(tot)
    for z in ("VE", "A", "X500"):
        for a in ("structures", "value", "night_population"):
            if f"{a}_{z}" not in w:
                w[f"{a}_{z}"] = 0
    w["sfha_structures"] = w.structures_VE + w.structures_A
    w["sfha_value"] = w.value_VE + w.value_A
    w["sfha_share_of_structures"] = w.sfha_structures / w.all_structures
    w = w.reset_index().sort_values("sfha_value", ascending=False)
    cols = ["jurisdiction", "all_structures", "structures_VE", "structures_A", "structures_X500", "sfha_structures", "sfha_share_of_structures", "all_value", "value_VE", "value_A", "value_X500", "sfha_value", "all_pop", "night_population_VE", "night_population_A", "night_population_X500"]
    save("13_flood_exposure_by_jurisdiction", w[cols], "Structures, value (structure plus contents) and night-time population in each FEMA flood zone, by jurisdiction. SFHA = VE plus A zones.")
    o = st.groupby(["occ_group", "zclass"]).agg(structures=("fd_id", "count"), value=("value_total", "sum")).reset_index()
    o["zone"] = o.zclass.map(ZONE_LAB)
    save("14_flood_exposure_by_occupancy", o.drop(columns="zclass"), "Flood exposure by occupancy group and flood zone.")
    cf = st[st.occ_base.isin(CRIT)].copy()
    cf["facility_type"] = cf.occ_base.map(CRIT)
    ct = cf.pivot_table(index="facility_type", columns="zclass", values="fd_id", aggfunc="count", fill_value=0).reset_index()
    save("15_critical_facilities_flood", ct, "Critical facility structures by type and flood zone, identified from NSI occupancy classes (COM6, RES6, EDU1, EDU2, GOV1, GOV2); a facility campus can count as several structures.")
    t = st.assign(high_svi=st.svi >= 0.75, sfha=st.zclass.isin(["VE", "A"]))
    sv = t.groupby(["high_svi", "sfha"]).agg(structures=("fd_id", "count"), night_population=("pop_night", "sum"), value=("value_total", "sum")).reset_index()
    sv["high_svi"] = sv.high_svi.map({True: "High social vulnerability (SVI 0.75 or more)", False: "Lower social vulnerability"})
    sv["sfha"] = sv.sfha.map({True: "In SFHA", False: "Outside SFHA"})
    save("16_social_vulnerability_flood", sv, "Flood exposure in census tracts in the top quartile of the CDC/ATSDR Social Vulnerability Index (2022, ranked within South Carolina).")
    return st


FIRM_YEAR = 1975  # every Charleston County community's first FIRM is 1971 (James Island's own 2004 FIRM followed the county's); 1975 allows for a lag in enforcement


def first_floor(st):
    """Two first-floor elevations. 'nsi': NSI ground elevation plus its default foundation height for the foundation type (slab 0.75 ft, crawlspace 2 ft, pier 5.25 ft).
    'adjusted' (Hazus-style pre/post-FIRM): a structure in the SFHA whose block-group median year built is after the first FIRM is taken to meet the floodplain
    ordinance, i.e. its first floor is at least today's BFE plus the median height above BFE measured on post-FIRM, elevation-rated NFIP buildings in the county; pre-FIRM structures keep the NSI value."""
    c = pd.DataFrame(json.loads((RAW / "nfip_claims_45019.json").read_text()))
    c["ed"] = pd.to_numeric(c.elevationDifference, errors="coerce")
    m = c.ed.between(-30, 30) & c.ratedFloodZone.fillna("").str[:1].isin(["A", "V"]) & (c.postFIRMConstructionIndicator == True)
    offset = float(c.ed[m].median())  # measured: median lowest floor above BFE of post-FIRM, elevation-rated NFIP buildings in this county
    post = st.med_yr_blt.fillna(0) >= FIRM_YEAR
    adj = np.where(post & st.bfe.notna(), np.maximum(st.ffe_ft, st.bfe + offset), st.ffe_ft)
    print("post-FIRM first-floor offset above BFE (ft):", offset, "from", int(m.sum()), "claims")
    return st.ffe_ft.to_numpy(float), adj, post


def validate_ffe(st, adj):
    c = pd.DataFrame(json.loads((RAW / "nfip_claims_45019.json").read_text()))
    c["ed"] = pd.to_numeric(c.elevationDifference, errors="coerce")
    z = c.ratedFloodZone.fillna("").str[:1]
    rows = []
    for zz, lab in (("A", "A"), ("V", "VE")):
        m = (z == zz) & c.ed.between(-30, 30)
        s = st.zclass.eq(lab) & st.bfe.notna()
        rows.append(dict(zone=lab, nfip_rated_buildings=int(m.sum()), nfip_median_floor_minus_bfe_ft=float(c.ed[m].median()), nfip_share_below_bfe=float((c.ed[m] < 0).mean()),
                         nsi_structures=int(s.sum()), nsi_default_median_floor_minus_bfe_ft=float((st.ffe_ft - st.bfe)[s].median()), nsi_default_share_below_bfe=float(((st.ffe_ft - st.bfe)[s] < 0).mean()),
                         adjusted_median_floor_minus_bfe_ft=float((adj - st.bfe)[s].median()), adjusted_share_below_bfe=float(((adj - st.bfe)[s] < 0).mean())))
    save("26_first_floor_check_nfip", pd.DataFrame(rows), "Check of first-floor elevations against NFIP claims that carry an elevation-certificate rating (lowest floor minus BFE). NFIP-rated buildings are a biased sample "
         "(insured, mostly post-FIRM), but the NSI's default foundation heights put far too many buildings below the BFE, so the adjusted (pre/post-FIRM) elevations are the central estimate and the NSI defaults an upper bound.")


def hazus_flood(st):
    ddfs = HZ.load_ddfs()
    inA = st.zclass.isin(["VE", "A"]) & st.bfe.notna()
    ffe_nsi, ffe_adj, post = first_floor(st)
    validate_ffe(st, ffe_adj)
    res = {}
    rows = []
    for slr in (0, 1, 2, 3):
        d = np.where(inA, st.bfe + slr - ffe_adj, np.nan)
        L = HZ.flood_loss(st, d, ddfs)
        res[slr] = (d, L)
        dmg = L.structural_ratio > 0
        rows.append(dict(scenario="1% annual chance flood" + (f" + {slr} ft sea-level rise" if slr else " (effective FIRM)"), structures_with_bfe=int(inA.sum()),
                         structures_flooded_above_first_floor=int((d > 0).sum()), structures_damaged=int(dmg.sum()), structures_over_50pct_damage=int((L.structural_ratio >= 0.5).sum()),
                         building_loss=L.structural_loss.sum(), contents_loss=L.contents_loss.sum(), total_loss=L.total_loss.sum(), displaced_night_population=float(st.pop_night[d > 0].sum())))
    d = np.where(inA, st.bfe - ffe_nsi, np.nan)
    L = HZ.flood_loss(st, d, ddfs)
    rows.append(dict(scenario="1% annual chance flood, NSI default first floors (upper bound)", structures_with_bfe=int(inA.sum()), structures_flooded_above_first_floor=int((d > 0).sum()),
                     structures_damaged=int((L.structural_ratio > 0).sum()), structures_over_50pct_damage=int((L.structural_ratio >= 0.5).sum()), building_loss=L.structural_loss.sum(),
                     contents_loss=L.contents_loss.sum(), total_loss=L.total_loss.sum(), displaced_night_population=float(st.pop_night[d > 0].sum())))
    sc = pd.DataFrame(rows)
    save("17_hazus_flood_scenarios", sc, "Hazus flood depth-damage loss for the 1% annual chance flood from the effective FIRM base flood elevations, and the same flood with 1 to 3 ft of sea-level rise added "
         "(applied only inside today's SFHA, so the rise scenarios undercount). Depth in a structure = BFE minus first-floor elevation; post-FIRM structures are taken at today's BFE plus the NFIP-measured median freeboard (see table 26). "
         "The last row uses the NSI's default foundation heights for every structure and is an upper bound. Water below the first floor still causes the small losses the Hazus curves give for negative depths.")
    d0, L0 = res[0]
    st = st.assign(post_firm=post, ffe_adj=ffe_adj, depth_ft=d0, flood_bldg_ratio=L0.structural_ratio, flood_bldg_loss=L0.structural_loss, flood_cont_loss=L0.contents_loss, flood_loss=L0.total_loss,
                   flood_loss_slr2=res[2][1].total_loss)
    j = st.groupby("jurisdiction").agg(structures_in_sfha=("zclass", lambda z: int(z.isin(["VE", "A"]).sum())), flooded_above_first_floor=("depth_ft", lambda x: int((x > 0).sum())),
                                       building_loss=("flood_bldg_loss", "sum"), contents_loss=("flood_cont_loss", "sum"), total_loss=("flood_loss", "sum"), total_loss_with_2ft_slr=("flood_loss_slr2", "sum")).reset_index()
    j = j.sort_values("total_loss", ascending=False)
    save("18_hazus_flood_by_jurisdiction", j, "Hazus 1% annual chance flood loss by jurisdiction (structure and contents).")
    o = st[st.flood_loss > 0].groupby(st.occ_base.str[:3].map(OCC_LAB)).agg(structures=("fd_id", "count"), total_loss=("flood_loss", "sum")).reset_index().rename(columns={"occ_base": "occupancy"})
    save("19_hazus_flood_by_occupancy", o, "Hazus 1% annual chance flood loss by occupancy group.")
    used = pd.Series(np.r_[L0.structural_ddf[L0.structural_ratio > 0].to_numpy(), L0.contents_ddf[L0.contents_ratio > 0].to_numpy()]).value_counts().reset_index()
    used.columns = ["hazus_ddf", "structures"]
    save("20_hazus_flood_ddfs_used", used, "The Hazus depth-damage functions applied, with how many damaged structures used each.")
    return st


def hazus_eq(st):
    years = st.med_yr_blt.fillna(1980).astype(int)
    bt = [HZ.eq_building_type(b, o, s, y) for b, o, s, y in zip(st.bldgtype, st.occ_base, st.stories, years)]
    inv = pd.DataFrame(dict(btype=[b for b, _ in bt], hclass=[h for _, h in bt], occ_base=st.occ_base.values, val_struct=st.val_struct.values), index=st.index)
    inv["design"] = [HZ.design_level(y, b) for y, b in zip(years, inv.btype)]
    E = HZ.eq_damage(inv, st.pga_g.values)
    st = st.assign(eq_btype=inv.btype, eq_design=inv.design, eq_loss=E.building_loss, eq_ratio=E.loss_ratio, p_slight=E.p_slight, p_moderate=E.p_moderate, p_extensive=E.p_extensive, p_complete=E.p_complete)
    st["p_ext_or_comp"] = st.p_extensive + st.p_complete
    tot = dict(scenario="1886 Charleston earthquake (M7.0, USGS ShakeMap) repeated today", structures=len(st), median_pga_g=float(st.pga_g.median()), max_pga_g=float(st.pga_g.max()),
               expected_slight=float(st.p_slight.sum()), expected_moderate=float(st.p_moderate.sum()), expected_extensive=float(st.p_extensive.sum()), expected_complete=float(st.p_complete.sum()),
               building_loss=float(st.eq_loss.sum()), loss_ratio=float(st.eq_loss.sum() / st.val_struct.sum()))
    save("21_hazus_eq_summary", pd.DataFrame([tot]), "Hazus earthquake building damage from equivalent-PGA fragility curves (Hazus EQ v6.1) and building repair-cost ratios for the 1886 ShakeMap; expected numbers of structures in each damage state. Structural, building-only loss; no contents, casualties, debris or liquefaction.")
    # sensitivity: one design level higher (1975-1999 Moderate-Code, 2000 on High-Code: Charleston's newer buildings fall in a high seismic design category), and PGA x 0.8 / x 1.2
    sens = []
    up = {"Pre-Code": "Pre-Code", "Low-Code": "Moderate-Code", "Moderate-Code": "High-Code"}
    inv2 = inv.copy()
    inv2["design"] = [up[d] if b not in ("URM", "S5", "C3") else d for d, b in zip(inv.design, inv.btype)]
    for lab, iv, f in (("base case", inv, 1.0), ("design level one step higher for buildings from 1975 on", inv2, 1.0), ("ShakeMap PGA x 0.8", inv, 0.8), ("ShakeMap PGA x 1.2", inv, 1.2)):
        Ei = HZ.eq_damage(iv, st.pga_g.values * f)
        sens.append(dict(case=lab, expected_extensive_or_complete=float((Ei.p_extensive + Ei.p_complete).sum()), building_loss=float(Ei.building_loss.sum()), loss_ratio=float(Ei.building_loss.sum() / st.val_struct.sum())))
    save("21b_hazus_eq_sensitivity", pd.DataFrame(sens), "How much the earthquake loss depends on the assumed seismic design levels and on the ShakeMap ground motion (which for 1886 is inferred from felt-intensity reports, not instruments).")
    j = st.groupby("jurisdiction").agg(structures=("fd_id", "count"), median_pga_g=("pga_g", "median"), expected_moderate=("p_moderate", "sum"), expected_extensive=("p_extensive", "sum"),
                                       expected_complete=("p_complete", "sum"), building_loss=("eq_loss", "sum"), building_value=("val_struct", "sum")).reset_index()
    j["loss_ratio"] = j.building_loss / j.building_value
    save("22_hazus_eq_by_jurisdiction", j.sort_values("building_loss", ascending=False), "Hazus earthquake damage and loss for the 1886 scenario by jurisdiction.")
    b = st.groupby(["eq_btype", "eq_design"]).agg(structures=("fd_id", "count"), mean_pga_g=("pga_g", "mean"), expected_extensive_or_complete=("p_ext_or_comp", "sum"), building_loss=("eq_loss", "sum")).reset_index()
    save("23_hazus_eq_by_building_type", b.sort_values("building_loss", ascending=False), "Hazus earthquake damage by model building type and seismic design level (assigned from the NSI's general construction type, stories and year built).")
    m = st.groupby(st.mmi.round().astype(int)).agg(structures=("fd_id", "count"), value=("value_total", "sum"), night_population=("pop_night", "sum")).reset_index().rename(columns={"mmi": "MMI"})
    save("24_eq_shaking_exposure", m, "Exposure to 1886-scenario shaking intensity (Modified Mercalli Intensity from the ShakeMap).")
    return st


def wind_tract(st):
    tr = gpd.read_file(PROC / "county.gpkg", layer="tracts")
    keep = ["GEOID", "NAMELSAD", "POPULATION", "BUILDVALUE", "RISK_SCORE", "RISK_RATNG", "EAL_VALT", "HRCN_EALT", "HRCN_RISKR", "CFLD_EALT", "CFLD_RISKR", "RFLD_EALT", "ERQK_EALT", "TRND_EALT", "RPL_THEMES", "RESL_RATNG"]
    t = tr[[k for k in keep if k in tr]].copy()
    agg = st.groupby("tract").agg(structures=("fd_id", "count"), sfha_structures=("zclass", lambda z: int(z.isin(["VE", "A"]).sum())), hazus_flood_loss=("flood_loss", "sum"), hazus_eq_loss=("eq_loss", "sum"))
    t = t.merge(agg, left_on="GEOID", right_index=True, how="left")
    save("25_tract_risk_profile", t.sort_values("RISK_SCORE", ascending=False), "Census-tract risk profile: NRI composite risk and hazard EAL, CDC SVI, and this study's Hazus flood and earthquake losses.")


def main():
    r = hazard_profile()
    s, c = history()
    st = pd.read_parquet(PROC / "structures.parquet")
    st = exposure(st)
    st = hazus_flood(st)
    st = hazus_eq(st)
    wind_tract(st)
    keep = ["fd_id", "x", "y", "occtype", "occ_base", "bldgtype", "num_story", "med_yr_blt", "val_struct", "val_cont", "value_total", "pop_night", "jurisdiction", "tract", "svi", "zclass", "bfe", "ffe_ft",
            "post_firm", "ffe_adj", "depth_ft", "flood_bldg_ratio", "flood_loss", "flood_loss_slr2", "pga_g", "mmi", "eq_btype", "eq_design", "eq_loss", "eq_ratio", "p_ext_or_comp"]
    st[keep].to_parquet(PROC / "structures_results.parquet")
    with pd.ExcelWriter(TAB / "charleston_risk_assessment_tables.xlsx") as xw:
        idx = pd.DataFrame([(k, n) for k, (_, n) in TABLES.items()], columns=["table", "description"])
        idx.to_excel(xw, sheet_name="index", index=False)
        for k, (df, _) in TABLES.items():
            df.to_excel(xw, sheet_name=k[:31], index=False)
    (TAB / "table_notes.json").write_text(json.dumps({k: n for k, (_, n) in TABLES.items()}, indent=1))
    for k in ("17_hazus_flood_scenarios", "21_hazus_eq_summary"):
        print(TABLES[k][0].T.to_string())


if __name__ == "__main__":
    main()
