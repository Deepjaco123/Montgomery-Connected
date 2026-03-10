from nicegui import ui
import styles
import json
import os
import requests
from datetime import datetime
import httpx
import asyncio

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_ADDRESS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'home_address.json')
SERVICES_JSON_PATH = os.path.join(BASE_DIR, 'json_data', '311_nearme.json')
SUMMARY_JSON_PATH = os.path.join(BASE_DIR, 'json_data', '311_summary.json')
ARCGIS_SERVICE_URL = "https://services7.arcgis.com/xNUwUjOJqYE54USz/ArcGIS/rest/services/Environmental_Nuisance/FeatureServer/0/query"
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "ibm/granite-3.1-8b"

# Global flag to prevent simultaneous generations
_is_generating = False

def get_home_address():
    if os.path.exists(HOME_ADDRESS_JSON_PATH):
        with open(HOME_ADDRESS_JSON_PATH, 'r') as f:
            return json.load(f)
    return None

async def generate_summary_json():
    """
    Generates the summary from 311 data and saves it to JSON.
    Returns (success, message_or_content, timestamp).
    """
    global _is_generating
    if _is_generating:
        print("⏳ Summary generation already in progress. Skipping request.")
        return False, "Busy", None

    _is_generating = True
    try:
        return await _generate_summary_logic()
    finally:
        _is_generating = False

async def _generate_summary_logic():
    # Smart Caching: Check if summary is newer than data
    if os.path.exists(SERVICES_JSON_PATH) and os.path.exists(SUMMARY_JSON_PATH):
        try:
            services_mtime = os.path.getmtime(SERVICES_JSON_PATH)
            summary_mtime = os.path.getmtime(SUMMARY_JSON_PATH)
            
            if summary_mtime > services_mtime:
                print("✅ Summary is up-to-date. Skipping AI generation.")
                with open(SUMMARY_JSON_PATH, 'r') as f:
                    data = json.load(f)
                return True, data.get('summary', ''), data.get('last_updated', '')
        except Exception as e:
            print(f"⚠️ Cache check failed: {e}")

    if not os.path.exists(SERVICES_JSON_PATH):
        print("🔍 311 Data missing. Attempting to fetch...")
        # Attempt to fetch data automatically if missing
        home = get_home_address()
        if home:
            load_311_services(home.get('lat'), home.get('lon'))
        else:
            return False, "No home address set.", None
            
    if not os.path.exists(SERVICES_JSON_PATH):
        return False, "No 311 data found.", None

    try:
        with open(SERVICES_JSON_PATH, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Error reading data: {e}", None

    if not data:
        return False, "No service requests found to summarize.", None

    # Prepare Data for LLM
    simplified_items = []
    for item in data[:30]: 
        attrs = item.get('attributes', {})
        desc = f"- {attrs.get('Type', 'Issue')}: {attrs.get('Remarks', 'No details')} ({attrs.get('Address', '')})"
        simplified_items.append(desc)
    
    data_context = "\n".join(simplified_items)
    
    prompt = (
        "You are an AI assistant for the Montgomery Connected app, and providing citizens with information about 311 request near them. "
        "Summarize these 311 service requests, do not use bulletpoints, give clear information about the topics." # Specific constraint
        "Focus only on the most urgent or most recent issues "
        "Do not include an intro or outro. Keep it under 100 words.\n\n"
        f"311 Data:\n{data_context}"
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 200
    }

    print(f"🤖 Connecting to LM Studio with model: {MODEL_NAME}...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(LM_STUDIO_URL, json=payload, timeout=120.0)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data = {
                "summary": content,
                "last_updated": timestamp
            }
            with open(SUMMARY_JSON_PATH, 'w') as f:
                json.dump(save_data, f, indent=4)
            
            return True, content, timestamp
        else:
            print(f"❌ LM Studio Error: {response.status_code} - {response.text}")
            return False, f"AI Error: {response.status_code}", None

    except httpx.ConnectError:
        print("❌ Connection Error: Could not reach LM Studio at 127.0.0.1:1234. Is the server started?")
        return False, "LM Studio server not running.", None
    except Exception as e:
        print(f"❌ Summary Generation Error: {e}")
        return False, f"Error: {e}", None

def load_311_services(lat, lon):
    params = {
        'where': '1=1',
        'geometry': f'{lon},{lat}',
        'geometryType': 'esriGeometryPoint',
        'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects',
        'distance': 200,
        'units': 'esriSRUnit_Meter',
        'outFields': '*',
        'f': 'json'
    }
    try:
        print(f"🌍 Fetching 311 data for {lat}, {lon}...")
        response = requests.get(ARCGIS_SERVICE_URL, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        features = data.get('features', [])
        print(f"✅ Found {len(features)} 311 items.")
        
        # Only save if data has changed to preserve mtime for smart caching
        should_save = True
        if os.path.exists(SERVICES_JSON_PATH):
            try:
                with open(SERVICES_JSON_PATH, 'r') as f:
                    if json.load(f) == features:
                        should_save = False
                        print("ℹ️ 311 Data unchanged. Skipping file write.")
            except: pass
            
        if should_save:
            with open(SERVICES_JSON_PATH, 'w') as f:
                json.dump(features, f, indent=4)
        return features
    except requests.exceptions.RequestException as e:
        # Offline Fallback: Load from local cache if API fails
        if os.path.exists(SERVICES_JSON_PATH):
            ui.notify("Network error. Loading cached 311 data...", type='warning', icon='wifi_off')
            with open(SERVICES_JSON_PATH, 'r') as f:
                return json.load(f)
        else:
            ui.notify(f"Error fetching 311 services: {e}", color='negative')
            return []

def format_date(timestamp):
    if timestamp:
        # Timestamp is in milliseconds, so divide by 1000
        dt_object = datetime.fromtimestamp(timestamp / 1000)
        return dt_object.strftime("%d-%m-%Y, %I:%M %p")
    return "N/A"

@ui.page('/311')
def three_one_one_near_me_page():
    styles.apply_styles()

    with ui.header().classes('items-center justify-between q-pa-md bg-[#2D667E] shadow-lg'):
        ui.icon('arrow_back').classes('text-2xl cursor-pointer').on('click', lambda: ui.navigate.back())
        ui.label('311 Near Me').classes('text-lg font-medium text-white').style('border-bottom: 2px solid #C99700')



    with ui.column().classes('w-full q-pa-md gap-4 items-center'):
        with ui.card().classes('w-full bg-white border-l-4 border-[#2D667E] cursor-pointer hover:shadow-md') as card:
            # Ensure the click listener is bound to the specific card instance
            card.on('click', lambda: ui.navigate.to('https://www.montgomeryal.gov/residents/report-an-issue', new_tab=True))
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('File a 311 Service Request').classes('text-base font-semibold text-[#2D667E]')
                ui.icon('arrow_forward_ios').classes('text-[#2D667E]')

        with ui.card().classes('w-full bg-white border-l-4 border-[#2D667E] shadow-sm'):
            with ui.scroll_area().classes('w-full h-[calc(100vh-150px)]'):
                home_address = get_home_address()
                if home_address:
                    services = load_311_services(home_address['lat'], home_address['lon'])
                    if not services:
                        ui.label('No 311 services found near you.').classes('text-sm italic text-grey-4 q-pa-md')
                    else:
                        with ui.column().classes('w-full gap-4 q-pr-sm'):
                            for item in services:
                                attributes = item.get('attributes', {})
                                with ui.row().classes('w-full no-wrap items-center cursor-pointer border-b border-grey-1 q-pb-md hover:bg-slate-50'):
                                    with ui.column().classes('grow q-ml-md overflow-hidden'):
                                        ui.label(attributes.get('Type', 'N/A')).classes('text-sm font-semibold leading-tight text-slate-800 line-clamp-3')
                                        ui.label(attributes.get('Address', 'N/A')).classes('text-sm font-medium text-slate-600')
                                        ui.label(attributes.get('Remarks', 'N/A')).classes('text-xs text-slate-600 line-clamp-2')
                                        ui.label(f"Source Date: {format_date(attributes.get('Source_Date'))}").classes('text-xs text-slate-500')
                else:
                    ui.label('Please set your home address first.').classes('text-sm italic text-grey-4 q-pa-md')
