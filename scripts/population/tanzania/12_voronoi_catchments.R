# scripts/population/tanzania/12_voronoi_catchments.R
#
# Voronoi (nearest-facility) catchments for Tanzania. For every facility,
# the catchment polygon is the region of space closer to it than to any
# other facility, clipped to the country boundary. Population is summed
# inside each polygon.
#
# Voronoi is the honest alternative to my radial 5/10 km buffers on
# population-access.qmd — the buffers overlap between neighbouring
# facilities and double-count people, while Voronoi tiles the country
# with no overlap and no gaps.
#
# Outputs (data/population/processed/):
#   tanzania_catchments_voronoi.csv       one row per facility with
#                                          catchment_population + category
#   tanzania_voronoi_polygons.geojson     the polygon layer for the map
#
# Inputs:
#   etl/data/processed/country_standardized/tanzania_standardized.csv
#   data/population/raw/tanzania/worldpop_2026_100m.tif
#   data/population/raw/tanzania/districts/District_TZ_wgs84.shp
#
# Adapted from population and access tab/catchment_pop.R.
#
# Memory: capping BLAS threads, bumping GDAL cache, and simplifying the
# country boundary before st_intersection — the ~11k Voronoi polygons vs
# a fully-detailed multi-polygon country cutter blows GEOS heap allocation.
Sys.setenv(OPENBLAS_NUM_THREADS = "1",
           OMP_NUM_THREADS      = "1",
           GDAL_CACHEMAX        = "1024")

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(exactextractr)
  library(readr)
  library(dplyr)
})

terraOptions(memfrac = 0.5, todisk = TRUE, tempdir = tempdir())

# Simplify the country boundary by this tolerance (metres) before clipping
# the Voronoi cells. 500 m is imperceptible at country scale but makes the
# intersection ~10x faster / lighter.
BOUNDARY_SIMPLIFY_M <- 500

FAC_CSV       <- "etl/data/processed/country_standardized/tanzania_standardized.csv"
POP_TIF       <- "data/population/raw/tanzania/worldpop_2026_100m.tif"
DISTRICT_SHP  <- "data/population/raw/tanzania/districts/District_TZ_wgs84.shp"
OUT_DIR       <- "data/population/processed"

# Tanzania UTM 37S — accurate metres over the country footprint.
UTM_TZA <- 32737

dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)
for (p in c(FAC_CSV, POP_TIF, DISTRICT_SHP)) {
  if (!file.exists(p)) stop("Missing input: ", p)
}

# ---- facilities ------------------------------------------------------------
# The ETL CSV already has a `catchment_population` column (legacy — appears
# to be a pre-computed estimate from an earlier pipeline). Drop it so our
# Voronoi-based catchment_population is the ONLY one in the join; otherwise
# left_join disambiguates to catchment_population.x / .y and the later
# select() bombs.
hf <- suppressWarnings(read_csv(FAC_CSV, show_col_types = FALSE)) |>
  select(-any_of("catchment_population")) |>
  filter(!is.na(latitude), !is.na(longitude),
         is.finite(as.numeric(latitude)), is.finite(as.numeric(longitude))) |>
  mutate(latitude  = as.numeric(latitude),
         longitude = as.numeric(longitude),
         # site_id = "lon_lat" so facilities that share coords share a polygon
         site_id = paste(longitude, latitude, sep = "_"))

message(sprintf("Facilities with valid coords: %d", nrow(hf)))

# One point per unique location (keep first row's metadata)
sites <- hf |>
  group_by(site_id) |>
  slice(1) |>
  ungroup() |>
  st_as_sf(coords = c("longitude", "latitude"), crs = 4326, remove = FALSE)
message(sprintf("Unique facility locations: %d", nrow(sites)))

# ---- Voronoi ---------------------------------------------------------------
message("Building Voronoi polygons (UTM 37S)...")
sites_utm <- st_transform(sites, UTM_TZA)
vor <- st_voronoi(st_union(sites_utm)) |>
  st_collection_extract("POLYGON") |>
  st_as_sf()

# Attach facility metadata back onto the polygons
vor <- st_join(vor, sites_utm |> select(site_id, facility_code, facility_name,
                                        admin1, admin2, facility_type))

# Clip to country border (union of districts). Simplify the boundary first
# so GEOS doesn't run out of heap intersecting 11k polygons against a
# high-detail multi-polygon.
message("Clipping to country boundary (with simplification)...")
country <- st_read(DISTRICT_SHP, quiet = TRUE) |>
  st_transform(UTM_TZA) |>
  st_union() |>
  st_make_valid() |>
  st_simplify(dTolerance = BOUNDARY_SIMPLIFY_M, preserveTopology = TRUE)
gc()
vor <- st_intersection(vor, country)
# st_intersection can produce GEOMETRYCOLLECTIONs at boundary cells (polygon
# + a stray line where two Voronoi edges meet the border). Keep only the
# polygon parts so exact_extract sees consistent geometry.
vor <- st_collection_extract(vor, "POLYGON")
vor <- vor[!st_is_empty(vor), ]
gc()
message(sprintf("  after clip: %d polygons", nrow(vor)))

# ---- population per polygon -----------------------------------------------
message("Extracting population per catchment...")
pop     <- rast(POP_TIF)
vor_wgs <- st_transform(vor, 4326)
pop_vec <- exact_extract(pop, vor_wgs, "sum", progress = FALSE)
if (length(pop_vec) != nrow(vor_wgs)) {
  stop(sprintf("exact_extract returned %d values but vor_wgs has %d rows",
               length(pop_vec), nrow(vor_wgs)))
}
vor_wgs$catchment_population <- round(pop_vec)

# ---- facility-level CSV ---------------------------------------------------
catchment_lookup <- vor_wgs |>
  st_drop_geometry() |>
  select(site_id, catchment_population)

hf_out <- hf |>
  left_join(catchment_lookup, by = "site_id") |>
  select(facility_code, facility_name, admin1, admin2, facility_type,
         latitude, longitude, catchment_population)

# Quintile categories for the map colour ramp
qb <- quantile(hf_out$catchment_population, probs = seq(0, 1, 0.2),
               na.rm = TRUE, names = FALSE)
hf_out$catchment_category <- as.character(cut(
  hf_out$catchment_population,
  breaks = unique(qb),  # unique() in case of ties at boundaries
  include.lowest = TRUE,
  labels = c("Very Low", "Low", "Moderate", "High", "Very High")[
    seq_len(length(unique(qb)) - 1)]
))

CSV_OUT <- file.path(OUT_DIR, "tanzania_catchments_voronoi.csv")
write_csv(hf_out, CSV_OUT)
message(sprintf("Wrote %s (%d rows, median catchment = %s)",
                CSV_OUT, nrow(hf_out),
                format(round(median(hf_out$catchment_population, na.rm = TRUE)),
                       big.mark = ",")))

# ---- polygon layer for the portal map -------------------------------------
# Keep only what the portal needs; round coords for size. Don't name the
# geometry column in the select() — sf preserves the active geometry
# automatically, and it may not literally be called "geometry" (it's often
# named "x" when the sf was built from a bare sfc via st_as_sf).
vor_out <- vor_wgs |>
  select(facility_code, facility_name, admin1, admin2, catchment_population)

GEO_OUT <- file.path(OUT_DIR, "tanzania_voronoi_polygons.geojson")
if (file.exists(GEO_OUT)) file.remove(GEO_OUT)
st_write(vor_out, GEO_OUT, driver = "GeoJSON",
         layer_options = c("COORDINATE_PRECISION=5", "WRITE_BBOX=NO"),
         quiet = TRUE)
message(sprintf("Wrote %s (%.1f MB)", GEO_OUT, file.info(GEO_OUT)$size / 1e6))
