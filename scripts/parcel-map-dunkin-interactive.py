"""
Dunkin' Site Selection — Interactive Folium Map
Uses OpenStreetMap base layer for road context.
Overlays parcels color-coded by Dunkin' suitability.
"""

import json
import urllib.request
import urllib.parse
import time
import sys
import os
import folium
from folium.plugins import MarkerCluster

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'westchester-parcels')
BASE_URL = "https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Westchester_County_Parcels/FeatureServer/0/query"
PAGE_SIZE = 1000

# Dunkin' suitability scoring
IDEAL_CLASSES = {
    '430', '432', '440', '441', '442', '443', '449',
    '450', '451', '452', '453',
    '460', '461', '462',
    '477', '478', '479',
    '482', '483', '484', '487', '488', '489',
}
SECONDARY_CLASSES = {
    '411', '412', '414', '415', '416', '417', '418', '420',
    '431', '434', '435', '436', '437',
    '464', '465',
    '470', '471', '472', '473', '474',
    '480', '481',
}
MAJOR_ROADS = [
    'BROADWAY', 'MAIN ST', 'CENTRAL AVE', 'TARRYTOWN RD', 'WHITE PLAINS RD',
    'BOSTON POST RD', 'ROUTE', 'RT-', 'SAW MILL', 'HUTCHINSON', 'CROSS',
    'HILLSDALE', 'KING ST', 'MAMARONECK AVE', 'TUCKAHOE RD', 'ASHFORD',
    'EASTCHESTER', 'GRASSLANDS', 'NEPPERHAN', 'YONKERS AVE',
    'SOUTH BROADWAY', 'NORTH BROADWAY', 'RTE ', 'RT ',
    'STEVENS AVE', 'PROSPECT AVE', 'WARBURTON AVE', 'RIDGE',
]

COMMERCIAL_CLASSES = set(list(IDEAL_CLASSES) + list(SECONDARY_CLASSES) + [
    '438', '439', '447', '448', '454',
    '463', '467', '468',
    '475', '476',
    '485', '486', '490', '491', '492', '493', '494', '495', '496', '497', '498', '499',
])


def is_major_road(street):
    if not street:
        return False
    s = street.upper()
    return any(r in s for r in MAJOR_ROADS)


def score_dunkin(props):
    pclass = str(props.get('PROP_CLASS') or '').strip()
    acres = float(props.get('ACRES') or 0)
    street = str(props.get('LOC_STREET') or '').strip()

    score = 0
    if pclass in IDEAL_CLASSES:
        score += 40
    elif pclass in SECONDARY_CLASSES:
        score += 20
    elif pclass.startswith('4') or pclass.startswith('6'):
        score += 10
    else:
        return 0, 'other'

    if 0.08 <= acres <= 0.8:
        score += 30
    elif 0.05 <= acres <= 1.5:
        score += 15
    elif acres > 1.5:
        score += 5

    if is_major_road(street):
        score += 30
    elif street:
        score += 10

    if score >= 70:
        return score, 'prime'
    elif score >= 40:
        return score, 'suitable'
    return score, 'background'


def get_class_desc(pclass):
    DESCS = {
        '430': 'Vacant Commercial', '432': 'Commercial', '440': 'Restaurant',
        '441': 'Diner/Franchise', '449': 'Fast Food Franchise', '450': 'Bank',
        '451': 'Bank w/Drive-Thru', '452': 'Bank/Residence', '460': 'Gas Station',
        '461': 'Gas w/Store', '462': 'Gas w/Parking', '477': 'Small Retail',
        '478': 'Mid Retail', '479': 'Large Retail', '480': 'Supermarket',
        '482': 'Restaurant (Chain)', '483': 'Shopping Center', '484': 'Mini-Mall',
        '487': 'Neighborhood Ctr', '488': 'Community Ctr', '489': 'Strip Mall',
    }
    return DESCS.get(pclass, 'Class %s' % pclass)


def download_municipality(muni_name):
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


def render_dunkin_folium(geojson_path, muni_name):
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    print("Building Dunkin' map for %d parcels..." % len(features))

    # Calculate center
    all_coords = []
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") == "Polygon":
            for ring in geom.get("coordinates", []):
                all_coords.extend(ring)
        elif geom.get("type") == "MultiPolygon":
            for poly in geom.get("coordinates", []):
                for ring in poly:
                    all_coords.extend(ring)

    center_lat = sum(c[1] for c in all_coords) / len(all_coords)
    center_lon = sum(c[0] for c in all_coords) / len(all_coords)

    # Create map with OSM tiles
    m = folium.Map(location=[center_lat, center_lon], zoom_start=14,
                   tiles="OpenStreetMap")

    # Separate features by tier
    prime_features = []
    suitable_features = []
    commercial_features = []
    prime_sites = []

    for feat in features:
        props = feat.get("properties", {})
        pclass = str(props.get('PROP_CLASS') or '').strip()
        score, tier = score_dunkin(props)

        if tier == 'prime':
            prime_features.append(feat)
            addr = props.get('PARCEL_ADDR', '') or '%s %s' % (props.get('LOC_ST_NBR',''), props.get('LOC_STREET',''))
            prime_sites.append({
                'addr': addr,
                'owner': props.get('PRIMARY_OWNER', ''),
                'class': pclass,
                'class_desc': get_class_desc(pclass),
                'acres': float(props.get('ACRES') or 0),
                'score': score
            })
        elif tier == 'suitable':
            suitable_features.append(feat)
        elif pclass in COMMERCIAL_CLASSES:
            commercial_features.append(feat)

    # Add commercial background layer (dim)
    if commercial_features:
        bg_coll = {"type": "FeatureCollection", "features": commercial_features}
        folium.GeoJson(
            bg_coll,
            name='Commercial (background)',
            style_function=lambda x: {
                'fillColor': '#8888aa',
                'color': '#666688',
                'weight': 0.3,
                'fillOpacity': 0.25,
            },
            show=True,
        ).add_to(m)

    # Add suitable layer (orange)
    if suitable_features:
        suit_coll = {"type": "FeatureCollection", "features": suitable_features}
        folium.GeoJson(
            suit_coll,
            name='Suitable Sites',
            style_function=lambda x: {
                'fillColor': '#FFB347',
                'color': '#FF8C00',
                'weight': 1,
                'fillOpacity': 0.55,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['PARCEL_ADDR', 'PRIMARY_OWNER', 'PROP_CLASS', 'ACRES'],
                aliases=['Address', 'Owner', 'Class', 'Acres'],
            ),
            show=True,
        ).add_to(m)

    # Add prime layer (red, bold)
    if prime_features:
        prime_coll = {"type": "FeatureCollection", "features": prime_features}
        folium.GeoJson(
            prime_coll,
            name='PRIME Sites',
            style_function=lambda x: {
                'fillColor': '#FF2222',
                'color': '#CC0000',
                'weight': 2,
                'fillOpacity': 0.65,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['PARCEL_ADDR', 'PRIMARY_OWNER', 'PROP_CLASS', 'ACRES'],
                aliases=['Address', 'Owner', 'Class', 'Acres'],
            ),
            popup=folium.GeoJsonPopup(
                fields=['PARCEL_ADDR', 'PRIMARY_OWNER', 'PROP_CLASS', 'ACRES', 'TOTAL_AV'],
                aliases=['Address', 'Owner', 'Class', 'Acres', 'Total AV ($)'],
            ),
            show=True,
        ).add_to(m)

    # Add numbered markers for top 10 prime sites
    marker_cluster = MarkerCluster(name='Top Sites').add_to(m)
    for i, site in enumerate(sorted(prime_sites, key=lambda x: -x['score'])[:10]):
        # Find centroid for marker placement
        for feat in prime_features:
            addr = feat.get('properties',{}).get('PARCEL_ADDR','') or '%s %s' % (
                feat.get('properties',{}).get('LOC_ST_NBR',''),
                feat.get('properties',{}).get('LOC_STREET',''))
            if addr == site['addr']:
                geom = feat.get('geometry',{})
                if geom.get('type') == 'Polygon':
                    coords = geom['coordinates'][0]
                    clat = sum(c[1] for c in coords) / len(coords)
                    clon = sum(c[0] for c in coords) / len(coords)
                elif geom.get('type') == 'MultiPolygon':
                    coords = geom['coordinates'][0][0]
                    clat = sum(c[1] for c in coords) / len(coords)
                    clon = sum(c[0] for c in coords) / len(coords)
                else:
                    continue

                popup_html = '<div style="font-size:13px;"><b>#%d — Score: %d</b><br>%s<br>Owner: %s<br>Class: %s (%s)<br>Acres: %.2f</div>' % (
                    i+1, site['score'], site['addr'], site['owner'][:30],
                    site['class_desc'], site['class'], site['acres'])
                folium.Marker(
                    location=[clat, clon],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip='#%d: %s (score %d)' % (i+1, site['addr'][:30], site['score']),
                    icon=folium.DivIcon(
                        html='<div style="background:#FF2222;color:white;border-radius:50%%;width:24px;height:24px;text-align:center;line-height:24px;font-weight:bold;font-size:13px;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4);">%d</div>' % (i+1),
                        icon_size=(24, 24),
                        icon_anchor=(12, 12),
                    )
                ).add_to(marker_cluster)
                break

    # Layer control
    folium.LayerControl().add_to(m)

    # Title
    title_html = '<div style="position:fixed;top:10px;left:50pct;transform:translateX(-50pct);z-index:9999;background:rgba(0,0,0,0.8);color:white;padding:10px 20px;border-radius:8px;font-size:18px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3);">Dunkin\' Site Selection — %s</div>' % muni_name
    m.get_root().html.add_child(folium.Element(title_html.replace('50pct', '50%')))

    # Legend
    legend_html = '''<div style="position:fixed;bottom:30px;left:30px;z-index:9999;background:rgba(0,0,0,0.85);color:white;padding:14px 18px;border-radius:8px;font-size:12px;line-height:1.8;box-shadow:0 2px 6px rgba(0,0,0,0.3);">
    <b style="font-size:14px;">Dunkin' Suitability</b><br>
    <span style="background:#FF2222;width:14px;height:14px;display:inline-block;margin-right:6px;border-radius:3px;"></span>PRIME (score ≥70) — %d sites<br>
    <span style="background:#FFB347;width:14px;height:14px;display:inline-block;margin-right:6px;border-radius:3px;"></span>Suitable (score 40-69) — %d sites<br>
    <span style="background:#8888aa;width:14px;height:14px;display:inline-block;margin-right:6px;border-radius:3px;"></span>Commercial (background)<br>
    <hr style="border-color:#555;margin:6px 0;">
    <span style="color:#aaa;font-size:11px;">Click parcels for details • Numbered = top 10 sites</span>
    </div>''' % (len(prime_features), len(suitable_features))
    m.get_root().html.add_child(folium.Element(legend_html))

    out_path = os.path.join(OUTPUT_DIR, '%s_dunkin_interactive.html' % muni_name.replace(" ", "_"))
    m.save(out_path)
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print("Map saved: %s (%.1f MB)" % (out_path, size_mb))

    print("\n=== TOP PRIME SITES ===")
    for i, site in enumerate(sorted(prime_sites, key=lambda x: -x['score'])[:15]):
        print("  #%d Score:%d | %s | %s | %s | %.2f ac" % (
            i+1, site['score'], site['addr'][:35], site['owner'][:25],
            site['class_desc'], site['acres']))

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

    render_dunkin_folium(geojson_path, muni)
