# Westchester Parcels — 3D Viewer

Interactive 3D map of Westchester County, NY parcels using [CesiumJS](https://cesium.com/) and Google Photorealistic 3D Tiles.

## Features

- 🌎 **Google Photorealistic 3D Tiles** — real buildings, terrain, trees
- 📦 **Parcel overlay** — color-coded by LBCS Activity standard (APA)
- 🍩 **Dunkin' Donuts site selection** — suitability scoring (commercial zone, lot size, road frontage)
- 🔍 **Click for details** — owner, property class, assessed value, Dunkin' score
- 📍 **Municipality selector** — Scarsdale, Irvington, Yonkers, White Plains, and more

## Setup

1. Get a free Cesium ion token at [cesium.com/signup](https://cesium.com/signup)
2. Replace `YOUR_ACCESS_TOKEN` in `index.html` with your token
3. Open `index.html` in Chrome/Edge

## Controls

| Action | Input |
|--------|-------|
| Pan | Left click + drag |
| Zoom | Scroll wheel or right click + drag |
| Tilt | Ctrl + left/right drag |
| Rotate | Middle click + drag |

## Data Source

Parcel data from [Westchester County ArcGIS FeatureServer](https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Westchester_County_Parcels/FeatureServer/0)

## Scripts

- `scripts/fetch-parcels.py` — Download all 257K+ parcels to CSV/GeoJSON/Parquet
- `scripts/parcel-map.py` — Generate Folium interactive maps
- `scripts/parcel-map-static.py` — Generate static PNG maps (matplotlib)
- `scripts/parcel-map-lbcs.py` — LBCS Activity classification maps
- `scripts/parcel-map-dunkin.py` — Dunkin' site selection maps
- `scripts/parcel-map-dunkin-interactive.py` — Interactive Dunkin' maps with roads

## LBCS Classification

Uses [APA Land-Based Classification Standards](https://www.planning.org/lbcs/standards/activity/) color codes:

| Code | Category | Color |
|------|----------|-------|
| 1000 | Residential | Yellow |
| 2000 | Commercial/Business | Red |
| 3000 | Industrial | Purple |
| 4000 | Institutional | Blue |
| 5000 | Transportation | Gray |
| 7000 | Recreation/Leisure | Light Green |
| 8000 | Conservation | Forest Green |
| 9000 | Vacant | Light Gray |
