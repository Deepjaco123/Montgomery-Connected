from nicegui import ui
import base_maplayer
import styles
import os
import json
import requests
import asyncio
import time
import math


# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_ADDRESS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'home_address.json')
HOSPITALS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'hospitals.json')
FIRE_POLICE_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/arcgis/rest/services/Story_Map___Live__1__WFL1/FeatureServer/3/query?outFields=*&where=1%3D1&f=geojson"
PHARMACY_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/arcgis/rest/services/Pharmacy_Locator/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson"
SHELTER_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/arcgis/rest/services/Tornado_Shelter/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson"

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

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates Haversine distance in miles."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@ui.page('/emergency')
def emergency_page():
    styles.apply_styles()
    
    # 1. Header
    with ui.header().classes('items-center justify-between q-pa-md bg-[#2D667E]'):
        ui.icon('arrow_back').classes('text-2xl cursor-pointer').on('click', lambda: ui.navigate.back())
        ui.label('Emergency & Healthcare').classes('text-white text-lg').style('border-bottom: 2px solid #C99700')

    # 2. Map
    m = base_maplayer.create_base_map().classes('w-full h-[75vh]')

    # 3. Nearest Services Container
    nearest_container = ui.column().classes('w-full q-pa-md gap-4')
    
    # 4. Async Load Layers (Home + Fire/Police)
    async def load_map_layers():
        home_coords = None
        services = {
            'Hospital': [],
            'Pharmacy': [],
            'Shelter': [],
            'Police': [],
            'Fire': []
        }

        # --- HOME ---
        if os.path.exists(HOME_ADDRESS_JSON_PATH):
            try:
                with open(HOME_ADDRESS_JSON_PATH, 'r') as f:
                    home = json.load(f)
                    marker = m.marker(latlng=(home['lat'], home['lon']))
                    set_icon(marker, 'home.png')
                    home_coords = (home['lat'], home['lon'])
            except Exception as e:
                print(f"Error loading home marker: {e}")

        # --- HOSPITALS ---
        if os.path.exists(HOSPITALS_JSON_PATH):
            try:
                with open(HOSPITALS_JSON_PATH, 'r') as f:
                    data = json.load(f)
                    for hospital in data.get('hospitals', []):
                        if 'lat' in hospital and 'lon' in hospital:
                            marker = m.marker(latlng=(hospital['lat'], hospital['lon']))
                            set_icon(marker, 'hospital.png')
                            if home_coords:
                                dist = calculate_distance(home_coords[0], home_coords[1], hospital['lat'], hospital['lon'])
                                services['Hospital'].append({'name': hospital.get('name', 'Hospital'), 'dist': dist, 'lat': hospital['lat'], 'lon': hospital['lon']})
            except Exception as e:
                print(f"Error loading hospital markers: {e}")

        # --- FIRE & POLICE ---
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(FIRE_POLICE_URL, timeout=5))
            data = response.json()
            
            for feat in data['features']:
                props = feat['properties']
                geom = feat['geometry']
                if not geom: continue
                
                lat, lon = geom['coordinates'][1], geom['coordinates'][0]
                category = props.get('category', '').lower()
                name = props.get('Facility_Name', 'Emergency Service')
                
                icon_file = 'police.png' if 'police' in category else 'fire.png'
                marker = m.marker(latlng=(lat, lon))
                set_icon(marker, icon_file)

                if home_coords:
                    dist = calculate_distance(home_coords[0], home_coords[1], lat, lon)
                    cat_key = 'Police' if 'police' in category else 'Fire'
                    services[cat_key].append({'name': name, 'dist': dist, 'lat': lat, 'lon': lon})
        except Exception as e:
            print(f"Error loading emergency data: {e}")

        # --- PHARMACIES ---
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(PHARMACY_URL, timeout=5))
            data = response.json()
            
            for feat in data['features']:
                geom = feat['geometry']
                if not geom: continue
                lat, lon = geom['coordinates'][1], geom['coordinates'][0]
                marker = m.marker(latlng=(lat, lon))
                set_icon(marker, 'pharmacy.png')
                
                if home_coords:
                    dist = calculate_distance(home_coords[0], home_coords[1], lat, lon)
                    name = feat['properties'].get('COMPANY_NAME', 'Pharmacy')
                    services['Pharmacy'].append({'name': name, 'dist': dist, 'lat': lat, 'lon': lon})
        except Exception as e:
            print(f"Error loading pharmacy data: {e}")

        # --- SHELTERS ---
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(SHELTER_URL, timeout=5))
            data = response.json()
            
            for feat in data['features']:
                geom = feat['geometry']
                if not geom: continue
                lat, lon = geom['coordinates'][1], geom['coordinates'][0]
                marker = m.marker(latlng=(lat, lon))
                set_icon(marker, 'shelter.png')

                if home_coords:
                    dist = calculate_distance(home_coords[0], home_coords[1], lat, lon)
                    name = feat['properties'].get('SHELTER', 'Shelter')
                    services['Shelter'].append({'name': name, 'dist': dist, 'lat': lat, 'lon': lon})
        except Exception as e:
            print(f"Error loading shelter data: {e}")

        # --- RENDER NEAREST LIST ---
        if home_coords:
            nearest_container.clear()
            with nearest_container:
                ui.label('Nearest Emergency Services').classes('text-xl font-bold text-[#2D667E] q-mb-sm')
                
                def render_category(title, items, icon_file):
                    if not items: return
                    sorted_items = sorted(items, key=lambda x: x['dist'])[:3]
                    
                    with ui.card().classes('w-full bg-white border-l-4 border-[#2D667E] shadow-sm q-mb-md'):
                        with ui.row().classes('items-center q-pb-sm border-b border-gray-100 w-full'):
                            ui.image(f'/map_icons/{icon_file}').classes('w-8 h-8')
                            ui.label(title).classes('text-lg font-semibold text-slate-800')
                        
                        with ui.column().classes('w-full q-pt-sm gap-2'):
                            for item in sorted_items:
                                url = f"https://www.google.com/maps/dir/{home_coords[0]},{home_coords[1]}/{item['lat']},{item['lon']}"
                                with ui.row().classes('w-full justify-between items-center cursor-pointer hover:bg-slate-50 q-pa-xs rounded') \
                                        .on('click', lambda u=url: ui.navigate.to(u, new_tab=True)):
                                    ui.label(item['name']).classes('text-sm font-medium text-slate-700')
                                    with ui.row().classes('items-center'):
                                        ui.label(f"{item['dist']:.2f} miles").classes('text-sm text-slate-500 q-mr-xs')
                                        ui.icon('directions', color='primary').classes('text-sm')

                render_category('Hospitals', services['Hospital'], 'hospital.png')
                render_category('Pharmacies', services['Pharmacy'], 'pharmacy.png')
                render_category('Tornado Shelters', services['Shelter'], 'shelter.png')
                render_category('Police Stations', services['Police'], 'police.png')
                render_category('Fire Stations', services['Fire'], 'fire.png')
        else:
            nearest_container.clear()
            with nearest_container:
                ui.label('Please set your home address to see nearest services.').classes('text-gray-500 italic q-pa-md')

    ui.timer(0.5, load_map_layers, once=True)