# scripts/population/tanzania/11_travel_time_bands.R
#
# Aligns the 100 m modelled travel-time-to-facility raster onto the 100 m
# constrained WorldPop 2026 raster, classifies travel time into 4 bands
# (0-30, 30-60, 60-90, >90 min), and produces:
#
#   Portal-ready outputs (data/population/processed/):
#     tanzania_access_summary.csv        pop per band + %
#     tanzania_district_burden.csv       per-district pop total + pop >60min + %
#     tanzania_travel_time_bands.geojson polygonised bands for map overlay
#
# Method notes:
#   - Population is a COUNT — never interpolate. TT is a continuous surface —
#     safe to bilinear-resample onto the population grid.
#   - `zonal()` cross-tabulation is used instead of as.data.frame(raster) to
#     stay memory-safe on national 100 m rasters.
#   - Districts are rasterised onto the pop grid, then zonal() by district ID.
#
# Adapted from population and access tab/pop_access.R.
#
# Memory notes for Windows R:
#   - OpenBLAS defaults to using all CPU threads, each with its own scratch
#     memory. On a 100 m national raster that pushes R past the working-set
#     ceiling. Setting *_NUM_THREADS=1 before load cuts scratch dramatically.
#   - GDAL keeps a raster block cache; the default (~40 MB) is too small for
#     ~1 GB rasters and causes "cannot allocate N bytes (GDAL error 2)".
#     Bumped to 1 GB — still safe on 8 GB laptops because it's a cap.
#   - terraOptions(memfrac=0.5, todisk=TRUE) tells terra to write any
#     intermediate raster it would otherwise hold in memory to a temp file.
#   - AGG_FACT below aggregates both input rasters before any heavy op.
#     100 m -> 300 m reduces working set 9x while keeping population counts
#     exact (sum aggregation) and travel-time surface functionally unchanged
#     for the coarse 30/60/90-min classification.
Sys.setenv(OPENBLAS_NUM_THREADS = "1",
           OMP_NUM_THREADS      = "1",
           GDAL_CACHEMAX        = "1024")

suppressPackageStartupMessages({
  library(terra)
  library(sf)
  library(dplyr)
  library(readr)
})

terraOptions(memfrac = 0.5, todisk = TRUE, tempdir = tempdir())

AGG_FACT <- 3   # 100 m -> 300 m. Bump to 5 (500 m) if this still OOMs.

RAW_DIR <- "data/population/raw/tanzania"
OUT_DIR <- "data/population/processed"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

TT_TIF        <- file.path(RAW_DIR, "travel_time_100m.tif")
POP_TIF       <- file.path(RAW_DIR, "worldpop_2026_100m.tif")
DISTRICT_SHP  <- file.path(RAW_DIR, "districts", "District_TZ_wgs84.shp")
DISTRICT_COL  <- "District_N"   # attribute column holding the district name

for (p in c(TT_TIF, POP_TIF, DISTRICT_SHP)) {
  if (!file.exists(p)) stop("Missing input: ", p,
                            "\nDrop it into data/population/raw/tanzania/")
}

# ---- load ------------------------------------------------------------------
message("Loading rasters + districts...")
tt_raw      <- rast(TT_TIF)
pop_raw     <- rast(POP_TIF)
tz_district <- st_read(DISTRICT_SHP, quiet = TRUE)

# ---- pre-aggregate for memory safety --------------------------------------
# Population: sum aggregation preserves totals EXACTLY.
# Travel time: mean aggregation is fine for a smooth continuous surface at
# the coarseness of the 30/60/90-minute bands.
message(sprintf("Aggregating rasters by factor %d (%d m -> %d m)...",
                AGG_FACT, round(res(pop_raw)[1] * 100000), # ugly but close
                round(res(pop_raw)[1] * 100000 * AGG_FACT)))
pop <- aggregate(pop_raw, fact = AGG_FACT, fun = "sum",  na.rm = TRUE)
tt  <- aggregate(tt_raw,  fact = AGG_FACT, fun = "mean", na.rm = TRUE)
rm(pop_raw, tt_raw); gc()

# ---- align travel time onto the (aggregated) population grid --------------
pop_total <- global(pop, "sum", na.rm = TRUE)[[1]]
tt <- project(tt, pop, method = "bilinear")
message(sprintf("National population (aggregated WorldPop 2026): %s",
                format(round(pop_total), big.mark = ",")))
gc()

# ---- 4 travel-time bands ---------------------------------------------------
access_class <- classify(tt, rbind(
  c(-Inf, 30,  1),
  c(30,   60,  2),
  c(60,   90,  3),
  c(90,   Inf, 4)
))
names(access_class) <- "access"
rm(tt); gc()          # tt no longer needed — free it before the heavier steps

# ---- national pop per band ------------------------------------------------
band_pop <- zonal(pop, access_class, fun = "sum", na.rm = TRUE)
names(band_pop) <- c("access", "population")
BAND_LABELS <- c("0-30 minutes", "30-60 minutes", "60-90 minutes", ">90 minutes")
band_pop <- band_pop |>
  mutate(access_band = BAND_LABELS[access],
         pct = round(100 * population / sum(population), 2),
         population = round(population)) |>
  select(access, access_band, population, pct)
print(band_pop)

write_csv(band_pop, file.path(OUT_DIR, "tanzania_access_summary.csv"))

# ---- district-level burden ------------------------------------------------
message("Rasterising districts onto pop grid...")
tz_district <- st_transform(tz_district, crs(pop))
dist_r <- rasterize(vect(tz_district), pop, field = DISTRICT_COL)
gc()

dist_pop     <- zonal(pop, dist_r, fun = "sum", na.rm = TRUE)
names(dist_pop) <- c("district", "pop_total")
gc()

pop_over60  <- ifel(access_class >= 3, pop, 0)   # bands 3 and 4 = beyond 60 min
dist_over60 <- zonal(pop_over60, dist_r, fun = "sum", na.rm = TRUE)
names(dist_over60) <- c("district", "pop_over60")
rm(pop_over60, dist_r); gc()

district_burden <- dist_pop |>
  left_join(dist_over60, by = "district") |>
  mutate(pop_total  = round(pop_total),
         pop_over60 = round(pop_over60),
         pct_over60 = round(100 * pop_over60 / pop_total, 2)) |>
  arrange(desc(pop_over60))

write_csv(district_burden, file.path(OUT_DIR, "tanzania_district_burden.csv"))
message(sprintf("Wrote district burden table: %d districts, worst = %s (%d over 60 min)",
                nrow(district_burden),
                district_burden$district[1],
                district_burden$pop_over60[1]))

# ---- polygonise bands for the portal overlay ------------------------------
# INT1U categorical raster -> polygons per band (dissolve identical values).
# Much smaller than the raster + renderable with plain leaflet.
message("Polygonising travel-time bands...")
bands_poly <- as.polygons(access_class, dissolve = TRUE) |>
  st_as_sf() |>
  rename(band = access) |>
  mutate(band_label = BAND_LABELS[band]) |>
  st_transform(4326)

BANDS_OUT <- file.path(OUT_DIR, "tanzania_travel_time_bands.geojson")
if (file.exists(BANDS_OUT)) file.remove(BANDS_OUT)
st_write(bands_poly, BANDS_OUT, driver = "GeoJSON",
         layer_options = c("COORDINATE_PRECISION=5", "WRITE_BBOX=NO"),
         quiet = TRUE)
message(sprintf("Wrote %s (%.0f KB)",
                BANDS_OUT, file.info(BANDS_OUT)$size / 1024))

# ---- also save the compact categorical raster (INT1U) for reproducibility -
# Not read by the portal directly (browsers can't render GeoTIFF without a
# raster plugin), but useful for anyone re-running or QA.
TT_CAT_OUT <- file.path(OUT_DIR, "tanzania_travel_time_categories.tif")
writeRaster(access_class, TT_CAT_OUT, overwrite = TRUE, datatype = "INT1U")
message(sprintf("Wrote %s (%.1f MB)",
                TT_CAT_OUT, file.info(TT_CAT_OUT)$size / 1e6))
