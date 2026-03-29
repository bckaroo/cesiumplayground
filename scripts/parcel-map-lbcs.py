"""
Westchester Parcels Map Generator — LBCS Standards
Uses APA Land-Based Classification Standards (Activity dimension) for color coding.
Maps NY RPSV property class codes to LBCS activity categories.
"""

import json
import urllib.request
import urllib.parse
import time
import sys
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
from shapely.geometry import shape

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'westchester-parcels')
BASE_URL = "https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Westchester_County_Parcels/FeatureServer/0/query"
PAGE_SIZE = 1000

# ============================================================================
# LBCS Activity Dimension — Official APA Color Codes
# Source: https://www.planning.org/lbcs/standards/activity/
# ============================================================================
LBCS_ACTIVITY = {
    '1000': ('Residential',              '#FFFF00', 'Residential activities'),
    '2000': ('Commercial/Business',      '#FF0000', 'Shopping, business, or trade activities'),
    '3000': ('Industrial',               '#A020F0', 'Industrial, manufacturing, waste-related'),
    '4000': ('Institutional',            '#0000FF', 'Social, institutional, infrastructure-related'),
    '5000': ('Transportation',           '#BEBEBE', 'Travel or movement activities'),
    '6000': ('Assembly',                 '#2F4F4F', 'Mass assembly of people'),
    '7000': ('Recreation/Leisure',       '#90EE90', 'Leisure activities'),
    '8000': ('Conservation',             '#228B22', 'Natural resources-related activities'),
    '9000': ('Vacant/Undeveloped',       '#D3D3D3', 'No human activity or unclassifiable'),
}

# ============================================================================
# NY RPSV Property Class → LBCS Activity Code Mapping
# Westchester County uses NYS Office of Real Property Tax Service codes
# ============================================================================
def map_rpsv_to_lbcs(prop_class):
    """Map NYS RPSV property class to LBCS Activity top-level code."""
    if not prop_class:
        return '9000'
    pc = str(prop_class).strip()

    # --- 100-199: Agricultural (LBCS 8000 - Conservation/Natural Resources) ---
    if pc.startswith('1'):
        return '8000'

    # --- 200-299: Residential (LBCS 1000) ---
    if pc.startswith('2'):
        if pc in ('310', '311', '312'):
            return '9000'  # Residential vacant → Vacant
        return '1000'

    # --- 300-399: Vacant Land (LBCS 9000) ---
    if pc.startswith('3'):
        return '9000'

    # --- 400-499: Commercial (LBCS 2000) ---
    if pc.startswith('4'):
        return '2000'

    # --- 500-599: Recreation/Tourist (LBCS 7000) ---
    if pc.startswith('5'):
        if pc in ('530', '531', '532', '533', '534'):
            return '8000'  # Forest/wildlife → Conservation
        return '7000'

    # --- 600-699: Community Services (mixed LBCS) ---
    if pc.startswith('6'):
        if pc in ('610', '612', '614', '615', '620', '621', '622', '630', '631', '632'):
            return '2000'  # Stores, shops, restaurants, banks → Commercial
        if pc in ('640', '641', '642', '643', '644', '649'):
            return '2000'  # Offices → Commercial
        if pc in ('650', '651', '652', '653'):
            return '2000'  # Auto-related → Commercial
        if pc in ('660', '661', '662', '663', '664', '665', '669'):
            return '2000'  # Misc commercial → Commercial
        if pc in ('670', '671', '672', '673'):
            return '3000'  # Industrial/commercial mix
        if pc in ('680', '681', '682', '683', '684', '685'):
            return '2000'  # Misc services → Commercial
        if pc in ('691', '692'):
            return '2000'  # Parking → Commercial
        return '2000'

    # --- 700-799: Industrial (LBCS 3000) ---
    if pc.startswith('7'):
        return '3000'

    # --- 800-899: Public Services (LBCS 4000) ---
    if pc.startswith('8'):
        if pc in ('820', '821', '822'):
            return '4000'  # Education
        if pc in ('830', '831', '832'):
            return '4000'  # Health
        if pc in ('840', '841', '842', '843', '844'):
            return '5000'  # Transportation
        if pc in ('850', '851', '852', '853'):
            return '4000'  # Utilities
        if pc in ('860', '861', '862'):
            return '4000'  # Cemeteries
        return '4000'

    # --- 900-999: Wild/Forest/Wetlands/Parks (mixed LBCS) ---
    if pc.startswith('9'):
        if pc in ('910', '911', '912'):
            return '5000'  # Roads/railroads
        if pc in ('920', '921', '922'):
            return '5000'  # Underwater/riparian
        if pc in ('930', '931', '932'):
            return '8000'  # Forest
        if pc in ('940', '941', '942'):
            return '8000'  # Wild/DBO
        if pc in ('950', '951', '952'):
            return '8000'  # State forest
        if pc in ('960', '961', '962', '963', '964', '965', '970', '971', '972'):
            return '7000'  # Parks/recreation
        if pc in ('980', '981', '982'):
            return '8000'  # Fish/game management
        return '8000'

    return '9000'


def download_municipality(muni_name):
    """Download all parcels for a municipality."""
    fields = "OBJECTID,MUNI_NAME,PARCEL_ADDR,PRIMARY_OWNER,PROP_CLASS,TOTAL_AV,LAND_AV,ACRES,YR_BLT"
    features = []
    offset = 0

    while True:
        params = {
            "where": "MUNI_NAME='%s'" % muni_name,
            "outFields": fields,
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "f": "geojson",
            "orderByFields": "OBJECTID"
        }
        url = BASE_URL + "?" + urllib.parse.urlencode(params)

        print("  Fetching offset %d..." % offset, end="", flush=True)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(" ERROR: %s" % e)
            break

        batch = data.get("features", [])
        features.extend(batch)
        print(" %d rows (total: %d)" % (len(batch), len(features)))

        if not data.get("properties", {}).get("exceededTransferLimit", False):
            break
        offset += PAGE_SIZE
        time.sleep(0.3)

    return {"type": "FeatureCollection", "features": features}


def render_lbcs_map(geojson_path, muni_name):
    """Render a static map using LBCS Activity color codes."""
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    print("Rendering %d parcels with LBCS colors..." % len(features))

    fig, ax = plt.subplots(1, 1, figsize=(22, 17), dpi=150)
    fig.patch.set_facecolor('#f8f8f8')
    ax.set_facecolor('#e0e0e0')

    patches = []
    colors = []
    lbcs_counts = {}

    for feat in features:
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        pclass = props.get("PROP_CLASS", "")

        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue

        lbcs_code = map_rpsv_to_lbcs(pclass)
        lbcs_name, color, _ = LBCS_ACTIVITY.get(lbcs_code, ('Unknown', '#999999', ''))
        lbcs_counts[lbcs_code] = lbcs_counts.get(lbcs_code, 0) + 1

        try:
            poly = shape(geom)
            if poly.is_valid and not poly.is_empty:
                if poly.geom_type == "Polygon":
                    patches.append(plt.Polygon(list(poly.exterior.coords), closed=True))
                    colors.append(color)
                elif poly.geom_type == "MultiPolygon":
                    for p in poly.geoms:
                        patches.append(plt.Polygon(list(p.exterior.coords), closed=True))
                        colors.append(color)
        except Exception:
            continue

    if patches:
        p = PatchCollection(patches, facecolors=colors, edgecolors='#333333',
                           linewidths=0.12, alpha=0.8)
        ax.add_collection(p)

    ax.autoscale_view()
    ax.set_aspect('equal')

    # Title
    ax.set_title('%s — LBCS Activity Classification' % muni_name,
                fontsize=24, fontweight='bold', pad=20)

    # Subtitle
    ax.text(0.5, 1.01, 'APA Land-Based Classification Standards (%d parcels)' % len(features),
           transform=ax.transAxes, fontsize=12, ha='center', va='bottom',
           color='#555555', style='italic')

    # Legend — only show categories present in data
    legend_patches = []
    for code in sorted(lbcs_counts.keys()):
        name, color, desc = LBCS_ACTIVITY.get(code, ('?', '#999', ''))
        count = lbcs_counts[code]
        pct = count / len(features) * 100
        legend_patches.append(mpatches.Patch(
            color=color,
            label='%s (%s) — %d parcels (%.1f%%)' % (name, code, count, pct)
        ))

    ax.legend(handles=legend_patches, loc='lower left', fontsize=10,
             framealpha=0.95, title='LBCS Activity', title_fontsize=12,
             edgecolor='#cccccc')

    # Stats
    total_av = sum(float(f.get("properties",{}).get("TOTAL_AV") or 0) for f in features)
    stats_text = 'Parcels: %d\nTotal Assessed Value: $%.1fM\nSource: Westchester County ArcGIS' % (
        len(features), total_av / 1e6)
    ax.text(0.98, 0.02, stats_text, transform=ax.transAxes, fontsize=11,
           verticalalignment='bottom', horizontalalignment='right',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#cccccc', alpha=0.95))

    # LBCS source note
    ax.text(0.98, 0.98, 'Color Standard: APA LBCS\nplanning.org/lbcs/standards',
           transform=ax.transAxes, fontsize=9, ha='right', va='top',
           color='#888888')

    ax.set_xlabel('Longitude', fontsize=10)
    ax.set_ylabel('Latitude', fontsize=10)

    out_path = os.path.join(OUTPUT_DIR, '%s_lbcs_map.png' % muni_name.replace(" ", "_"))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    size_kb = os.path.getsize(out_path) / 1024
    print("Map saved: %s (%.0f KB)" % (out_path, size_kb))
    return out_path


if __name__ == "__main__":
    muni = sys.argv[1] if len(sys.argv) > 1 else "Scarsdale"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    geojson_path = os.path.join(OUTPUT_DIR, '%s_parcels.geojson' % muni.replace(" ", "_"))

    if not os.path.exists(geojson_path):
        print("Downloading %s parcels..." % muni)
        data = download_municipality(muni)
        with open(geojson_path, 'w') as f:
            json.dump(data, f)
        print("Saved: %s (%d features)" % (geojson_path, len(data['features'])))
    else:
        print("Using cached: %s" % geojson_path)

    render_lbcs_map(geojson_path, muni)
