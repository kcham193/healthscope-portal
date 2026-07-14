# scripts/population/tanzania/13_simplify_bands.R
#
# The polygonised travel-time bands from step 11 come out at ~50 MB because
# 300 m raster cells produce jagged band boundaries with millions of tiny
# vertices. This script simplifies the geometry to a size that's usable in
# the browser (target: 3-5 MB) with an imperceptible visual change at the
# zoom levels the portal actually uses.
#
# Input & output are the same file — we overwrite the 50 MB version in
# place. The categorical GeoTIFF (tanzania_travel_time_categories.tif) is
# the source of truth; if we ever want a different tolerance, we can
# re-polygonise from that raster and re-run this.
#
# Usage:
#   Rscript scripts/population/tanzania/13_simplify_bands.R

suppressPackageStartupMessages({
  library(sf)
})

PATH   <- "data/population/processed/tanzania_travel_time_bands.geojson"
UTM_TZ <- 32737       # metres — st_simplify's tolerance is in CRS units
TOL_M  <- 1000        # 1 km tolerance. Bump to 2000 if still too big.

if (!file.exists(PATH)) {
  stop("Missing input: ", PATH,
       "\nRun 11_travel_time_bands.R first.")
}

size_before <- file.info(PATH)$size / 1e6
bands <- st_read(PATH, quiet = TRUE)
message(sprintf("Loaded %d band polygons (%.1f MB on disk)",
                nrow(bands), size_before))

message(sprintf("Simplifying at %d m tolerance in UTM 37S...", TOL_M))
bands_simple <- bands |>
  st_transform(UTM_TZ) |>
  st_simplify(dTolerance = TOL_M, preserveTopology = TRUE) |>
  st_transform(4326) |>
  st_make_valid()

# Drop any empty geometries st_simplify may have collapsed
bands_simple <- bands_simple[!st_is_empty(bands_simple), ]

if (file.exists(PATH)) file.remove(PATH)
st_write(bands_simple, PATH, driver = "GeoJSON",
         layer_options = c("COORDINATE_PRECISION=4", "WRITE_BBOX=NO"),
         quiet = TRUE)

size_after <- file.info(PATH)$size / 1e6
message(sprintf("Wrote %s (%.1f MB, %.0f%% smaller)",
                PATH, size_after,
                100 * (1 - size_after / size_before)))
