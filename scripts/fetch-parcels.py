"""
Westchester County Parcels — ArcGIS FeatureServer Downloader
Pulls all 257K+ parcels in paginated chunks.

Usage:
  python fetch-parcels.py csv          # Attributes only (fast, ~50MB)
  python fetch-parcels.py geojson      # With geometry (large, ~1GB+)
  python fetch-parcels.py parquet      # Attributes as Parquet (efficient)
"""

import json
import csv
import sys
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Westchester_County_Parcels/FeatureServer/0/query"
PAGE_SIZE = 1000
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "westchester-parcels"

# Non-geometry fields for CSV/Parquet export
ATTR_FIELDS = [
    "OBJECTID", "COUNTY_NAME", "MUNI_NAME", "SWIS", "PARCEL_ADDR",
    "PRINT_KEY", "SBL", "CITYTOWN_NAME", "CITYTOWN_SWIS",
    "LOC_ST_NBR", "LOC_STREET", "LOC_UNIT", "LOC_ZIP",
    "PROP_CLASS", "ROLL_SECTION",
    "LAND_AV", "TOTAL_AV", "FULL_MARKET_VAL",
    "YR_BLT", "FRONT", "DEPTH", "SQ_FT", "ACRES",
    "SCHOOL_CODE", "SCHOOL_NAME",
    "SEWER_TYPE", "SEWER_DESC", "WATER_SUPPLY", "WATER_DESC",
    "UTILITIES", "UTILITIES_DESC",
    "BLDG_STYLE", "BLDG_STYLE_DESC", "HEAT_TYPE", "HEAT_TYPE_DESC",
    "FUEL_TYPE", "FUEL_TYPE_DESC",
    "SQFT_LIVING", "GFA", "NBR_KITCHENS", "NBR_FULL_BATHS", "NBR_BEDROOMS",
    "USED_AS_CODE", "USED_AS_DESC", "AG_DIST_CODE", "AG_DIST_NAME",
    "PRIMARY_OWNER", "MAIL_ADDR", "PO_BOX", "MAIL_CITY", "MAIL_STATE", "MAIL_ZIP",
    "ADD_OWNER", "ADD_MAIL_ADDR", "ADD_MAIL_PO_BOX",
    "ADD_MAIL_CITY", "ADD_MAIL_STATE", "ADD_MAIL_ZIP",
    "BOOK", "PAGE", "GRID_EAST", "GRID_NORTH",
    "MUNI_PARCEL_ID", "SWIS_SBL_ID", "SWIS_PRINT_KEY_ID",
    "ROLL_YR", "SPATIAL_YR", "OWNER_TYPE",
    "NYS_NAME", "NYS_NAME_SOURCE", "DUP_GEO",
    "CALC_ACRES", "Shape__Area", "Shape__Length"
]

def fetch_page(offset, out_fields="*", return_geometry="false"):
    """Fetch a single page from the ArcGIS API."""
    params = {
        "where": "1=1",
        "outFields": out_fields,
        "returnGeometry": return_geometry,
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "json",
        "orderByFields": "OBJECTID"
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return data.get("features", [])
        except Exception as e:
            print(f"  Retry {attempt+1}/3 for offset {offset}: {e}")
            time.sleep(2 ** attempt)
    
    print(f"  FAILED at offset {offset}")
    return []


def fetch_count():
    """Get total record count."""
    url = BASE_URL + "?where=1=1&returnCountOnly=true&f=json"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        return data.get("count", 0)


def download_csv():
    """Download all attributes to CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "westchester_parcels.csv"
    
    count = fetch_count()
    print(f"Total parcels: {count:,}")
    print(f"Pages needed: {(count // PAGE_SIZE) + 1}")
    print(f"Output: {out_path}")
    
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ATTR_FIELDS)
        writer.writeheader()
        
        offset = 0
        fetched = 0
        while offset < count:
            print(f"  Fetching offset {offset:,}...", end="", flush=True)
            t0 = time.time()
            features = fetch_page(offset, out_fields=",".join(ATTR_FIELDS))
            elapsed = time.time() - t0
            
            if not features:
                print(" (empty, stopping)")
                break
            
            for feat in features:
                attrs = feat.get("attributes", {})
                writer.writerow(attrs)
            
            fetched += len(features)
            print(f" {len(features)} rows ({elapsed:.1f}s) — total: {fetched:,}/{count:,}")
            offset += PAGE_SIZE
            time.sleep(0.3)  # Be nice to the server
    
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\nDone! {fetched:,} parcels saved ({size_mb:.1f} MB)")


def download_geojson():
    """Download all parcels with geometry to GeoJSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "westchester_parcels.geojson"
    
    count = fetch_count()
    print(f"Total parcels: {count:,}")
    print(f"Pages needed: {(count // PAGE_SIZE) + 1}")
    print(f"Output: {out_path}")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write('{"type":"FeatureCollection","features":[\n')
        
        offset = 0
        fetched = 0
        first = True
        
        while offset < count:
            print(f"  Fetching offset {offset:,}...", end="", flush=True)
            t0 = time.time()
            
            params = {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
                "f": "geojson",
                "orderByFields": "OBJECTID"
            }
            url = BASE_URL + "?" + urllib.parse.urlencode(params)
            
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode())
            except Exception as e:
                print(f" ERROR: {e}")
                time.sleep(5)
                offset += PAGE_SIZE
                continue
            
            elapsed = time.time() - t0
            features = data.get("features", [])
            
            if not features:
                print(" (empty, stopping)")
                break
            
            for feat in features:
                if not first:
                    f.write(",\n")
                json.dump(feat, f)
                first = False
            
            fetched += len(features)
            print(f" {len(features)} rows ({elapsed:.1f}s) — total: {fetched:,}/{count:,}")
            offset += PAGE_SIZE
            time.sleep(0.5)  # GeoJSON is heavier, be gentler
        
        f.write("\n]}\n")
    
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\nDone! {fetched:,} parcels saved ({size_mb:.1f} MB)")


def download_parquet():
    """Download attributes to Parquet (requires pyarrow)."""
    try:
        import pyarrow as pa
        import pyarrow.csv as pcsv
    except ImportError:
        print("Installing pyarrow...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarrow", "-q"])
        import pyarrow as pa
        import pyarrow.csv as pcsv

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "westchester_parcels.parquet"
    
    # First download CSV, then convert
    csv_path = OUTPUT_DIR / "westchester_parcels.csv"
    if not csv_path.exists():
        print("Downloading CSV first...")
        download_csv()
    
    print(f"Converting to Parquet: {out_path}")
    table = pcsv.read_csv(str(csv_path))
    import pyarrow.parquet as pq
    pq.write_table(table, str(out_path), compression="snappy")
    
    csv_mb = os.path.getsize(csv_path) / (1024 * 1024)
    pq_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"CSV: {csv_mb:.1f} MB → Parquet: {pq_mb:.1f} MB (ratio: {csv_mb/pq_mb:.1f}x)")


if __name__ == "__main__":
    fmt = sys.argv[1] if len(sys.argv) > 1 else "csv"
    
    if fmt == "csv":
        download_csv()
    elif fmt == "geojson":
        download_geojson()
    elif fmt == "parquet":
        download_parquet()
    else:
        print(f"Unknown format: {fmt}. Use csv, geojson, or parquet.")
