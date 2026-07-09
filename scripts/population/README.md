# Population catchment pipeline (Milestone A — sub-objective 2)

Produces, for every facility in every country, the population count within a
5 km and 10 km radius. The output CSVs are read directly by the portal's
Population and Access page (`population-access.qmd`).

## Output shape

One `data/population/processed/<country>_catchments.csv` per country:

| column         | example        | notes                                    |
| -------------- | -------------- | ---------------------------------------- |
| facility_code  | TZA-001        | Stable ETL uid                           |
| facility_name  | Muhimbili …    |                                          |
| admin1         | Dar es Salaam  |                                          |
| admin2         | Kinondoni      |                                          |
| facility_type  | Regional Hosp. |                                          |
| latitude       | -6.8006        | WGS84                                    |
| longitude      | 39.2650        |                                          |
| pop_5km        | 284320         | Sum of WorldPop 2020 within 5 km buffer  |
| pop_10km       | 891450         | Sum of WorldPop 2020 within 10 km buffer |

## Prerequisites

R 4.2+ with these packages:

```r
install.packages(c("sf", "terra", "exactextractr",
                   "readr", "dplyr", "httr", "purrr"))
```

WorldPop rasters (~40-100 MB per country) are **not** committed; the
`00_download_worldpop.R` step fetches them into
`data/population/raw/` (gitignored).

## Running the pipeline

From the repository root, in this order:

```powershell
# 1. Download WorldPop 2020 1 km rasters for all 8 countries
Rscript scripts/population/00_download_worldpop.R

# 2. Compute per-facility catchments (writes 8 CSVs into data/population/processed/)
Rscript scripts/population/01_catchment_extract.R
```

Runtime, rough:

- Step 1: 5–15 min depending on your network (WorldPop is ~350 MB total).
- Step 2: 2–5 min per country on a laptop. Nigeria and Ethiopia are the slow
  ones because they have the most facilities.

To rerun only one country, pass the country slug:

```powershell
Rscript scripts/population/01_catchment_extract.R tanzania
```

## After running

The 8 CSVs in `data/population/processed/` are committed and served by Quarto
(they're listed in `_quarto.yml` under `resources:`). Re-render + push:

```powershell
.\render.ps1 population-access.qmd
git add data/population/processed _quarto.yml docs/population-access.html docs/search.json docs/sitemap.xml
git commit -m "Population catchment CSVs: initial run"
git push origin main
```

## Method notes

- **Buffers are computed in Africa Albers Equal-Area Conic (ESRI:102022)**
  so the 5 / 10 km distance is accurate to sub-meter across every country
  in the portal, including those that span multiple UTM zones (Nigeria,
  Ethiopia).
- **Population raster is WorldPop unconstrained 2020, 1 km resolution**
  (`Global_2000_2020/2020/<ISO3>/<iso3>_ppp_2020_1km_Aggregated.tif`).
  Unconstrained means every populated cell is estimated even where no
  building footprints have been mapped — better recall for rural areas.
- **`exact_extract` with `sum`** uses fractional cell coverage at buffer
  boundaries, so a cell straddling the edge contributes proportionally
  rather than all-or-nothing.
- **Facilities without valid coordinates are excluded.** They keep no row
  in the catchment CSV — the portal treats them as "no catchment data
  available".

## Refreshing later

WorldPop 2020 is the current baseline. When a newer year is available,
change the `WORLDPOP_YEAR` constant in `01_catchment_extract.R`, re-run
step 1 (it will download the new rasters), then re-run step 2.
