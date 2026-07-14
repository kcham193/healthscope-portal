# scripts/population/tanzania/10_wdpa_mask.R
#
# Reads the two WDPA polygon shapefiles for Tanzania (May 2026 snapshot),
# filters to STRICT protected areas (IUCN Ia, Ib, II, III — national parks,
# wilderness, strict nature reserves, natural monuments), and writes a
# compact GeoJSON for use as an OPTIONAL overlay on the accessibility map.
#
# We do NOT mask the population raster with this — the tt_b4 travel-time
# surface already has NA over protected zones. This layer is visual
# context: "here's why Serengeti looks empty in the map."
#
# Input:
#   data/population/raw/tanzania/wdpa/wdpa_0/WDPA_WDOECM_May2026_Public_TZA_shp-polygons.shp
#   data/population/raw/tanzania/wdpa/wdpa_1/WDPA_WDOECM_May2026_Public_TZA_shp-polygons.shp
#
# Output:
#   data/population/processed/tanzania_wdpa_strict.geojson

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
})

RAW_DIR <- "data/population/raw/tanzania/wdpa"
OUT     <- "data/population/processed/tanzania_wdpa_strict.geojson"

paths <- c(
  file.path(RAW_DIR, "wdpa_0", "WDPA_WDOECM_May2026_Public_TZA_shp-polygons.shp"),
  file.path(RAW_DIR, "wdpa_1", "WDPA_WDOECM_May2026_Public_TZA_shp-polygons.shp")
)
missing <- paths[!file.exists(paths)]
if (length(missing)) {
  stop("Missing WDPA shapefiles:\n  ", paste(missing, collapse = "\n  "),
       "\nDrop your wdpa_0/ and wdpa_1/ folders into ", RAW_DIR)
}

wdpa_all <- bind_rows(lapply(paths, st_read, quiet = TRUE))
message(sprintf("Total WDPA polygons: %d", nrow(wdpa_all)))

# Active designations only — no "Proposed"
wdpa_clean <- wdpa_all |>
  filter(STATUS %in% c("Designated", "Inscribed", "Established"))
message(sprintf("Active designations: %d", nrow(wdpa_clean)))

# Strict IUCN categories only (Ia, Ib, II, III)
wdpa_strict <- wdpa_clean |>
  filter(IUCN_CAT %in% c("Ia", "Ib", "II", "III")) |>
  mutate(area_type = case_when(
    IUCN_CAT == "II"  ~ "National Park",
    IUCN_CAT == "III" ~ "Natural Monument",
    IUCN_CAT == "Ib"  ~ "Wilderness Area",
    IUCN_CAT == "Ia"  ~ "Strict Nature Reserve",
    TRUE              ~ "Other"
  )) |>
  select(NAME, area_type, IUCN_CAT, geometry)
message(sprintf("Strict-category polygons: %d", nrow(wdpa_strict)))

dir.create(dirname(OUT), recursive = TRUE, showWarnings = FALSE)
if (file.exists(OUT)) file.remove(OUT)
st_write(wdpa_strict, OUT, driver = "GeoJSON",
         layer_options = c("COORDINATE_PRECISION=5", "WRITE_BBOX=NO"),
         quiet = TRUE)
size_kb <- file.info(OUT)$size / 1024
message(sprintf("Wrote %s (%.0f KB)", OUT, size_kb))
