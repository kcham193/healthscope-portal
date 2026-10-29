# NOTE: run from the hf-data-portal project root - paths below expect its
# "population and access tab/" folder (rasters are not committed here).
# =====================================================================
# BAYESIAN CATCHMENT POPULATION - REGIONAL LOOP (population-conserving)
#
# Runs the PATH/catchment Bayesian gravity model once per Tanzania
# admin1 region at ~1 km resolution, then combines the runs nationally.
#
# Each run:
#   - population : only the people INSIDE the region polygon (district
#                  shapefile, unioned by Region_Nam). Every population
#                  cell therefore belongs to exactly one run.
#   - facilities : every facility physically inside the region or within
#                  BUFFER_KM of its border (by coordinates, not by the
#                  admin1 label), so cross-border travel is still allowed.
#   - extent     : region bbox + buffer, so travel surfaces cover the
#                  neighbouring facilities.
#
# Combine: a border facility appears in several runs; its national
# catchment is the SUM across runs. Because each person is allocated in
# exactly one run, the national total equals the population raster.
# SEs are combined as sqrt(sum(se^2)) (runs treated as independent);
# for multi-run facilities the 95% interval is the normal approximation.
#
# Per-run CSVs are cached; a re-run skips regions already done.
#
# Usage (from the project root):
#   Rscript "population and access tab/catchment_pop_bayesian_regional.R"            # all regions + combine
#   Rscript "population and access tab/catchment_pop_bayesian_regional.R" Arusha     # subset, no combine
#
# Outputs:
#   population and access tab/regional_runs/<region>.csv        (per run)
#   data/population/processed/tanzania_catchments.csv           (national)
#   data/population/processed/tanzania_facility_location_issues.csv
# =====================================================================

AGG_FACTOR <- as.integer(Sys.getenv("CATCH_AGG", "10"))
                     # 10 = ~1 km grid - fits 26 admin1 x mid-thousands
                     # facilities in RAM. Override with CATCH_AGG=5 for small
                     # dense regions (Dar es Salaam fails to fit at 1 km).
BUFFER_KM  <- 20     # facilities within this distance of a region border
                     # compete for that region's population
CACHE_ROOT <- file.path(path.expand("~"), "bayesian_tt_cache",
                        sprintf("regional_v2_agg%d", AGG_FACTOR))
dir.create(CACHE_ROOT, recursive = TRUE, showWarnings = FALSE)

suppressPackageStartupMessages({
  library(sf); library(terra); library(dplyr); library(fs)
  library(catchment); library(malariaAtlas); library(INLA)
})

# ---------- Paths ----------
proj_root <- normalizePath(".", winslash = "/")
work_dir  <- file.path(proj_root, "population and access tab")
out_dir   <- file.path(proj_root, "data", "population", "processed")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

hf_csv       <- file.path(proj_root, "data", "tanzania", "tanzania_standardized.csv")
pop_tif      <- file.path(work_dir, "tza_pop_2026_CN_100m_R2025A_v1.tif")
friction_tif <- file.path(work_dir, "friction_TZA_2015.tif")
district_shp <- file.path(work_dir, "Tanzania_shapefile_district",
                          "District_TZ_wgs84.shp")

run_out_dir <- file.path(work_dir, "regional_runs")
dir.create(run_out_dir, recursive = TRUE, showWarnings = FALSE)

ts <- function() format(Sys.time(), "%H:%M:%S")

# ---------- Load once ----------
# Region polygons; harmonise the one name that differs from the facility list
region_polys <- st_read(district_shp, quiet = TRUE) |>
  mutate(Region_Nam = recode(Region_Nam, "Dar-es-salaam" = "Dar es Salaam")) |>
  st_make_valid() |>
  group_by(region = Region_Nam) |> summarise(.groups = "drop") |>
  st_make_valid()

hf_full <- read.csv(hf_csv, stringsAsFactors = FALSE) |>
  mutate(across(where(is.character),
                \(x) iconv(x, from = "latin1", to = "UTF-8", sub = ""))) |>
  filter(!is.na(longitude), !is.na(latitude),
         longitude >= 29, longitude <= 41,
         latitude  >= -12, latitude <=  0) |>
  mutate(site_id = paste0(round(longitude, 5), "_", round(latitude, 5))) |>
  group_by(site_id) |> slice(1) |> ungroup() |>
  mutate(x = longitude, y = latitude, label = site_id, weight = 1) |>
  st_as_sf(coords = c("longitude", "latitude"), crs = 4326, remove = FALSE)

# Region each facility actually sits in (by coordinates)
hf_full$region_located <- region_polys$region[
  vapply(st_intersects(hf_full, region_polys),
         \(i) if (length(i)) i[1] else NA_integer_, integer(1))]

# Data-quality report: label disagrees with location, or outside all regions
issues <- hf_full |> st_drop_geometry() |>
  filter(is.na(region_located) | region_located != admin1) |>
  transmute(facility_code, facility_name, facility_type, admin1_label = admin1,
            region_located, latitude, longitude,
            issue = ifelse(is.na(region_located), "outside all regions",
                           "label differs from location"))
write.csv(issues, file.path(out_dir, "tanzania_facility_location_issues.csv"),
          row.names = FALSE)
cat(sprintf("[%s] %d facility sites; %d location issues written\n",
            ts(), nrow(hf_full), nrow(issues)))

pop_full  <- terra::rast(pop_tif)
fric_full <- terra::rast(friction_tif)

regions <- sort(region_polys$region)

# Optional: restrict to regions named on the command line
only_regions <- commandArgs(trailingOnly = TRUE)
if (length(only_regions)) regions <- intersect(regions, only_regions)

cat(sprintf("[%s] Regions to process: %d (%s)\n",
            ts(), length(regions), paste(head(regions, 6), collapse = ", ")))

safe_name <- function(x) gsub("[^A-Za-z0-9]+", "_", x)

# ---------- Loop ----------
for (region in regions) {
  slug     <- safe_name(region)
  csv_path <- file.path(run_out_dir, paste0(slug, ".csv"))
  if (file.exists(csv_path)) {
    cat(sprintf("[%s] SKIP %-20s (already done)\n", ts(), region))
    next
  }

  t0 <- Sys.time()
  cat(sprintf("\n[%s] === %s ===\n", ts(), region))

  poly     <- region_polys |> filter(region == !!region)
  poly_buf <- st_buffer(poly, BUFFER_KM * 1000)   # s2: distance in metres

  # Facilities inside the region or within the buffer, by coordinates
  in_buf <- lengths(st_intersects(hf_full, poly_buf)) > 0
  sites  <- hf_full[in_buf, ]
  n_own  <- sum(sites$region_located %in% region)
  cat(sprintf("  %d facilities (%d inside region, %d from buffer)\n",
              nrow(sites), n_own, nrow(sites) - n_own))
  if (n_own < 1 || nrow(sites) < 3) {
    cat("  SKIP - too few facilities\n"); next
  }

  # Population: only cells inside the region (mask at 100 m, then aggregate,
  # so border cells are split exactly between regions). Extent = buffer bbox
  # so the travel surfaces reach the buffer facilities.
  bb  <- terra::ext(terra::vect(poly_buf))
  pop <- terra::crop(pop_full, bb) |> terra::mask(terra::vect(poly))
  if (AGG_FACTOR > 1)
    pop <- terra::aggregate(pop, fact = AGG_FACTOR, fun = "sum", na.rm = TRUE)
  cat(sprintf("  Region population: %s\n",
              format(round(terra::global(pop, "sum", na.rm = TRUE)[1, 1]),
                     big.mark = ",")))

  # Friction over the full buffered extent (not masked: travel crosses borders)
  fric <- terra::crop(fric_full, bb) |> terra::resample(pop, method = "bilinear")

  # Drop facilities that fall outside friction extent (e.g. on water)
  inside <- !is.na(terra::extract(fric, terra::vect(sites))[, 2])
  if (sum(!inside)) cat("  Dropping", sum(!inside), "facilities on NA friction\n")
  sites <- sites[inside, ]
  if (nrow(sites) < 3) {
    cat("  SKIP - fewer than 3 facilities in extent\n"); next
  }

  # Per-facility travel-time surfaces (cache-per-region)
  tt_dir <- file.path(CACHE_ROOT, slug)
  dir.create(tt_dir, recursive = TRUE, showWarnings = FALSE)
  need_build <- length(list.files(tt_dir, pattern = "\\.tif$")) < nrow(sites)
  if (need_build) {
    cat("  Building", nrow(sites), "travel-time surfaces...\n")
    built <- tryCatch({
      catchment::create_travel_surface(
        friction_surface    = fric,
        extent_file         = pop,
        points              = sites,
        id_col              = "label",
        x_col               = "x",
        y_col               = "y",
        output_dir          = tt_dir,
        individual_surfaces = TRUE)
      TRUE
    },
      error = function(e) {
        cat("  FAIL create_travel_surface:", conditionMessage(e), "\n")
        FALSE
      })
    if (!built) next
  } else {
    cat("  Reusing existing travel-time surfaces\n")
  }

  tmat <- tryCatch(
    catchment::travel_mat_from_folder(dir = tt_dir, reference = pop),
    error = function(e) {
      cat("  FAIL travel_mat_from_folder:", conditionMessage(e), "\n")
      NULL
    })
  if (is.null(tmat)) next

  catch_dat <- tryCatch(
    catchment::prepare_data(
      prob_mat_init   = tmat,
      pop_raster      = pop,
      location_data   = sites,
      minimum_time    = 10,
      force_threshold = 300,
      n_fac_limit     = 10,
      mesh.args       = list(cutoff = 0.5, max.edge = c(0.5, 4))),
    error = function(e) {
      cat("  FAIL prepare_data:", conditionMessage(e), "\n")
      NULL
    })
  if (is.null(catch_dat)) next

  mod <- tryCatch(
    catchment::catchment_model(catch_dat),
    error = function(e) {
      cat("  FAIL catchment_model:", conditionMessage(e), "\n")
      NULL
    })
  if (is.null(mod)) next

  catch_pop <- catchment::catchment_populations(mod, uncertainty = TRUE) |>
    rename(any_of(c(site_id = "label", mean = "estimate",
                    lo95 = "lower", hi95 = "upper")))

  run_out <- catch_pop |>
    transmute(site_id, run_region = region, mean, se, lo95, hi95)

  write.csv(run_out, csv_path, row.names = FALSE)
  cat(sprintf("[%s] DONE %-20s %5d facilities, %s people allocated, %.1f min\n",
              ts(), region, nrow(run_out),
              format(round(sum(run_out$mean, na.rm = TRUE)), big.mark = ","),
              as.numeric(difftime(Sys.time(), t0, units = "mins"))))
}

# ---------- Combine ----------
if (length(only_regions)) {
  cat("\nRegion subset run - skipping national combine.\n")
  quit(save = "no")
}
cat("\n=== Combining regional runs ===\n")
csvs <- list.files(run_out_dir, pattern = "\\.csv$", full.names = TRUE)
if (!length(csvs)) stop("No per-region CSVs produced.")
missing_runs <- setdiff(safe_name(regions), tools::file_path_sans_ext(basename(csvs)))
if (length(missing_runs))
  cat("WARNING - regions without output:", paste(missing_runs, collapse = ", "), "\n")

runs <- do.call(rbind, lapply(csvs, read.csv, stringsAsFactors = FALSE))

combined <- runs |>
  filter(!is.na(mean)) |>
  group_by(site_id) |>
  summarise(n_runs   = n(),
            regions  = paste(run_region, collapse = "; "),
            lo95_one = first(lo95), hi95_one = first(hi95),
            se       = sqrt(sum(se^2, na.rm = TRUE)),
            mean     = sum(mean), .groups = "drop") |>
  mutate(lo95 = ifelse(n_runs == 1, lo95_one, pmax(0, mean - 1.96 * se)),
         hi95 = ifelse(n_runs == 1, hi95_one, mean + 1.96 * se))

all <- hf_full |> st_drop_geometry() |>
  inner_join(combined, by = "site_id") |>
  transmute(facility_code, facility_name, admin1, region_located, facility_type,
            latitude, longitude,
            catchment_population       = round(mean),
            catchment_population_se    = round(se, 1),
            catchment_population_lo95  = round(lo95),
            catchment_population_hi95  = round(hi95),
            n_runs, runs_regions = regions)

# National quintile category for map colouring
brk <- quantile(all$catchment_population,
                probs = seq(0, 1, 0.2), na.rm = TRUE)
all$catchment_category <- as.character(cut(
  all$catchment_population, breaks = unique(brk), include.lowest = TRUE,
  labels = c("Very Low", "Low", "Moderate", "High", "Very High")[seq_len(length(unique(brk)) - 1)]))

final_csv <- file.path(out_dir, "tanzania_catchments.csv")
write.csv(all, final_csv, row.names = FALSE)

cat(sprintf("\nWrote %d facilities from %d regional runs to:\n  %s\n",
            nrow(all), length(csvs), final_csv))
cat(sprintf("Total allocated: %s   (population raster total: %s)\n",
            format(sum(all$catchment_population), big.mark = ","),
            format(round(terra::global(pop_full, "sum", na.rm = TRUE)[1, 1]),
                   big.mark = ",")))
