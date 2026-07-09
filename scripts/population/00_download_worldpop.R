# scripts/population/00_download_worldpop.R
#
# Downloads WorldPop 2020 1 km unconstrained population rasters for the 8
# portal countries into data/population/raw/. Idempotent — skips files that
# already exist. See scripts/population/README.md for context.

suppressPackageStartupMessages({
  library(httr)
  library(purrr)
})

WORLDPOP_YEAR <- 2020

# ISO3 lowercase → WorldPop file naming. Matches the portal's country slugs
# used by 01_catchment_extract.R and the frontend.
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

RAW_DIR <- "data/population/raw"
dir.create(RAW_DIR, recursive = TRUE, showWarnings = FALSE)

worldpop_url <- function(iso3_lower) {
  iso3_upper <- toupper(iso3_lower)
  sprintf(
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/%d/%s/%s_ppp_%d_1km_Aggregated.tif",
    WORLDPOP_YEAR, iso3_upper, iso3_lower, WORLDPOP_YEAR
  )
}

# NOTE: iwalk(named_list, .f) calls .f(value, name), so `iso3_lower` (the
# value in COUNTRIES) is the FIRST arg and `slug` (the name) is the SECOND.
download_one <- function(iso3_lower, slug) {
  dest <- file.path(RAW_DIR, sprintf("%s_ppp_%d_1km.tif", iso3_lower, WORLDPOP_YEAR))
  if (file.exists(dest) && file.info(dest)$size > 1e6) {
    message(sprintf("  %-9s [skip]  already have %s (%.1f MB)",
                    slug, basename(dest), file.info(dest)$size / 1e6))
    return(invisible(dest))
  }
  url <- worldpop_url(iso3_lower)
  message(sprintf("  %-9s [get ]  %s", slug, url))
  resp <- tryCatch(
    GET(url, write_disk(dest, overwrite = TRUE), progress()),
    error = function(e) e
  )
  if (inherits(resp, "error") || http_error(resp)) {
    file.remove(dest)
    stop(sprintf("Failed to download %s: %s", url,
                 if (inherits(resp, "error")) conditionMessage(resp) else status_code(resp)))
  }
  size_mb <- file.info(dest)$size / 1e6
  message(sprintf("  %-9s [ok  ]  %.1f MB -> %s", slug, size_mb, basename(dest)))
  invisible(dest)
}

message(sprintf("Downloading WorldPop %d rasters for %d countries to %s/",
                WORLDPOP_YEAR, length(COUNTRIES), RAW_DIR))
message("")
iwalk(COUNTRIES, download_one)
message("")
message("Done. Next: Rscript scripts/population/01_catchment_extract.R")
