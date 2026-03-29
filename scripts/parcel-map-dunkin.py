"""
Dunkin' Donuts Site Selection Map
Highlights parcels suitable for a Dunkin' location based on:
- Commercial zoning (LBCS 2000)
- Vacant commercial land (potential development)
- Lot size 0.1-0.5 acres (typical Dunkin' footprint)
- Road frontage
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

# Dunkin'-suitable property classes
# Commercial classes in NYS RPSV system
COMMERCIAL_CLASSES = {
    # Shopping/retail
    '411': 'Apartments (mixed-use potential)',
    '412': 'Apts over store',
    '414': 'Row houses/commercial',
    '415': 'Coop/condo apt commercial',
    '416': 'Condo/apt complex',
    '417': 'Garden apts',
    '418': 'Lg conv bldg',
    '420': 'Other apartment',
    # Commercial
    '430': 'Vacant commercial',
    '431': 'Vacant w/improvements',
    '432': 'Commercial (improved)',
    '433': 'Underwater commercial',
    '434': 'Commercial condo unit',
    '435': 'Patio/gazebo commercial',
    '436': 'Hotel/motel',
    '437': 'Professional building',
    '438': 'Parking',
    '439': 'Residence with commercial',
    '440': 'Diner/restaurant',
    '441': 'Diner/franchise restaurant',
    '442': 'Diners w/parking',
    '443': 'Restaurant/residence',
    '447': 'Nightclub',
    '448': 'Bar/tavern',
    '449': 'Fast food franchise',
    '450': 'Bank',
    '451': 'Bank w/drive-thru',
    '452': 'Bank/residence',
    '453': 'Bank with parking',
    '454': 'Insurance company',
    '460': 'Service station',
    '461': 'Service station w/store',
    '462': 'Service station w/parking',
    '463': 'Car wash',
    '464': 'Parking garage',
    '465': 'Parking lot',
    '467': 'Auto repair',
    '468': 'Car dealer',
    '470': 'Clinic/medical',
    '471': 'Professional services',
    '472': 'Offices',
    '473': 'Small office',
    '474': 'Professional bldg',
    '475': 'Funeral home',
    '476': 'Animal hospital',
    '477': 'Small retail',
    '478': 'Mid-size retail',
    '479': 'Large retail',
    '480': 'Supermarket',
    '481': 'Small supermarket',
    '482': 'Restaurant (chain)',
    '483': 'Shopping center',
    '484': 'Mini-mall',
    '485': 'Department store',
    '486': 'Regional mall',
    '487': 'Neighborhood center',
    '488': 'Community center',
    '489': 'Strip mall',
    '490': 'Bowling alley',
    '491': 'Marina',
    '492': 'Amusement',
    '493': 'Race track',
    '494': 'Fitness center',
    '495': 'Stadium',
    '496': 'Golf course (commercial)',
    '497': 'Resort',
    '498': 'Campground (commercial)',
    '499': 'Theater',
}

# Ideal Dunkin' property classes (highest suitability)
IDEAL_CLASSES = {
    '430', '432', '440', '441', '442', '443', '449',  # Commercial vacant/restaurants
    '450', '451', '452', '453',  # Banks (drive-thru compatible)
    '460', '461', '462',  # Gas stations (corner/high traffic)
    '477', '478', '479',  # Retail small/med/large
    '482', '483', '484',  # Restaurant/shopping center
    '487', '488', '489',  # Strip/neighborhood centers
}

# Good secondary classes
SECONDARY_CLASSES = {
    '411', '412', '414', '415', '416', '417', '418', '420',  # Multi-family (mixed-use)
    '431', '434', '435', '436', '437',  # Other commercial
    '464', '465',  # Parking
    '470', '471', '472', '473', '474',  # Offices
    '480', '481',  # Supermarkets
}

# High-traffic road keywords (Westchester major corridors)
MAJOR_ROADS = [
    'BROADWAY', 'MAIN ST', 'CENTRAL AVE', 'TARRYTOWN RD', 'WHITE PLAINS RD',
    'BOSTON POST RD', 'ROUTE', 'RT-', 'SAW MILL', 'HUTCHINSON', 'CROSS',
    'HILLSDALE', 'KING ST', 'MAMARONECK AVE', 'TUCKAHOE RD', 'ASHFORD',
    'EASTCHESTER', 'GRASSLANDS', 'NEPPERHAN', 'YONKERS AVE',
    'SOUTH BROADWAY', 'NORTH BROADWAY', 'RTE ', 'RT ',
    'STEVENS AVE', 'PROSPECT AVE', 'WARBURTON AVE', 'RIDGE',
]

def is_major_road(street_name):
    """Check if a street is a major traffic corridor."""
    if not street_name:
        return False
    street = street_name.upper()
    return any(road in street for road in MAJOR_ROADS)


def score_dunkin_suitability(props):
    """Score a parcel's suitability for a Dunkin' location. Returns (score, tier)."""
    pclass = str(props.get('PROP_CLASS') or '').strip()
    acres = float(props.get('ACRES') or 0)
    street = str(props.get('LOC_STREET') or '').strip()
    
    score = 0
    tier = 'background'
    
    # Class suitability
    if pclass in IDEAL_CLASSES:
        score += 40
    elif pclass in SECONDARY_CLASSES:
        score += 20
    elif pclass.startswith('4') or pclass.startswith('6'):
        score += 10
    else:
        return 0, 'background'
    
    # Size suitability (Dunkin' wants 0.1 - 0.5 acres ideally)
    if 0.08 <= acres <= 0.8:
        score += 30
    elif 0.05 <= acres <= 1.5:
        score += 15
    elif acres > 1.5:
        score += 5  # Too big, but could subdivide
    
    # Road frontage
    if is_major_road(street):
        score += 30
    elif street:
        score += 10
    
    # Tier determination
    if score >= 70:
        tier = 'prime'
    elif score >= 40:
        tier = 'suitable'
    
    return score, tier


def download_municipality(muni_name):
    """Download all parcels for a municipality."""
    fields = "OBJECTID,MUNI_NAME,PARCEL_ADDR,PRIMARY_OWNER,PROP_CLASS,TOTAL_AV,LAND_AV,ACRES,YR_BLT,LOC_STREET,LOC_ST_NBR"
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


def render_dunkin_map(geojson_path, muni_name):
    """Render Dunkin' site selection map."""
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    print("Analyzing %d parcels for Dunkin' suitability..." % len(features))

    fig, ax = plt.subplots(1, 1, figsize=(22, 17), dpi=150)
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')

    patches = []
    colors = []
    edge_colors = []
    edge_widths = []
    prime_count = 0
    suitable_count = 0
    background_count = 0

    prime_sites = []

    for feat in features:
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})

        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue

        score, tier = score_dunkin_suitability(props)
        pclass = str(props.get('PROP_CLASS') or '').strip()
        street = props.get('LOC_STREET', '')
        addr = props.get('PARCEL_ADDR', '')
        acres = float(props.get('ACRES') or 0)

        if tier == 'prime':
            color = '#FF4444'
            edge = '#FF0000'
            ew = 1.5
            prime_count += 1
            prime_sites.append({
                'addr': addr or '%s %s' % (props.get('LOC_ST_NBR',''), street),
                'owner': props.get('PRIMARY_OWNER', ''),
                'class': pclass,
                'acres': acres,
                'score': score
            })
        elif tier == 'suitable':
            color = '#FFB347'
            edge = '#FF8C00'
            ew = 0.6
            suitable_count += 1
        else:
            # Background — show all commercial as dim, hide non-commercial
            if pclass.startswith('4') or pclass.startswith('6'):
                color = '#3d3d5c'
                edge = '#2d2d4c'
                ew = 0.1
                background_count += 1
            else:
                color = '#1e1e3a'
                edge = '#1a1a30'
                ew = 0.05

        try:
            poly = shape(geom)
            if poly.is_valid and not poly.is_empty:
                if poly.geom_type == "Polygon":
                    patches.append(plt.Polygon(list(poly.exterior.coords), closed=True))
                    colors.append(color)
                    edge_colors.append(edge)
                    edge_widths.append(ew)
                elif poly.geom_type == "MultiPolygon":
                    for p in poly.geoms:
                        patches.append(plt.Polygon(list(p.exterior.coords), closed=True))
                        colors.append(color)
                        edge_colors.append(edge)
                        edge_widths.append(ew)
        except Exception:
            continue

    if patches:
        p = PatchCollection(patches, facecolors=colors, edgecolors=edge_colors,
                           linewidths=edge_widths, alpha=0.85)
        ax.add_collection(p)

    ax.autoscale_view()
    ax.set_aspect('equal')

    # Title
    ax.set_title("🍩 Dunkin' Site Selection — %s" % muni_name,
                fontsize=24, fontweight='bold', pad=20, color='white')

    # Legend
    legend_patches = [
        mpatches.Patch(color='#FF4444', label='⭐ PRIME — Highly Suitable (score ≥70)'),
        mpatches.Patch(color='#FFB347', label='✓ Suitable — Good Potential (score 40-69)'),
        mpatches.Patch(color='#3d3d5c', label='Commercial — Background'),
        mpatches.Patch(color='#1e1e3a', label='Residential/Other'),
    ]
    leg = ax.legend(handles=legend_patches, loc='lower left', fontsize=11,
                   framealpha=0.9, title='Site Suitability', title_fontsize=13,
                   edgecolor='#555555', facecolor='#1a1a2e', labelcolor='white')
    leg.get_title().set_color('white')

    # Stats box
    total = len(features)
    stats = ("Parcels analyzed: %d\n"
             "⭐ Prime sites: %d\n"
             "✓ Suitable sites: %d\n"
             "Criteria: Commercial zone,\n"
             "0.1-0.8 acres, road frontage") % (total, prime_count, suitable_count)
    ax.text(0.98, 0.02, stats, transform=ax.transAxes, fontsize=11,
           verticalalignment='bottom', horizontalalignment='right',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a1a2e', edgecolor='#FF4444',
                    alpha=0.95), color='white')

    ax.set_xlabel('Longitude', fontsize=10, color='#888888')
    ax.set_ylabel('Latitude', fontsize=10, color='#888888')
    ax.tick_params(colors='#666666')

    out_path = os.path.join(OUTPUT_DIR, '%s_dunkin_map.png' % muni_name.replace(" ", "_"))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    size_kb = os.path.getsize(out_path) / 1024
    print("Map saved: %s (%.0f KB)" % (out_path, size_kb))

    # Print top prime sites
    print("\n=== TOP PRIME SITES ===")
    for site in sorted(prime_sites, key=lambda x: -x['score'])[:15]:
        print("  Score: %d | %s | %s | Class: %s | %.2f ac" % (
            site['score'], site['addr'][:40], site['owner'][:25], site['class'], site['acres']))

    return out_path, prime_sites


if __name__ == "__main__":
    muni = sys.argv[1] if len(sys.argv) > 1 else "Scarsdale"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    geojson_path = os.path.join(OUTPUT_DIR, '%s_parcels.geojson' % muni.replace(" ", "_"))

    if not os.path.exists(geojson_path):
        print("Downloading %s parcels..." % muni)
        data = download_municipality(muni)
        with open(geojson_path, 'w') as f:
            json.dump(data, f)
    else:
        print("Using cached: %s" % geojson_path)

    render_dunkin_map(geojson_path, muni)
