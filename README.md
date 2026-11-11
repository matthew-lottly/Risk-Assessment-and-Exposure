# Risk Assessment and Exposure: Charleston County, South Carolina

A hazard mitigation plan (HMP) risk assessment for Charleston County, SC, built entirely from public data:
hazard identification and ranking, hazard history, exposure tables for every structure in the county, and Hazus
loss estimates for a 1% annual chance flood (with sea-level rise) and a repeat of the 1886 Charleston earthquake.
It is laid out to support the risk-assessment section of a FEMA-approvable plan (44 CFR 201.6(c)(2)): hazard
descriptions, location and extent, previous occurrences, probability, vulnerability, NFIP repetitive-loss
properties and impacts by jurisdiction.

**Why Charleston County.** It is the highest-risk county in South Carolina on FEMA's National Risk Index (composite
score 98.6, rank 1 of 46), and it carries every major hazard type a plan has to address: hurricanes,
storm surge and tidal flooding, rainfall flooding, sea-level rise, and the largest historical earthquake in the
southeastern US (1886). Its current multi-jurisdictional plan was approved 2024-03-20 and expires 2029-03-19
(OpenFEMA), so this is the analysis its next update needs.

## Headline results

| Measure | Result | Table |
|---|---|---|
| Expected annual loss, all hazards (NRI, Dec 2025) | **$500 M per year**: hurricane $281 M (62%), earthquake $118 M (26%), coastal flooding $36 M (8%) | 01 |
| Structures (USACE NSI) | 166,665; $89.7 B structure value, $63.5 B contents | 12 |
| In the special flood hazard area (A + VE) | **47,385 structures (28%)**, $47.3 B structure and contents value, 113,016 night-time residents | 13 |
| Hazus 1% annual chance flood | **$3.4 B** (building $1.1 B, contents $2.3 B); 7,644 structures with water above the first floor | 17 |
| Same flood with +1 / +2 / +3 ft sea-level rise | $4.4 B / $7.3 B / $9.7 B (lower bounds, see limits) | 17 |
| Hazus 1886 earthquake (M7.0 ShakeMap, median PGA 0.59 g at structures) | **$39 B** building loss (44% of value); about 80,000 structures extensively or completely damaged; sensitivity range $28 B to $47 B | 21, 21b |
| NFIP history | 19,289 claims, $312 M paid since 1978; 1,296 multiple-loss properties (177 severe repetitive loss, 45 mitigated) | 05, 08 |
| Disaster declarations | 27 FEMA declarations designating the county (hurricanes most often) | 03 |

## Maps and figures (`outputs/maps/`)

| Plate | Content |
|---|---|
| 01 | Planning area: jurisdictions, structures, structures by jurisdiction |
| 02 | National Risk Index composite risk by census tract; expected annual loss by hazard |
| 03 | NRI expected annual loss by tract for the six largest hazards |
| 04 | Hazard history: declarations timeline, NOAA storm damage by type, NFIP claims by year, largest flood events |
| 05 | FEMA flood zones and exposed structures; SFHA structures by jurisdiction |
| 06 | Hazus 1% annual chance flood loss (1 km hexagons) and loss by jurisdiction |
| 07 | Sea-level rise: added loss with 2 ft of rise; loss by scenario |
| 08 | 1886 earthquake ShakeMap (PGA, MMI contours); structures by intensity |
| 09 | Hazus earthquake loss (1 km hexagons), damage states and sensitivity |
| 10 | Social vulnerability (CDC SVI) with the SFHA; high-SVI tracts with the largest flood loss |
| 11 | NFIP payments by tract and repetitive-loss properties by community |
| 12 | Model check: first-floor elevations against NFIP elevation-certificate data |

## Tables (`outputs/tables/`)

All tables are CSV, and all are also in one workbook, `charleston_risk_assessment_tables.xlsx`, with an index
sheet describing each. `table_notes.json` holds the same descriptions.

01 NRI hazard ranking · 02 NRI ranking of SC counties · 03 disaster declarations · 04 storm events by type ·
05 NFIP claims by year · 06 NFIP claims by flood zone · 07 largest NFIP flood events · 08 repetitive loss by
community · 09 earthquakes M3+ within 200 km · 10 HMA subapplications · 11 plan status · 12 building inventory ·
13 flood exposure by jurisdiction · 14 flood exposure by occupancy · 15 critical facilities in flood zones ·
16 social vulnerability and flood exposure · 17 Hazus flood scenarios · 18 Hazus flood loss by jurisdiction ·
19 by occupancy · 20 Hazus flood curves used · 21 Hazus earthquake summary · 21b earthquake sensitivity ·
22 earthquake by jurisdiction · 23 earthquake by building type · 24 shaking exposure · 25 tract risk profile ·
26 first-floor elevation check · 27 NFIP community status and CRS class

## Methods

**Data** (`scripts/fetch_data.py`): FEMA National Risk Index (tract and county feature services, Dec 2025);
FEMA National Flood Hazard Layer flood zones (FIRMs effective 2021-01-29); USACE National Structure Inventory
(every structure with occupancy, construction type, stories, foundation, ground elevation, value and population);
OpenFEMA disaster declarations, NFIP redacted claims, NFIP multiple-loss properties, community status book, HMA
subapplications and plan status; NOAA NCEI Storm Events 1996 to 2026; USGS ComCat earthquakes and the ShakeMap
for the 1886 event (`ushis251`); CDC/ATSDR SVI 2022; Census TIGER/Line 2023 and cartographic boundaries.

**Exposure** (`scripts/prepare.py`, `scripts/run_analysis.py`): each structure is placed in the effective flood
zone by this study's own overlay of the NFHL. It agrees with the NSI's own flood-zone attribute for 99.1% of
structures. Each structure also gets a jurisdiction (incorporated places), census tract, SVI and ShakeMap
intensity. Critical facilities are identified from NSI occupancy classes.

**Hazus damage functions**: the FEMA Hazus tables, as published in machine-readable form by the NHERI SimCenter
Damage and Loss Model Library (`data/reference/hazus`, BSD-3 licence): Hazus Flood v6.1 depth-damage functions
and Hazus Earthquake v6.1 fragility and repair-cost tables. `src/riskx/hazus.py` applies them structure by
structure. This is the Hazus methodology and its tables, not a run of the Hazus desktop software.

**Flood**: depth of water above the first floor = base flood elevation (from the FIRM) minus the first-floor
elevation. Curves: FIA curves for single-family homes (by floors, basement, A or V zone), FIA mobile-home curves,
and USACE Galveston "average" curves for other occupancies. The first-floor elevation needed a correction, which
plate 12 shows:
- The NSI's default foundation heights put 68% of A-zone buildings below the BFE.
- NFIP elevation-rated buildings in the county show 10%.
- Every community here entered the NFIP with a 1971 FIRM, so buildings from 1975 on are taken to meet the
  ordinance: first floor at today's BFE plus the 2.0 ft median freeboard measured on 6,377 post-FIRM rated NFIP
  buildings.

That puts 16% below the BFE, and it is the central estimate. The NSI-default result ($8.1 B) is kept as an upper
bound.

**Earthquake**: the 1886 ShakeMap PGA at each structure drives the Hazus equivalent-PGA fragility curves. Model
building type comes from the NSI construction class, stories and year. Design level comes from year built: Pre-Code
before 1975, Low-Code 1975 to 1999, Moderate-Code from 2000. Expected repair loss uses the Hazus damage-state loss
ratios. Sensitivity (table 21b): one design level higher gives $28 B, and PGA scaled by 0.8 or 1.2 gives $30 B or
$47 B.

## Limits (read before using the numbers)

- **Hurricane wind has no Hazus run.** It needs a wind field (for example a Hugo reconstruction from NOAA HURDAT2)
  and roof, wall and opening attributes the NSI does not carry. The NRI hurricane expected annual loss is used
  instead. This is the obvious next step.
- **Flood.** BFEs exist only in mapped A and VE zones with elevations. The sea-level-rise scenarios add the rise
  only inside today's SFHA, so they undercount: about 41,000 structures sit in today's 0.2% zone. The NSI year
  built is a block-group median, not each building's own year. Hazus curves give some loss when water is just
  below the first floor; that is why "structures damaged" jumps at +2 ft, where post-FIRM freeboard is used up.
- **Earthquake.** The equivalent-PGA curves are Hazus's simplified method (the full method uses capacity spectra).
  The loss is building repair only: no contents, casualties, debris, lifelines or liquefaction. The 1886 ShakeMap
  is inferred from felt reports. The building types and design levels are assumptions from coarse NSI attributes.
  Treat the result as an order of magnitude, with the sensitivity range as the honest spread.
- **Values and dates.** NSI values are replacement-cost estimates, not market or tax values. Storm Events and NFIP
  dollars are nominal and not inflation-adjusted.
- These products are for planning. They are not regulatory flood determinations.

## Reproduce

```bash
python scripts/fetch_data.py all      # about 520 MB into data/raw (git-ignored)
python scripts/prepare.py             # data/processed/structures.parquet, county.gpkg
python scripts/run_analysis.py        # outputs/tables
python scripts/make_maps.py all       # outputs/maps
```
Python 3.10+ with geopandas, pandas, numpy, scipy, matplotlib, requests, pyarrow and openpyxl.
