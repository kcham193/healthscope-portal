# scripts/population/03_road_reachability.R
#
# For each portal country: fetches the OSM road network from GeoFabrik,
# computes each facility's distance to the nearest road, and classifies
# into 4 accessibility buckets. Output:
# data/population/processed/{country}_reachability.csv
#
# Columns: facility_code, road_dist_m, road_class
#          (road_class ∈ on_road | near_road | off_road | isolated)
#
# Requires the osmextract R package. First run downloads ~1.5-2 GB of
# .osm.pbf extracts to data/population/raw/geofabrik/ (gitignored).
# Subsequent runs are cached.
#
# Usage:
#   Rscript scripts/population/03_road_reachability.R            # all
#   Rscript scripts/population/03_road_reachability.R tanzania   # one

suppressPackageStartupMessages({
  library(osmextract)
  library(sf)
  library(readr)
  library(dplyr)
})

AFRICA_EQUAL_AREA <- "ESRI:102022"

# Thresholds (metres) matching the concept-note framing.
# The 10 km cut captures "the dispensary 15 km from the nearest road".
CLASS_THRESHOLDS <- c(500, 2000, 10000)
CLASS_LABELS     <- c("on_road", "near_road", "off_road", "isolated")

# Portal slug -> GeoFabrik place name (both happen to match here).
COUNTRIES <- list(
  tanzania = "tanzania",
  kenya    = "kenya",
  nigeria  = "nigeria",
  uganda   = "uganda",
  zambia   = "zambia",
  malawi   = "malawi",
  botswana = "botswana",
  ethiopia = "ethiopia"
)

OSM_DIR <- "data/population/raw/geofabrik"
dir.create(OSM_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create("data/population/processed", recursive = TRUE, showWarnings = FALSE)

facility_csv <- function(slug) {
  sprintf("etl/data/processed/country_standardized/%s_standardized.csv", slug)
}
out_csv <- function(slug) {
  sprintf("data/population/processed/%s_reachability.csv", slug)
}

process_country <- function(slug) {
  message(sprintf("\n=== %s ===", slug))
  place <- COUNTRIES[[slug]]

  fac_path <- facility_csv(slug)
  if (!file.exists(fac_path)) {
    warning(sprintf("[%s] facility CSV missing: %s", slug, fac_path))
    return(invisible(NULL))
  }

  # 1. Download + parse OSM roads. osmextract handles GeoFabrik fetching
  #    and caches under download_directory. `layer = "lines"` + the SQL
  #    query filters to highway=* features only, keeping the read fast.
  message(sprintf("  fetching OSM road network for %s (cached after first run)...", place))
  roads <- tryCatch(
    oe_get(
      place              = place,
      layer              = "lines",
      query              = "SELECT highway, geometry FROM lines WHERE highway IS NOT NULL",
      download_directory = OSM_DIR,
      quiet              = TRUE
    ),
    error = function(e) e
  )
  if (inherits(roads, "error")) {
    warning(sprintf("[%s] OSM fetch failed: %s", slug, conditionMessage(roads)))
    return(invisible(NULL))
  }
  message(sprintf("  road segments: %d", nrow(roads)))

  # 2. Load facilities (same filter as 01_catchment_extract.R).
  facilities <- suppressWarnings(read_csv(fac_path, show_col_types = FALSE)) |>
    filter(!is.na(latitude), !is.na(longitude),
           is.finite(as.numeric(latitude)), is.finite(as.numeric(longitude))) |>
    mutate(latitude  = as.numeric(latitude),
           longitude = as.numeric(longitude))
  message(sprintf("  facilities with valid coords: %d", nrow(facilities)))

  # 3. Compute nearest-road distance in Africa Albers (metres).
  fac_sf    <- st_as_sf(facilities, coords = c("longitude", "latitude"),
                        crs = 4326, remove = FALSE)
  fac_alb   <- st_transform(fac_sf, AFRICA_EQUAL_AREA)
  roads_alb <- st_transform(roads,  AFRICA_EQUAL_AREA)

  message("  computing nearest-road distances (spatial index)...")
  nearest_idx <- st_nearest_feature(fac_alb, roads_alb)
  dists       <- st_distance(fac_alb, roads_alb[nearest_idx, ], by_element = TRUE)
  facilities$road_dist_m <- round(as.numeric(dists))

  # 4. Classify.
  facilities$road_class <- as.character(cut(
    facilities$road_dist_m,
    breaks = c(-Inf, CLASS_THRESHOLDS, Inf),
    labels = CLASS_LABELS
  ))

  # 5. Report + write.
  cls <- table(factor(facilities$road_class, levels = CLASS_LABELS))
  pct <- sprintf("%.0f%%", 100 * cls / sum(cls))
  message(sprintf("  class breakdown: %s",
                  paste0(names(cls), "=", cls, " (", pct, ")",
                         collapse = "   ")))

  dest <- out_csv(slug)
  out  <- facilities |> select(facility_code, road_dist_m, road_class)
  write_csv(out, dest)
  message(sprintf("  wrote %s (%d rows)", dest, nrow(out)))
  invisible(dest)
}

# Driver
args    <- commandArgs(trailingOnly = TRUE)
targets <- if (length(args)) intersect(args, names(COUNTRIES)) else names(COUNTRIES)
if (length(targets) == 0) {
  stop("No matching countries. Valid: ", paste(names(COUNTRIES), collapse = ", "))
}

for (slug in targets) {
  tryCatch(
    process_country(slug),
    error = function(e) message(sprintf("[%s] ERROR: %s", slug, conditionMessage(e)))
  )
}
message("\nDone.")
