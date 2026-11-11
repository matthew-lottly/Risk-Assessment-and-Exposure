"""Hazus building loss for flood and earthquake, structure by structure.

The damage and loss functions are FEMA Hazus tables as published in machine-readable form by the NHERI SimCenter Damage and Loss Model Library
(data/reference/hazus, BSD-3 licence): flood depth-damage functions from Hazus Flood v6.1, earthquake equivalent-PGA fragilities and repair-cost ratios
from the Hazus Earthquake Technical Manual v6.1. This module applies them to a structure inventory; it is not the Hazus desktop software.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REF = Path(__file__).resolve().parents[2] / "data" / "reference" / "hazus"


# ------------------------------------------------------------------ flood
def load_ddfs():
    """{id: (depths_ft, loss_ratios)} for every Hazus flood depth-damage function, with its description."""
    t = pd.read_csv(REF / "flood_loss_repair.csv")
    out = {}
    for _, r in t.iterrows():
        ratios, depths = r["LossFunction-Theta_0"].split("|")
        out[r["ID"].replace("-Cost", "")] = (np.array([float(v) for v in depths.split(",")]), np.array([float(v) for v in ratios.split(",")]))
    return out


# the curve each occupancy uses: an exact Hazus id prefix by occupancy (RES1 and RES2 are resolved per structure below)
OCC_STRUCT = {"RES3": "structural.206.", "RES4": "structural.209.", "RES5": "structural.214.", "RES6": "structural.215.", "COM1": "structural.217.", "COM2": "structural.341.",
              "COM3": "structural.375.", "COM4": "structural.431.", "COM5": "structural.467.", "COM6": "structural.474.", "COM7": "structural.475.", "COM8": "structural.493.",
              "COM9": "structural.532.", "COM10": "structural.543.", "IND1": "structural.545.", "IND2": "structural.559.", "IND3": "structural.575.", "IND4": "structural.586.",
              "IND5": "structural.591.", "IND6": "structural.592.", "AGR1": "structural.616.", "REL1": "structural.624.", "GOV1": "structural.631.", "GOV2": "structural.640.",
              "EDU1": "structural.643.", "EDU2": "structural.652."}
OCC_CONT = {"RES4": "contents.085.", "RES5": "contents.088.", "COM1": "contents.090.", "COM2": "contents.195.", "COM3": "contents.240.", "COM4": "contents.280.",
            "COM7": "contents.312.", "COM8": "contents.322.", "IND1": "contents.358.", "IND2": "contents.384.", "IND3": "contents.408.", "IND4": "contents.433.",
            "IND5": "contents.442.", "IND6": "contents.443.", "AGR1": "contents.460.", "GOV1": "contents.472.", "GOV2": "contents.477.", "EDU1": "contents.480.", "EDU2": "contents.485."}
# occupancies with no Galveston "average" contents curve fall back to the closest one (stated in the method notes)
CONT_FALLBACK = {"RES3": "RES4", "RES6": "RES5", "COM5": "COM4", "COM6": "COM7", "COM9": "COM8", "COM10": "COM2", "REL1": "GOV1"}


def ddf_ids(occ_base, stories, basement, vzone, kind):
    """Hazus curve id for one structure. RES1: FIA curves by floors, basement and A/V zone; RES2: FIA mobile home by zone; others: USACE Galveston averages."""
    z = "v_zone" if vzone else "a_zone"
    if occ_base == "RES1":
        fl = "one_floor" if stories <= 1 else ("two_floors" if stories == 2 else "three_or_more_floors")
        b = "with_basement" if basement else "no_basement"
        num = {("structural", "one_floor", "no_basement", "a_zone"): 105, ("structural", "two_floors", "no_basement", "a_zone"): 107, ("structural", "three_or_more_floors", "no_basement", "a_zone"): 109,
               ("structural", "one_floor", "no_basement", "v_zone"): 113, ("structural", "two_floors", "no_basement", "v_zone"): 115, ("structural", "three_or_more_floors", "no_basement", "v_zone"): 117,
               ("structural", "one_floor", "with_basement", "a_zone"): 121, ("structural", "two_floors", "with_basement", "a_zone"): 122, ("structural", "three_or_more_floors", "with_basement", "a_zone"): 123,
               ("structural", "one_floor", "with_basement", "v_zone"): 125, ("structural", "two_floors", "with_basement", "v_zone"): 126, ("structural", "three_or_more_floors", "with_basement", "v_zone"): 127}
        if kind == "structural":
            return f"structural.{num[('structural', fl, b, z)]}."
        # contents: FIA one-floor / two-floor curves (no three-floor contents curve in the table: two floors is used)
        cfl = "one_floor" if stories <= 1 else "two_floors"
        cmap = {("one_floor", "no_basement", "a_zone"): "021", ("one_floor", "with_basement", "a_zone"): "022", ("two_floors", "no_basement", "a_zone"): "023",
                ("one_floor", "no_basement", "v_zone"): "029", ("one_floor", "with_basement", "v_zone"): "030", ("two_floors", "no_basement", "v_zone"): "031"}
        return f"contents.{cmap.get((cfl, b, z), cmap[(cfl, 'no_basement', z)])}."
    if occ_base == "RES2":
        return ("structural.190." if vzone else "structural.189.") if kind == "structural" else ("contents.075." if vzone else "contents.074.")
    if kind == "structural":
        return OCC_STRUCT.get(occ_base, "structural.217.")
    return OCC_CONT.get(occ_base, OCC_CONT.get(CONT_FALLBACK.get(occ_base, "COM1"), "contents.090."))


def flood_loss(inv, depth_ft, ddfs=None):
    """inv: DataFrame with occ_base, stories, basement, vzone, val_struct, val_cont. depth_ft: depth of water above the first floor (NaN = not flooded).
    Returns DataFrame of building and contents loss ratios and dollars, and the curve ids used."""
    ddfs = ddfs or load_ddfs()
    by_prefix = {}
    for k in ddfs:
        m = re.match(r"(structural|contents)\.(\d+)\.", k)
        if m is None:
            continue
        by_prefix.setdefault(f"{m.group(1)}.{m.group(2)}.", k)
    n = len(inv)
    out = pd.DataFrame(index=inv.index)
    for kind, val in (("structural", "val_struct"), ("contents", "val_cont")):
        ids = [ddf_ids(o, s, b, v, kind) for o, s, b, v in zip(inv.occ_base, inv.stories, inv.basement, inv.vzone)]
        lr = np.zeros(n)
        d = np.asarray(depth_ft, float)
        ids_s = pd.Series(ids, index=inv.index)
        for pre, idx in ids_s.groupby(ids_s).groups.items():
            key = by_prefix[pre]
            xs, ys = ddfs[key]
            pos = inv.index.get_indexer(idx)
            dd = d[pos]
            ok = np.isfinite(dd)
            r = np.zeros(len(pos))
            # below the lowest tabulated depth: no loss; above the highest: the last ratio
            r[ok] = np.interp(dd[ok], xs, ys, left=0.0, right=ys[-1])
            lr[pos] = r
        lr = np.where(np.isfinite(d), lr, 0.0)
        out[f"{kind}_ratio"] = lr
        out[f"{kind}_loss"] = lr * inv[val].to_numpy(float)
        out[f"{kind}_ddf"] = [by_prefix[p] for p in ids]
    out["total_loss"] = out.structural_loss + out.contents_loss
    return out


# ------------------------------------------------------------------ earthquake
DESIGN_CODE = {"Pre-Code": "PC", "Low-Code": "LC", "Moderate-Code": "MC", "High-Code": "HC"}


def eq_building_type(bldgtype, occ_base, stories, year):
    """Hazus model building type and height class from the NSI's general type (W, M, C, S, H), stories and year (assumptions stated in the report)."""
    h = "L" if stories <= 3 else ("M" if stories <= 7 else "H")
    if bldgtype == "H" or occ_base == "RES2":
        return "MH", None
    if bldgtype == "W":
        return ("W1", None) if occ_base.startswith("RES") and stories <= 3 else ("W2", None)
    if bldgtype == "M":
        if year < 1975:
            return "URM", ("L" if stories <= 2 else "M")
        return "RM1", ("L" if stories <= 3 else "M")
    if bldgtype == "C":
        return "C2" if stories >= 4 else "C1", h
    if bldgtype == "S":
        return ("S3", None) if stories <= 1 and not occ_base.startswith("RES") else ("S1", h)
    return "W1", None


def design_level(year, btype):
    """Seismic design level by year built for Charleston County: before 1975 Pre-Code, 1975 to 1999 Low-Code, 2000 on Moderate-Code
    (Standard Building Code seismic provisions, then the IBC). Unreinforced masonry is Pre- or Low-Code only."""
    lvl = "Pre-Code" if year < 1975 else ("Low-Code" if year < 2000 else "Moderate-Code")
    if btype in ("URM", "S5", "C3") and lvl == "Moderate-Code":
        lvl = "Low-Code"
    return lvl


def load_eq():
    f = pd.read_csv(REF / "seismic_fragility.csv").set_index("ID")
    c = pd.read_csv(REF / "seismic_consequence_repair.csv").set_index("ID")
    return f, c


def eq_damage(inv, pga_g, frag=None, cons=None):
    """Probability of each Hazus damage state (none, slight, moderate, extensive, complete) from equivalent-PGA fragility curves, and building repair loss
    as the expected Hazus lifeline-facility loss ratio times structure value. inv: DataFrame with btype, hclass, design, occ_base, val_struct."""
    if frag is None:
        frag, cons = load_eq()
    n = len(inv)
    P = np.zeros((n, 5))
    fid = []
    pga = np.asarray(pga_g, float)
    for i, (bt, hc, dl) in enumerate(zip(inv.btype, inv.hclass, inv.design)):
        code = DESIGN_CODE[dl]
        hc = hc if isinstance(hc, str) else None
        key = f"LF.{bt}.{hc}.{code}" if hc else f"LF.{bt}.{code}"
        if key not in frag.index:
            # fall back one design level down, then to Pre-Code
            for alt in ("LC", "PC"):
                k2 = f"LF.{bt}.{hc}.{alt}" if hc else f"LF.{bt}.{alt}"
                if k2 in frag.index:
                    key = k2
                    break
        fid.append(key)
    fid = np.array(fid)
    for key in np.unique(fid):
        r = frag.loc[key]
        idx = np.flatnonzero(fid == key)
        x = np.maximum(pga[idx], 1e-6)
        ex = np.column_stack([norm.cdf(np.log(x / r[f"LS{k}-Theta_0"]) / r[f"LS{k}-Theta_1"]) for k in range(1, 5)])
        P[idx, 0] = 1 - ex[:, 0]
        P[idx, 1] = ex[:, 0] - ex[:, 1]
        P[idx, 2] = ex[:, 1] - ex[:, 2]
        P[idx, 3] = ex[:, 2] - ex[:, 3]
        P[idx, 4] = ex[:, 3]
    ratio = np.zeros(n)
    for occ, idx in pd.Series(np.arange(n), index=inv.occ_base.values).groupby(level=0):
        key = f"LF.{occ}-Cost"
        if key not in cons.index:
            key = "LF.COM1-Cost"
        lr = cons.loc[key, ["DS1-Theta_0", "DS2-Theta_0", "DS3-Theta_0", "DS4-Theta_0"]].to_numpy(float)
        ratio[idx.values] = P[idx.values, 1:] @ lr
    out = pd.DataFrame(P, columns=["p_none", "p_slight", "p_moderate", "p_extensive", "p_complete"], index=inv.index)
    out["fragility_id"] = fid
    out["loss_ratio"] = ratio
    out["building_loss"] = ratio * inv.val_struct.to_numpy(float)
    return out
