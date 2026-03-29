"""
Westchester Parcels Map Generator
Downloads GeoJSON for a municipality and renders an interactive Folium map.
"""

import json
import urllib.request
import urllib.parse
import time
import sys
import os

BASE_URL = "https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Westchester_County_Parcels/FeatureServer/0/query"
PAGE_SIZE = 1000
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'westchester-parcels')

# Property class descriptions
PROP_CLASSES = {
    '210': ('1-Family Res', '#2ecc71'),
    '220': ('2-Family Res', '#3498db'),
    '230': ('3-Family Res', '#9b59b6'),
    '310': ('Res Vacant', '#f1c40f'),
    '311': ('Vacant Land', '#e67e22'),
    '312': ('Rural Vacant', '#d35400'),
    '330': ('Res w/Com', '#1abc9c'),
    '411': ('Apartments', '#e74c3c'),
    '482': ('Restaurant', '#c0392b'),
    '620': ('Shopping Ctr', '#8e44ad'),
    '692': ('Parking', '#7f8c8d'),
    '963': ('Park/Rec', '#27ae60'),
}

def download_municipality(muni_name, fields="OBJECTID,MUNI_NAME,PARCEL_ADDR,PRIMARY_OWNER,PROP_CLASS,TOTAL_AV,LAND_AV,ACRES,YR_BLT"):
    """Download all parcels for a municipality."""
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


def render_map(geojson_path, muni_name):
    """Render an interactive Folium map from GeoJSON."""
    import folium
    from folium.plugins import MarkerCluster
    
    with open(geojson_path, 'r') as f:
        data = json.load(f)
    
    features = data.get("features", [])
    print("Rendering %d parcels..." % len(features))
    
    # Calculate center
    all_coords = []
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") == "Polygon":
            for ring in geom.get("coordinates", []):
                all_coords.extend(ring)
    
    if not all_coords:
        print("No coordinates found!")
        return
    
    center_lat = sum(c[1] for c in all_coords) / len(all_coords)
    center_lon = sum(c[0] for c in all_coords) / len(all_coords)
    
    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="cartodbpositron")
    
    # Style function by property class
    def style_function(feat):
        props = feat.get("properties", {})
        pclass = props.get("PROP_CLASS", "")
        _, color = PROP_CLASSES.get(pclass, ("Other", "#95a5a6"))
        return {
            "fillColor": color,
            "color": "#2c3e50",
            "weight": 0.5,
            "fillOpacity": 0.6,
        }
    
    # Add parcels
    folium.GeoJson(
        data,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["PARCEL_ADDR", "PRIMARY_OWNER", "PROP_CLASS", "TOTAL_AV"],
            aliases=["Address", "Owner", "Class", "Total AV"],
            localize=True,
        ),
        popup=folium.GeoJsonPopup(
            fields=["PARCEL_ADDR", "PRIMARY_OWNER", "PROP_CLASS", "TOTAL_AV", "LAND_AV", "ACRES"],
            aliases=["Address", "Owner", "Class", "Total AV ($)", "Land AV ($)", "Acres"],
        ),
    ).add_to(m)
    
    # Legend
    legend_html = '<div style="position:fixed;bottom:30px;left:30px;background:white;padding:12px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.3);z-index:1000;font-size:12px;"><b>Property Class</b><br>'
    for code, (desc, color) in sorted(PROP_CLASSES.items()):
        legend_html += '<span style="background:%s;width:12px;height:12px;display:inline-block;margin-right:4px;"></span>%s (%s)<br>' % (color, desc, code)
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Title
    title_html = '<div style="position:fixed;top:10px;left:10px;right:10px;text-align:center;background:white;padding:8px 16px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.3);z-index:1000;font-size:16px;font-weight:bold;">' + muni_name + ' &mdash; ' + str(len(features)) + ' Parcels</div>'
    m.get_root().html.add_child(folium.Element(title_html))
    
    out_path = os.path.join(OUTPUT_DIR, "%s_parcels_map.html" % muni_name.replace(" ", "_"))
    m.save(out_path)
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print("Map saved: %s (%.1f MB)" % (out_path, size_mb))
    return out_path


if __name__ == "__main__":
    muni = sys.argv[1] if len(sys.argv) > 1 else "Scarsdale"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    geojson_path = os.path.join(OUTPUT_DIR, "%s_parcels.geojson" % muni.replace(" ", "_"))
    
    if not os.path.exists(geojson_path):
        print("Downloading %s parcels..." % muni)
        data = download_municipality(muni)
        with open(geojson_path, 'w') as f:
            json.dump(data, f)
        print("Saved: %s (%d features)" % (geojson_path, len(data['features'])))
    else:
        print("Using cached: %s" % geojson_path)
    
    render_map(geojson_path, muni)
