#!/usr/bin/env python3
"""
==========================================================================
  KENYA MASTER HEALTH FACILITY REGISTRY (KMHFR) - FULL DATA EXTRACTION
==========================================================================

  Author:  Kasim Chambulilo
  Project: HealthScope Intelligence Portal
  Date:    May 2026
  Source:  https://kmhfr.health.go.ke/public/facilities

  Description:
  ------------
  This script extracts all health facility data from the Kenya Master
  Health Facility Registry (KMHFR) at https://kmhfr.health.go.ke.

  The KMHFR does not provide a public API. Data is embedded in server-
  rendered HTML pages using Next.js React Server Components. This script
  extracts facility data by:

    Phase 1: Scraping the paginated facility listing (30 per page)
             to get facility ID, name, type, owner, county, KEPH level,
             and operation status for all ~17,000+ facilities.

    Phase 2: Scraping each individual facility detail page to extract
             GPS coordinates (latitude/longitude) and the full list of
             services offered, with their categories.

  The output is two standardized CSV files:
    - kenya_standardized.csv  (facility registry with coordinates)
    - kenya_services.csv      (long-format service records)

  Requirements:
  -------------
  Python 3.10+ (standard library only - no pip packages needed)

  Usage:
  ------
    python kenya_extraction.py

  The script will create an output/ directory with all results.
  Total runtime: ~40-60 minutes depending on network speed.

==========================================================================
"""

import json
import csv
import re
import os
import sys
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Configuration ─────────────────────────────────────────────────────

OUTPUT_DIR = "output"
THREADS_LISTING = 8       # Threads for Phase 1 (listing pages)
THREADS_DETAIL = 10       # Threads for Phase 2 (detail pages)
FACILITIES_PER_PAGE = 30  # KMHFR returns 30 per page
REQUEST_TIMEOUT = 30      # Seconds per HTTP request
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Kenya geographic bounding box for coordinate validation
KENYA_BOUNDS = {
    "lat_min": -4.7,
    "lat_max": 5.5,
    "lon_min": 33.9,
    "lon_max": 41.9,
}

# SSL context (KMHFR uses standard HTTPS)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── HTTP Helper ───────────────────────────────────────────────────────

def fetch_url(url):
    """Fetch a URL and return the decoded HTML content."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=SSL_CTX)
    return resp.read().decode("utf-8", "replace")


# ======================================================================
#  PHASE 1: SCRAPE FACILITY LISTING PAGES
# ======================================================================

def extract_facilities_from_page(html):
    """
    Extract facility records from a KMHFR listing page.

    The KMHFR is a Next.js application. Facility data is embedded in
    self.__next_f.push() script blocks as escaped JSON within the
    server-rendered HTML. Each facility object contains:

      - id (UUID)
      - facility_type_name
      - owner_name
      - operation_status_name
      - constituency_name, ward_name, sub_county_name, county_name
      - keph_level_name
      - name, official_name
      - code (numeric facility code)

    This function uses regex to extract these objects from the HTML.
    """
    pushes = re.findall(
        r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL
    )
    facilities = []
    for push_content in pushes:
        # Unescape the JSON content embedded in the script tag
        content = push_content.replace('\\"', '"').replace("\\u0026", "&")

        # Match facility JSON objects
        for m in re.finditer(
            r'\{"id":"([a-f0-9-]{36})",'
            r'"facility_type_name":"([^"]*)",'
            r'"owner_name":"([^"]*)",'
            r'"operation_status_name":"([^"]*)",'
            r'"constituency_name":"([^"]*)",'
            r'"ward_name":"([^"]*)",'
            r'"sub_county_name":"([^"]*)",'
            r'"county_name":"([^"]*)",'
            r'"keph_level_name":"([^"]*)",'
            r'"name":"([^"]*)",'
            r'"official_name":"([^"]*)",'
            r'"code":(\d+|null)',
            content,
        ):
            facilities.append({
                "id": m.group(1),
                "facility_type": m.group(2),
                "owner": m.group(3),
                "status": m.group(4),
                "constituency": m.group(5),
                "ward": m.group(6),
                "sub_county": m.group(7),
                "county": m.group(8),
                "keph_level": m.group(9),
                "name": m.group(10),
                "official_name": m.group(11),
                "code": m.group(12) if m.group(12) != "null" else "",
            })
    return facilities


def fetch_listing_page(page_num):
    """Fetch a single listing page and extract facilities."""
    url = f"https://kmhfr.health.go.ke/public/facilities?page={page_num}"
    html = fetch_url(url)
    return page_num, extract_facilities_from_page(html)


def phase1_scrape_listings():
    """
    Phase 1: Scrape all paginated listing pages.

    The KMHFR has ~17,000+ facilities displayed 30 per page.
    We first fetch page 1 to confirm the format works, then
    scrape all ~580 pages concurrently using a thread pool.

    Returns a dict of {facility_id: facility_dict}.
    """
    print("=" * 60)
    print("  PHASE 1: Scraping facility listing pages")
    print("=" * 60)

    # First, determine total pages by fetching page 1
    print("Fetching page 1 to verify format...", flush=True)
    html = fetch_url("https://kmhfr.health.go.ke/public/facilities?page=1")
    page1_facs = extract_facilities_from_page(html)
    print(f"  Page 1: {len(page1_facs)} facilities extracted", flush=True)

    if not page1_facs:
        print("ERROR: No facilities found on page 1. The website format may have changed.")
        sys.exit(1)

    # Estimate total pages (17,418 / 30 = 581)
    # We overshoot slightly and stop when we get empty pages
    total_pages = 600
    print(f"  Scraping up to {total_pages} pages with {THREADS_LISTING} threads...", flush=True)

    all_facilities = {}
    for f in page1_facs:
        all_facilities[f["id"]] = f

    errors = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=THREADS_LISTING) as executor:
        # Submit pages 2 through total_pages
        futures = {
            executor.submit(fetch_listing_page, p): p
            for p in range(2, total_pages + 1)
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                page_num, facs = future.result()
                for f in facs:
                    all_facilities[f["id"]] = f
            except Exception:
                errors += 1

            if done % 50 == 0 or done <= 3:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                print(
                    f"  Progress: {done}/{total_pages - 1} pages | "
                    f"{len(all_facilities)} facilities | "
                    f"{errors} errors | "
                    f"{rate:.1f} pages/sec",
                    flush=True,
                )

    elapsed = time.time() - start_time
    print(f"\n  Phase 1 complete:")
    print(f"    Facilities: {len(all_facilities)}")
    print(f"    Errors:     {errors}")
    print(f"    Time:       {elapsed:.0f} seconds")
    print(f"    Counties:   {len(set(f['county'] for f in all_facilities.values()))}")

    return all_facilities


# ======================================================================
#  PHASE 2: SCRAPE FACILITY DETAIL PAGES (COORDINATES + SERVICES)
# ======================================================================

def extract_detail(facility):
    """
    Fetch a facility detail page and extract coordinates + services.

    Each facility has a detail page at:
      https://kmhfr.health.go.ke/public/facilities/{uuid}

    The detail page contains:
      - GPS coordinates in a JSON field: "lat_long":[-1.30088,36.80734]
      - Services listed with service_name and category_name fields
        embedded in the self.__next_f.push() blocks.

    Returns: (facility_id, latitude, longitude, list_of_services)
    """
    uid = facility["id"]
    url = f"https://kmhfr.health.go.ke/public/facilities/{uid}"
    html = fetch_url(url)

    # ── Extract coordinates ──
    lat, lon = "", ""
    coord_match = re.search(r"lat_long..:\[([0-9.\-]+),([0-9.\-]+)\]", html)
    if coord_match:
        lat, lon = coord_match.group(1), coord_match.group(2)

    # ── Extract services ──
    # Services are embedded in self.__next_f.push() blocks.
    # Each service has a service_name and category_name.
    pushes = re.findall(
        r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL
    )
    all_text = " ".join(
        p.replace('\\"', '"').replace("\\u0026", "&") for p in pushes
    )

    service_names = re.findall(r'"service_name":"([^"]{3,120})"', all_text)
    category_names = re.findall(r'"category_name":"([^"]{3,120})"', all_text)

    services = []
    if len(service_names) == len(category_names):
        # Paired: service_name and category_name appear in order
        for name, cat in zip(service_names, category_names):
            services.append({"name": name, "category": cat})
    else:
        # Unpaired: just use service names
        for name in service_names:
            services.append({"name": name, "category": ""})

    return uid, lat, lon, services


def phase2_scrape_details(all_facilities):
    """
    Phase 2: Scrape all facility detail pages for coordinates and services.

    This is the most time-consuming step as it requires one HTTP request
    per facility (~17,000 requests). We use a thread pool with 10-12
    concurrent connections to keep it under 30 minutes.

    Returns: (coords_dict, services_dict)
      - coords_dict:   {facility_id: (lat, lon)}
      - services_dict: {facility_id: [{"name": ..., "category": ...}, ...]}
    """
    print("\n" + "=" * 60)
    print("  PHASE 2: Scraping facility detail pages")
    print("=" * 60)

    total = len(all_facilities)
    print(f"  Scraping {total} detail pages with {THREADS_DETAIL} threads...")
    print(f"  Estimated time: {total * 1.5 / THREADS_DETAIL / 60:.0f}-{total * 3 / THREADS_DETAIL / 60:.0f} minutes")
    print(flush=True)

    coords = {}
    services_data = {}
    errors = 0
    start_time = time.time()

    facilities_list = list(all_facilities.values())

    with ThreadPoolExecutor(max_workers=THREADS_DETAIL) as executor:
        futures = {
            executor.submit(extract_detail, f): f["id"]
            for f in facilities_list
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                uid, lat, lon, svcs = future.result()
                if lat and lon:
                    coords[uid] = (lat, lon)
                if svcs:
                    services_data[uid] = svcs
            except Exception:
                errors += 1

            if done % 500 == 0 or done <= 3:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate / 60 if rate > 0 else 0
                print(
                    f"  Progress: {done}/{total} | "
                    f"{len(coords)} coords | "
                    f"{len(services_data)} w/services | "
                    f"{errors} errors | "
                    f"ETA: {eta:.0f} min",
                    flush=True,
                )

    elapsed = time.time() - start_time
    print(f"\n  Phase 2 complete:")
    print(f"    With coordinates: {len(coords)} / {total} ({len(coords)*100//total}%)")
    print(f"    With services:    {len(services_data)} / {total} ({len(services_data)*100//total}%)")
    print(f"    Errors:           {errors}")
    print(f"    Time:             {elapsed:.0f} seconds ({elapsed/60:.1f} minutes)")

    return coords, services_data


# ======================================================================
#  PHASE 3: STANDARDIZE AND EXPORT
# ======================================================================

def classify_ownership(owner_str):
    """Map KMHFR owner names to standardized ownership categories."""
    if not owner_str:
        return ""
    if "Ministry" in owner_str or "Government" in owner_str:
        return "Public"
    if "Private" in owner_str:
        return "Private"
    if any(kw in owner_str for kw in ("Faith", "Church", "Mission")):
        return "Faith-Based"
    if "NGO" in owner_str:
        return "NGO"
    return owner_str[:40]


def validate_kenya_coords(lat_str, lon_str):
    """
    Validate that coordinates fall within Kenya's bounding box.
    Returns (lat, lon) strings if valid, else ('', '').
    """
    try:
        lat = float(lat_str)
        lon = float(lon_str)
        b = KENYA_BOUNDS
        if b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]:
            return lat_str, lon_str
    except (ValueError, TypeError):
        pass
    return "", ""


def phase3_export(all_facilities, coords, services_data):
    """
    Phase 3: Build standardized CSVs from the scraped data.

    Output files:
      - kenya_standardized.csv: One row per facility
        Columns: facility_name, facility_code, facility_type,
                 facility_ownership, latitude, longitude, admin1, status

      - kenya_services.csv: One row per service per facility (long format)
        Columns: facility_code, service_category, service_group, service_detail
    """
    print("\n" + "=" * 60)
    print("  PHASE 3: Standardizing and exporting")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Build facility registry CSV ──
    rows = []
    for fac in all_facilities.values():
        lat, lon = "", ""
        if fac["id"] in coords:
            lat, lon = validate_kenya_coords(*coords[fac["id"]])

        rows.append({
            "facility_name": fac["name"],
            "facility_code": fac.get("code", ""),
            "facility_type": fac.get("facility_type", ""),
            "facility_ownership": classify_ownership(fac.get("owner", "")),
            "latitude": lat,
            "longitude": lon,
            "admin1": fac.get("county", ""),
            "status": "Operating" if fac.get("status") == "Operational" else fac.get("status", ""),
        })

    fac_path = os.path.join(OUTPUT_DIR, "kenya_standardized.csv")
    with open(fac_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "facility_name", "facility_code", "facility_type",
            "facility_ownership", "latitude", "longitude", "admin1", "status",
        ])
        writer.writeheader()
        writer.writerows(rows)

    with_coords = sum(1 for r in rows if r["latitude"])
    print(f"  Wrote {fac_path}")
    print(f"    Total facilities:  {len(rows)}")
    print(f"    With coordinates:  {with_coords}")
    print(f"    Without coords:    {len(rows) - with_coords}")

    # ── Build services CSV (long format) ──
    svc_rows = []
    for fac in all_facilities.values():
        if fac["id"] in services_data:
            code = fac.get("code", "")
            for svc in services_data[fac["id"]]:
                svc_rows.append({
                    "facility_code": code,
                    "service_category": svc.get("category", ""),
                    "service_group": svc.get("category", ""),
                    "service_detail": svc.get("name", ""),
                })

    svc_path = os.path.join(OUTPUT_DIR, "kenya_services.csv")
    with open(svc_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "facility_code", "service_category", "service_group", "service_detail",
        ])
        writer.writeheader()
        writer.writerows(svc_rows)

    # Count unique categories
    categories = set(s["service_category"] for s in svc_rows if s["service_category"])

    print(f"  Wrote {svc_path}")
    print(f"    Service records:    {len(svc_rows)}")
    print(f"    Service categories: {len(categories)}")

    # ── Print top categories ──
    cat_counts = {}
    for s in svc_rows:
        c = s["service_category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1
    print(f"\n  Top 10 service categories:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {cat:50s} {count:>6,}")

    # ── Save intermediate JSON (for debugging/reprocessing) ──
    json_path = os.path.join(OUTPUT_DIR, "kenya_facilities_raw.json")
    with open(json_path, "w") as f:
        json.dump(list(all_facilities.values()), f, indent=2)
    print(f"\n  Saved raw JSON: {json_path}")

    coords_path = os.path.join(OUTPUT_DIR, "kenya_coords.json")
    with open(coords_path, "w") as f:
        json.dump(coords, f)
    print(f"  Saved coordinates: {coords_path}")

    svcs_path = os.path.join(OUTPUT_DIR, "kenya_services_raw.json")
    with open(svcs_path, "w") as f:
        json.dump(services_data, f)
    print(f"  Saved raw services: {svcs_path}")

    # ── County summary ──
    county_counts = {}
    for r in rows:
        c = r["admin1"]
        if c:
            county_counts[c] = county_counts.get(c, 0) + 1
    print(f"\n  Facilities by county ({len(county_counts)} counties):")
    for county, count in sorted(county_counts.items(), key=lambda x: -x[1]):
        print(f"    {county:30s} {count:>5,}")

    return rows, svc_rows


# ======================================================================
#  MAIN
# ======================================================================

def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  KMHFR DATA EXTRACTION - HealthScope Intelligence      ║")
    print("║  Author: Kasim Chambulilo                               ║")
    print("║  Source: https://kmhfr.health.go.ke/public/facilities   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    total_start = time.time()

    # Phase 1: Get all facility listings
    all_facilities = phase1_scrape_listings()

    # Phase 2: Get coordinates + services from detail pages
    coords, services_data = phase2_scrape_details(all_facilities)

    # Phase 3: Standardize and export
    rows, svc_rows = phase3_export(all_facilities, coords, services_data)

    # Final summary
    total_elapsed = time.time() - total_start
    print("\n" + "=" * 60)
    print("  EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  Total facilities:     {len(rows):,}")
    print(f"  With GPS coordinates: {sum(1 for r in rows if r['latitude']):,}")
    print(f"  Service records:      {len(svc_rows):,}")
    print(f"  Total time:           {total_elapsed/60:.1f} minutes")
    print(f"  Output directory:     {os.path.abspath(OUTPUT_DIR)}")
    print()
    print("  Output files:")
    print(f"    - {OUTPUT_DIR}/kenya_standardized.csv")
    print(f"    - {OUTPUT_DIR}/kenya_services.csv")
    print(f"    - {OUTPUT_DIR}/kenya_facilities_raw.json")
    print(f"    - {OUTPUT_DIR}/kenya_coords.json")
    print(f"    - {OUTPUT_DIR}/kenya_services_raw.json")
    print()


if __name__ == "__main__":
    main()
