# scripts/population/01_catchment_extract.R
#
# For each of the 8 portal countries, computes population within 5 km and
# 10 km buffers of every facility and writes one CSV per country into
# data/population/processed/. See scripts/population/README.md for context.
#
# Usage:
#   Rscript scripts/population/01_catchment_extract.R            # all countries
#   Rscript scripts/population/01_catchment_extract.R tanzania   # single country

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(exactextractr)
  library(readr)
  library(dplyr)
  library(purrr)
})

WORLDPOP_YEAR <- 2020

# Africa Albers Equal-Area Conic — accurate buffers across the continent,
# unlike UTM which is only accurate within its 6-degree zone. Buffers built
# in metres in this CRS then re-projected back to WGS84 for the raster op.
AFRICA_EQUAL_AREA <- "ESRI:102022"

BUFFERS_M <- c(pop_5km = 5000, pop_10km = 10000)

# slug -> ISO3 lowercase (must match 00_download_worldpop.R)
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

# ---- paths -----------------------------------------------------------------
facility_csv <- function(slug) {
  sprintf("etl/data/processed/country_standardized/%s_standardized.csv", slug)
}
worldpop_tif <- function(iso3_lower) {
  sprintf("data/population/raw/%s_ppp_%d_1km.tif", iso3_lower, WORLDPOP_YEAR)
}
out_csv <- function(slug) {
  sprintf("data/population/processed/%s_catchments.csv", slug)
}

dir.create("data/population/processed", recursive = TRUE, showWarnings = FALSE)

# ---- per-country ------------------------------------------------------------
process_country <- function(slug, iso3_lower) {
  message(sprintf("\n=== %s (%s) ===", slug, iso3_lower))

  fac_path <- facility_csv(slug)
  tif_path <- worldpop_tif(iso3_lower)

  if (!file.exists(fac_path)) {
    warning(sprintf("[%s] facility CSV missing: %s — skipping", slug, fac_path))
    return(invisible(NULL))
  }
  if (!file.exists(tif_path)) {
    warning(sprintf("[%s] WorldPop raster missing: %s — run 00_download_worldpop.R first",
                    slug, tif_path))
    return(invisible(NULL))
  }

  facilities <- suppressWarnings(read_csv(fac_path, show_col_types = FALSE)) |>
    filter(!is.na(latitude), !is.na(longitude),
           is.finite(as.numeric(latitude)), is.finite(as.numeric(longitude))) |>
    mutate(latitude  = as.numeric(latitude),
           longitude = as.numeric(longitude))
  message(sprintf("  facilities with valid coords: %d", nrow(facilities)))

  if (nrow(facilities) == 0) {
    warning(sprintf("[%s] no valid coordinates — skipping", slug))
    return(invisible(NULL))
  }

  pts <- st_as_sf(facilities, coords = c("longitude", "latitude"),
                  crs = 4326, remove = FALSE)
  pts_eq <- st_transform(pts, AFRICA_EQUAL_AREA)

  pop_raster <- rast(tif_path)

  for (col in names(BUFFERS_M)) {
    d <- BUFFERS_M[[col]]
    message(sprintf("  buffering %g m and extracting -> %s", d, col))
    buf <- st_buffer(pts_eq, dist = d) |> st_transform(4326)
    facilities[[col]] <- exact_extract(pop_raster, buf, "sum", progress = FALSE)
  }

  # Portal-friendly column set. `admin1` / `admin2` may not exist for every
  # country's schema so we only keep them if present.
  keep <- c("facility_code", "facility_name", "admin1", "admin2",
            "facility_type", "latitude", "longitude",
            names(BUFFERS_M))
  keep <- intersect(keep, names(facilities))
  out  <- facilities[, keep]

  # Round populations to whole people; the sub-integer noise is model artefact.
  out$pop_5km  <- round(out$pop_5km)
  out$pop_10km <- round(out$pop_10km)

  dest <- out_csv(slug)
  write_csv(out, dest)
  message(sprintf("  wrote %s  (%d rows, median pop_5km = %.0f, pop_10km = %.0f)",
                  dest, nrow(out),
                  median(out$pop_5km,  na.rm = TRUE),
                  median(out$pop_10km, na.rm = TRUE)))
  invisible(dest)
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
