from nicegui import ui, app
import json
import os
import httpx
import styles

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DATA_DIR = os.path.join(BASE_DIR, 'json_data')
HOME_ADDRESS_JSON_PATH = os.path.join(JSON_DATA_DIR, 'home_address.json')
TEMP_ADDRESS_PATH = os.path.join(JSON_DATA_DIR, 'temporary_address.json')
API_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/ArcGIS/rest/services/Address_Point_Updated/FeatureServer/0/query"

@ui.page('/address')
def address_page():
    styles.apply_styles()
    os.makedirs(JSON_DATA_DIR, exist_ok=True)

    address_map = {}

    def on_dropdown_change():
        if dropdown.value:
            save_btn.props(remove='disabled')
        else:
            save_btn.props(add='disabled')

    # --- 1. UI LAYOUT (INITIALIZATION) ---
    with ui.header().classes('items-center justify-between q-pa-md bg-[#2D667E] shadow-lg'):
        with ui.row().classes('items-center no-wrap overflow-hidden'):
            # Changed icon to arrow_back and action to navigate back
            ui.icon('arrow_back', color='white').classes('text-xl shrink-0').on('click', lambda: ui.navigate.to('/'))
            # Changed label text
            ui.label('Set Your Home Address').classes('text-sm font-medium text-white q-ml-sm truncate')


    with ui.column().classes('w-full items-center q-pa-md'):
        with ui.card().classes('w-full max-w-lg'):
            with ui.card_section():
                with ui.row().classes('items-center'):
                    ui.icon('location_on', color='primary').classes('text-2xl')
                    ui.label("Find Your Address").classes('text-xl font-bold text-dark q-ml-sm')
                ui.label("Enter your zip code and street number below.").classes('text-sm text-grey-7 q-mt-sm')
            
            ui.separator()

            with ui.card_section().classes('gap-4'):
                zip_input = ui.input(label='Zip Code', placeholder='e.g., 36111').classes('w-full')
                num_input = ui.input(label='Street Number', placeholder='e.g., 3568').classes('w-full')
                search_btn = ui.button('Search', icon='search', on_click=lambda: search()).classes('w-full')

            dropdown = ui.select(options=[], label='Select result', on_change=on_dropdown_change).props('disabled').classes('w-full')

            with ui.card_actions().classes('justify-center w-full q-pa-md'):
                save_btn = ui.button('Save Address', icon='save', on_click=lambda: save_selection()).props('disabled').classes('w-1/2')

    # --- 2. LOGIC FUNCTIONS ---
    async def search():
        if not zip_input.value or not num_input.value:
            ui.notify("Please enter both fields.", type='warning', icon='warning')
            return

        dropdown.props(add='disabled')
        save_btn.props(add='disabled')
        ui.notify("Fetching data...", type='info', icon='sync')

        params = {
            'where': f"ZIPCODE = '{zip_input.value.strip()}' AND ST_NUM = {num_input.value.strip()}",
            'outFields': 'FULLADDR, ST_NUM, ZIPCODE',
            'outSR': '4326',
            'f': 'json',
            'returnGeometry': 'true'
        }
        
        features = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(API_URL, params=params, timeout=10)
            data = response.json()

            # Cache raw results to temporary file
            with open(TEMP_ADDRESS_PATH, 'w') as f:
                json.dump(data, f, indent=4)
            
            features = data.get('features', [])

        except Exception as e:
            # Offline Fallback: Load from local cache if API fails
            if os.path.exists(TEMP_ADDRESS_PATH):
                ui.notify("Network error. Loading cached results...", type='warning', icon='wifi_off')
                try:
                    with open(TEMP_ADDRESS_PATH, 'r') as f:
                        data_from_file = json.load(f)
                    features = data_from_file.get('features', [])
                except:
                    pass
            
            if not features:
                ui.notify(f"API Error: {e}", type='negative', icon='report_problem')
                return

        if not features:
            ui.notify("No matches found.", type='negative', icon='error')
            return

        try:
            address_map.clear()
            new_options = []
            for feat in features:
                attr = feat['attributes']
                geom = feat['geometry']
                
                full_addr_str = attr['FULLADDR']
                address_details = {
                    "full_address": f"{full_addr_str}, Montgomery, AL {attr['ZIPCODE']}",
                    "zip": attr['ZIPCODE'],
                    "lat": geom['y'],
                    "lon": geom['x']
                }
                
                new_options.append(full_addr_str)
                address_map[full_addr_str] = address_details


            dropdown.options = new_options
            dropdown.value = None # Reset selection
            dropdown.props(remove='disabled')
            ui.notify(f"Found {len(features)} results. Please select an address.", type='positive', icon='check_circle')

        except Exception as e:
            ui.notify(f"Processing Error: {e}", type='negative', icon='report_problem')

    def save_selection():
        selected_address_str = dropdown.value
        if selected_address_str:
            selected_data = address_map.get(selected_address_str)
            if selected_data:
                try:
                    with open(HOME_ADDRESS_JSON_PATH, 'w') as f:
                        json.dump(selected_data, f, indent=4)
                    ui.notify('Address saved successfully', icon='check_circle', type='positive')
                    ui.navigate.to('/')
                except Exception as e:
                    ui.notify(f"Save failed: {e}", type='negative', icon='error')
        else:
            ui.notify("Please select an address first.", type='warning', icon='warning')
                
# --- 3. RUNTIME ---
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Montgomery Connected", port=8080)