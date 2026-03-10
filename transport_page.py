from nicegui import ui
import base_maplayer
import styles
import requests
import asyncio
import os
import json
import time

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_ADDRESS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'home_address.json')
ROUTES_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/arcgis/rest/services/Transit_Data_TIP/FeatureServer/2/query?where=1%3D1&outFields=*&f=geojson"

def set_icon(marker, filename):
    """Helper to set icon using L.icon definition directly."""
    if os.path.exists(os.path.join(BASE_DIR, 'map_icons', filename)):
        ts = int(time.time())
        js = f"""L.icon({{
            iconUrl: "/map_icons/{filename}?v={ts}",
            iconSize: [38, 38],
            iconAnchor: [19, 38],
            popupAnchor: [0, -38]
        }})"""
        marker.run_method(':setIcon', js)

@ui.page('/transport')
def transport_page():
    styles.apply_styles()

    # 1. Header
    with ui.header().classes('items-center justify-between q-pa-md bg-[#2D667E]'):
        ui.icon('arrow_back').classes('text-2xl cursor-pointer').on('click', lambda: ui.navigate.back())
        ui.label('Transport & Transit').classes('text-white text-lg').style('border-bottom: 2px solid #C99700')

    # 2. Map
    m = base_maplayer.create_base_map().classes('w-full h-[75vh]')

    # 3. External Link
    with ui.column().classes('w-full q-pa-md'):
        styles.nav_card('Visit MTransit', 'language', 'https://themtransit.com/', 'Official Transit Website')

    # 4. Async Load Layers
    async def load_map_layers():
        # --- HOME MARKER ---
        if os.path.exists(HOME_ADDRESS_JSON_PATH):
            try:
                with open(HOME_ADDRESS_JSON_PATH, 'r') as f:
                    home = json.load(f)
                    marker = m.marker(latlng=(home['lat'], home['lon']))
                    set_icon(marker, 'home.png')
            except Exception as e:
                print(f"Error loading home marker: {e}")

        # --- TRANSIT ROUTES ---
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, requests.get, ROUTES_URL)
            data = response.json()

            for feat in data.get('features', []):
                props = feat.get('properties', {})
                geom = feat.get('geometry', {})
                if not geom: continue
                
                # Parse Geometry & Flip Coordinates (GeoJSON [lon, lat] -> Leaflet [lat, lon])
                coords = geom.get('coordinates', [])
                geom_type = geom.get('type')
                latlngs = []

                if geom_type == 'LineString':
                    latlngs = [[p[1], p[0]] for p in coords]
                elif geom_type == 'MultiLineString':
                    latlngs = [[[p[1], p[0]] for p in line] for line in coords]
                else:
                    continue
                
                # Color Logic
                raw_hex = props.get('route_color', '555555')
                hex_color = f"#{raw_hex}" if raw_hex and not str(raw_hex).startswith('#') else (raw_hex or '#555555')

                # Plot using generic_layer (Vector Polyline)
                m.generic_layer(name='polyline', args=[latlngs, {'color': hex_color, 'weight': 6, 'opacity': 0.7, 'lineCap': 'round'}])

        except Exception as e:
            print(f"Error loading transit routes: {e}")
            ui.notify("Could not load transit routes.", type='negative')

    ui.timer(0.1, load_map_layers, once=True)