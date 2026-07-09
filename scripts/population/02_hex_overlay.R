# scripts/population/02_hex_overlay.R
#
# Aggregates WorldPop 1 km rasters onto a ~10 km hexagonal grid per country,
# for use as a background overlay on the Population and Access map. Output:
# one GeoJSON per country in data/population/processed/.
#
# Uses sf::st_make_grid in Africa Albers Equal-Area for accurate equal-area
# hexes; not H3-indexed but visually and analytically equivalent (H3 would
# have needed h3jsr, which pulls V8 and is finicky on Windows R).
#
# Usage:
#   Rscript scripts/population/02_hex_overlay.R            # all countries
#   Rscript scripts/population/02_hex_overlay.R tanzania   # single country

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(exactextractr)
  library(dplyr)
})

WORLDPOP_YEAR     <- 2020
AFRICA_EQUAL_AREA <- "ESRI:102022"

# cellsize in st_make_grid for hex = vertex-to-vertex distance (long axis).
# 10 km long axis ⇒ 5 km edge ⇒ area ≈ 65 km² per hex.
# Kenya ~580 k km² ⇒ ~9k hexes; Ethiopia ~1.1M km² ⇒ ~17k hexes total,
# ~60-80% of which survive the min-pop filter below.
HEX_LONG_AXIS_M <- 10000

# Drop hexes with essentially no population — cuts the geojson roughly in
# half for arid/desert countries (Botswana, northern Kenya, N. Nigeria).
MIN_POP <- 10

COUNTRIES <- list(
  tanzania = "tza",
  kenya    = "ken",
  nigeria  = "nga",
  uganda   = "uga",
  zambia   = "zmb",
  malawi   = "mwi",
  botswana = "bwa",
  ethiopia = "eth"
)

# Same country bounding boxes as 01_catchment_extract.R — used here to size
# the hex grid to just the country (rather than the raster's extent, which
# may include a small buffer of ocean / neighbouring land).
BBOX <- list(
  tanzania = c(-11.8, -1.0, 29.2, 40.6),
  kenya    = c(-4.7,   5.5, 33.9, 41.9),
  nigeria  = c(  4.0, 14.0,  2.7, 14.7),
  uganda   = c(-1.5,   4.3, 29.5, 35.1),
  zambia   = c(-18.1, -8.2, 21.9, 33.7),
  malawi   = c(-17.2, -9.3, 32.6, 36.0),
  botswana = c(-27.0,-17.7, 19.9, 29.4),
  ethiopia = c(  3.0, 15.0, 33.0, 48.0)
)

dir.create("data/population/processed", recursive = TRUE, showWarnings = FALSE)

process_country <- function(slug, iso3_lower) {
  message(sprintf("\n=== %s (%s) ===", slug, iso3_lower))

  tif_path <- sprintf("data/population/raw/%s_ppp_%d_1km.tif", iso3_lower, WORLDPOP_YEAR)
  out_path <- sprintf("data/population/processed/%s_hex_pop.geojson", slug)

  if (!file.exists(tif_path)) {
    warning(sprintf("[%s] raster missing: %s — run 00_download_worldpop.R first", slug, tif_path))
    return(invisible(NULL))
  }

  # 1. Build country bbox polygon in WGS84, then transform to Albers for the grid.
  b  <- BBOX[[slug]]
  bb <- st_as_sfc(st_bbox(c(xmin = b[3], xmax = b[4], ymin = b[1], ymax = b[2]), crs = 4326))
  bb_alb <- st_transform(bb, AFRICA_EQUAL_AREA)

  # 2. Hex grid in Albers (equal-area). Back to WGS84 for the raster op.
  hex_alb <- st_make_grid(bb_alb, cellsize = HEX_LONG_AXIS_M, square = FALSE)
  hex_alb_sf <- st_sf(geometry = hex_alb)
  hex_wgs <- st_transform(hex_alb_sf, 4326)
  message(sprintf("  hex grid over country bbox: %d cells", nrow(hex_wgs)))

  # 3. Sum WorldPop pixels within each hex.
  r <- rast(tif_path)
  hex_wgs$pop <- exact_extract(r, hex_wgs, "sum", progress = FALSE)
  hex_wgs$pop[!is.finite(hex_wgs$pop)] <- 0
  hex_wgs$pop <- round(hex_wgs$pop)

  # 4. Filter to hexes with meaningful population.
  keep <- hex_wgs[hex_wgs$pop >= MIN_POP, "pop"]
  message(sprintf("  hexes with pop >= %d: %d (%.0f%% of grid)",
                  MIN_POP, nrow(keep), 100 * nrow(keep) / nrow(hex_wgs)))

  # 5. Write with reduced coordinate precision (5 decimals ≈ 1 m at equator)
  #    to keep the geojson small.
  if (file.exists(out_path)) file.remove(out_path)
  st_write(keep, out_path, driver = "GeoJSON",
           layer_options = c("COORDINATE_PRECISION=5", "WRITE_BBOX=NO"),
           quiet = TRUE)

  size_kb <- file.info(out_path)$size / 1024
  message(sprintf("  wrote %s  (%d hexes, %.0f KB)",
                  out_path, nrow(keep), size_kb))
  invisible(out_path)
}

# ---- driver ----------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
targets <- if (length(args)) intersect(args, names(COUNTRIES)) else names(COUNTRIES)
if (length(targets) == 0) {
  stop("No matching countries. Valid: ", paste(names(COUNTRIES), collapse = ", "))
}

for (slug in targets) {
  tryCatch(
    process_country(slug, COUNTRIES[[slug]]),
    error = function(e) message(sprintf("[%s] ERROR: %s", slug, conditionMessage(e)))
  )
}
message("\nDone.")
