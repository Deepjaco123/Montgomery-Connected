from nicegui import ui
import base_maplayer
import styles
import requests
import asyncio
import os
import json
import time
import math

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_ADDRESS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'home_address.json')
PARKS_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/ArcGIS/rest/services/Park_and_Trail/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson"

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

@ui.page('/recreation')
def recreation_page():
    styles.apply_styles()

    # 1. Header
    with ui.header().classes('items-center justify-between q-pa-md bg-[#2D667E]'):
        ui.icon('arrow_back').classes('text-2xl cursor-pointer').on('click', lambda: ui.navigate.back())
        ui.label('Parks & Recreation').classes('text-white text-lg').style('border-bottom: 2px solid #C99700')

    # 2. Map
    m = base_maplayer.create_base_map().classes('w-full h-[75vh]')

    # 3. External Link
    with ui.column().classes('w-full q-pa-md'):
        styles.nav_card('Fun in Montgomery.', 'park', 'https://www.funinmontgomery.com/', 'Official City Website')

    # 4. Nearest Parks Container
    nearest_container = ui.column().classes('w-full q-pa-md gap-4')

    # 5. Async Load Layers
    async def load_map_layers():
        home_coords = None
        parks = []

        # --- HOME MARKER ---
        if os.path.exists(HOME_ADDRESS_JSON_PATH):
            try:
                with open(HOME_ADDRESS_JSON_PATH, 'r') as f:
                    home = json.load(f)
                    marker = m.marker(latlng=(home['lat'], home['lon']))
                    set_icon(marker, 'home.png')
                    home_coords = (home['lat'], home['lon'])
            except Exception as e:
                print(f"Error loading home marker: {e}")

        # --- PARKS & REC FACILITIES ---
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, requests.get, PARKS_URL)
            data = response.json()

            for feat in data.get('features', []):
                props = feat.get('properties', {})
                geom = feat.get('geometry', {})
                if not geom: continue
                
                lat, lon = geom['coordinates'][1], geom['coordinates'][0]
                name = props.get('FACILITYID', 'Unknown Facility')
                fac_type = props.get('FACILITYTYPE', 'Park')
                
                marker = m.marker(latlng=(lat, lon))
                
                # Dynamic icon loading based on facility type
                icon_name = fac_type.lower().replace(' ', '_') + '.png'
                if not os.path.exists(os.path.join(BASE_DIR, 'map_icons', icon_name)):
                    icon_name = 'park.png'
                set_icon(marker, icon_name)
                
                # Tooltip/Popup
                marker.props(f'title="{name} ({fac_type})"')
                
                # Collect data for nearest list
                if home_coords:
                    dist = calculate_distance(home_coords[0], home_coords[1], lat, lon)
                    
                    # Check amenities
                    amenity_list = []
                    def check(key, label):
                        if props.get(key) == 'Yes': amenity_list.append(label)
                    
                    check('PLAYGROUND', 'Playground')
                    check('RESTROOM', 'Restrooms')
                    check('PICNIC', 'Picnic')
                    check('BASKETBALL', 'Basketball')
                    check('TENNIS', 'Tennis')
                    check('SWIMMING', 'Pool')
                    check('HIKING', 'Hiking')
                    
                    parks.append({
                        'name': name,
                        'address': props.get('FULLADDR', 'No Address'),
                        'type': fac_type,
                        'dist': dist,
                        'lat': lat,
                        'lon': lon,
                        'amenities': amenity_list
                    })

        except Exception as e:
            print(f"Error loading parks data: {e}")
            ui.notify("Could not load parks data.", type='negative')

        # --- RENDER NEAREST LIST ---
        if home_coords and parks:
            nearest_container.clear()
            with nearest_container:
                ui.label('Nearest Parks & Recreation').classes('text-xl font-bold text-[#2D667E] q-mb-sm')
                
                sorted_parks = sorted(parks, key=lambda x: x['dist'])[:5]
                
                for p in sorted_parks:
                    url = f"https://www.google.com/maps/dir/{home_coords[0]},{home_coords[1]}/{p['lat']},{p['lon']}"
                    
                    with ui.card().classes('w-full bg-white border-l-4 border-[#2D667E] shadow-sm cursor-pointer hover:bg-slate-50') \
                            .on('click', lambda u=url: ui.navigate.to(u, new_tab=True)):
                        
                        with ui.row().classes('w-full justify-between items-start'):
                            with ui.column().classes('grow'):
                                ui.label(p['name']).classes('text-lg font-semibold text-slate-800 leading-tight')
                                ui.label(p['address']).classes('text-sm text-slate-600')
                                ui.label(f"{p['dist']:.2f} miles • {p['type']}").classes('text-xs text-slate-500 font-medium')
                            ui.icon('directions', color='primary').classes('text-xl q-mt-xs')
                        
                        if p['amenities']:
                            ui.separator().classes('q-my-sm')
                            with ui.row().classes('gap-1'):
                                for am in p['amenities'][:4]:
                                    ui.label(am).classes('text-[10px] bg-slate-100 text-slate-600 px-2 py-1 rounded-full')
                                if len(p['amenities']) > 4:
                                    ui.label(f"+{len(p['amenities'])-4}").classes('text-[10px] bg-slate-100 text-slate-600 px-2 py-1 rounded-full')
        elif not home_coords:
             nearest_container.clear()
             with nearest_container:
                ui.label('Set home address to see nearest parks.').classes('text-gray-500 italic q-pa-md')

    ui.timer(0.1, load_map_layers, once=True)