# Tanzania sophisticated accessibility pipeline

This subfolder holds the higher-fidelity population + access analysis for
Tanzania, adapted from the R scripts you had in
`hf-data-portal/population and access tab/`. It sits alongside — not
in place of — the simpler 8-country pipeline in the parent
`scripts/population/` folder.

Why a Tanzania-only subfolder?

- Uses **WorldPop 2026 constrained at 100 m** (much higher fidelity than
  the 2020 1 km unconstrained the parent pipeline uses).
- Uses a **modelled travel-time-to-facility surface** rather than a
  simple distance-to-road classification.
- Uses **Voronoi catchments** (non-overlapping, exhaustive) rather than
  radial 5/10 km buffers (overlap, double-count).
- Consumes country-specific inputs (WDPA shapefiles, admin boundaries,
  the travel-time raster) that would need to be produced separately per
  country to scale.

## Raw inputs — you drop these once

All under `data/population/raw/tanzania/` (gitignored — files are large):

```
data/population/raw/tanzania/
├── travel_time_100m.tif           # rename of your tt_b4.tif (~660 MB)
├── worldpop_2026_100m.tif         # rename of tza_pop_2026_CN_100m_R2025A_v1.tif (~140 MB)
├── districts/
│   ├── District_TZ_wgs84.shp
│   ├── District_TZ_wgs84.dbf
│   ├── District_TZ_wgs84.shx
│   └── District_TZ_wgs84.prj
└── wdpa/
    ├── wdpa_0/
    │   └── WDPA_WDOECM_May2026_Public_TZA_shp-polygons.{shp,dbf,shx,prj,cpg}
    └── wdpa_1/
        └── WDPA_WDOECM_May2026_Public_TZA_shp-polygons.{shp,dbf,shx,prj,cpg}
```

Quick copy from the source-repo folder (adjust the source path if you moved it):

```powershell
$src = "F:\AFTER UNIVERSITY PERIOD\IFAKARA HEALTH INSTITUTE\MAP PROJECT\QUARTO PROJECTS\hf-data-portal\population and access tab"
$dst = "F:\AFTER UNIVERSITY PERIOD\IFAKARA HEALTH INSTITUTE\MAP PROJECT\QUARTO PROJECTS\healthscope-portal\data\population\raw\tanzania"

New-Item -ItemType Directory -Path "$dst\districts", "$dst\wdpa\wdpa_0", "$dst\wdpa\wdpa_1" -Force | Out-Null

Copy-Item "$src\tt_b4.tif"                             "$dst\travel_time_100m.tif"
Copy-Item "$src\tza_pop_2026_CN_100m_R2025A_v1.tif"    "$dst\worldpop_2026_100m.tif"
Copy-Item "$src\Tanzania_shapefile_district\*"         "$dst\districts\"
Copy-Item "$src\wdpa_0\wdpa_0\*"                       "$dst\wdpa\wdpa_0\"
Copy-Item "$src\wdpa_1\wdpa_1\*"                       "$dst\wdpa\wdpa_1\"
```

## Running the pipeline

From the deploy clone root, in any order (they don't depend on each other):

```powershell
$R = "C:\Program Files\R\R-4.6.0\bin\Rscript.exe"

& $R scripts/population/tanzania/10_wdpa_mask.R
& $R scripts/population/tanzania/11_travel_time_bands.R
& $R scripts/population/tanzania/12_voronoi_catchments.R
```

## Outputs (all go into `data/population/processed/`)

| Script | Files produced | Purpose |
| ------ | -------------- | ------- |
| 10 | `tanzania_wdpa_strict.geojson` | Strict-category protected areas for optional map overlay |
| 11 | `tanzania_access_summary.csv` | National population per travel-time band (4 rows) |
| 11 | `tanzania_district_burden.csv` | Per-district pop total + pop >60 min, ranked worst-first |
| 11 | `tanzania_travel_time_bands.geojson` | Polygonised bands for map choropleth |
| 11 | `tanzania_travel_time_categories.tif` | Compact INT1U categorical raster (QA / re-use) |
| 12 | `tanzania_catchments_voronoi.csv` | Per-facility Voronoi catchment (replaces radial for Tanzania) |
| 12 | `tanzania_voronoi_polygons.geojson` | Voronoi polygon layer for map choropleth |

Portal integration is a separate PR — none of these outputs are wired
into `population-access.qmd` yet. When they are, the plan is:

- **Sub-obj #2 (Catchment)**: Tanzania loads Voronoi CSV + polygons; other
  countries stay on radial catchments until they get the same treatment.
- **Sub-obj #3 (Reachability)**: Tanzania shows the 4 travel-time bands +
  the district burden table; other countries stay on the simpler OSM
  road-distance classification.
- **Sub-obj #4 (Underserved zones)** becomes computable for Tanzania as
  the intersection of ">60 min" AND "population > threshold" per district
  — the district_burden.csv already ranks this.

## Scaling to the other 7 countries

Each of the three input data types would need to be produced per country:

1. **Travel-time raster** — the heavy one. The `tt_b4.tif` was produced
   by a separate modelling pipeline (probably `AccessMod` or a friction-
   surface approach with `gdistance`); porting that to each country is a
   real project.
2. **Constrained WorldPop 100 m** — downloadable per country from
   `data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/`.
3. **WDPA + admin boundaries** — WDPA has per-country downloads; admin
   boundaries come from national statistics offices or GADM.

Once those exist, generalise scripts 11 and 12 to a country-slug loop.
