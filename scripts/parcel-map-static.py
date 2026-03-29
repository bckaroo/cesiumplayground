"""
Static map renderer using matplotlib + geopandas
Generates a PNG map of Westchester parcels
"""

import json
import sys
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
from shapely.geometry import shape
import numpy as np

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

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'westchester-parcels')

def render_static_map(geojson_path, muni_name):
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    print("Rendering %d parcels..." % len(features))

    fig, ax = plt.subplots(1, 1, figsize=(20, 16), dpi=150)
    fig.patch.set_facecolor('#f5f5f5')
    ax.set_facecolor('#e8e8e8')

    patches = []
    colors = []

    for feat in features:
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        pclass = props.get("PROP_CLASS", "")

        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue

        try:
            poly = shape(geom)
            if poly.is_valid and not poly.is_empty:
                if poly.geom_type == "Polygon":
                    patches.append(plt.Polygon(list(poly.exterior.coords), closed=True))
                elif poly.geom_type == "MultiPolygon":
                    for p in poly.geoms:
                        patches.append(plt.Polygon(list(p.exterior.coords), closed=True))
                    
                _, color = PROP_CLASSES.get(pclass, ("Other", "#95a5a6"))
                if poly.geom_type == "Polygon":
                    colors.append(color)
                else:
                    for _ in poly.geoms:
                        colors.append(color)
        except Exception:
            continue

    if patches:
        p = PatchCollection(patches, facecolors=colors, edgecolors='#2c3e50',
                           linewidths=0.15, alpha=0.75)
        ax.add_collection(p)

    ax.autoscale_view()
    ax.set_aspect('equal')

    # Title
    ax.set_title('%s — %d Parcels' % (muni_name, len(features)),
                fontsize=22, fontweight='bold', pad=20)

    # Legend
    legend_patches = []
    for code in sorted(PROP_CLASSES.keys()):
        desc, color = PROP_CLASSES[code]
        count = sum(1 for f in features if f.get("properties",{}).get("PROP_CLASS","") == code)
        if count > 0:
            legend_patches.append(mpatches.Patch(color=color, label='%s (%s) - %d' % (desc, code, count)))

    ax.legend(handles=legend_patches, loc='lower left', fontsize=9,
             framealpha=0.9, title='Property Class', title_fontsize=11)

    # Stats box
    total_av = sum(float(f.get("properties",{}).get("TOTAL_AV") or 0) for f in features)
    stats = 'Parcels: %d\nTotal AV: $%.0fM' % (len(features), total_av/1e6)
    ax.text(0.98, 0.02, stats, transform=ax.transAxes, fontsize=11,
           verticalalignment='bottom', horizontalalignment='right',
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    ax.set_xlabel('Longitude', fontsize=10)
    ax.set_ylabel('Latitude', fontsize=10)

    out_path = os.path.join(OUTPUT_DIR, '%s_parcels_map.png' % muni_name.replace(" ", "_"))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print("Map saved: %s (%.1f MB)" % (out_path, size_mb))
    return out_path

if __name__ == "__main__":
    muni = sys.argv[1] if len(sys.argv) > 1 else "Scarsdale"
    geojson_path = os.path.join(OUTPUT_DIR, '%s_parcels.geojson' % muni.replace(" ", "_"))
    render_static_map(geojson_path, muni)
