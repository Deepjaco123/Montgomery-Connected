from nicegui import app, ui
import styles
import address_page
import base_maplayer
import emergency_page
import transport_page
import recreation_page
import os
import importlib
import json
import asyncio

three_one_one_near_me_page = importlib.import_module("311_nearme_page")
import subprocess
import sys

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'latest_news.json')
ADDRESS_JSON_PATH = os.path.join(BASE_DIR, 'json_data', 'home_address.json')
SUMMARY_JSON_PATH = os.path.join(BASE_DIR, 'json_data', '311_summary.json')
WORKER_SCRIPT_PATH = os.path.join(BASE_DIR, 'news_engine.py')
HOSPITAL_WORKER_PATH = os.path.join(BASE_DIR, 'hospital_engine.py')

# CLEANUP: Automatically remove the misplaced file from the root directory if it exists
legacy_news_path = os.path.join(BASE_DIR, 'latest_news.json')
if os.path.exists(legacy_news_path):
    try:
        os.remove(legacy_news_path)
        print(f"🗑️ Removed legacy file: {legacy_news_path}")
    except Exception as e:
        print(f"⚠️ Could not remove legacy file: {e}")

os.makedirs(os.path.join(BASE_DIR, 'json_data'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'map_icons'), exist_ok=True)
app.add_static_files('/map_icons', os.path.join(BASE_DIR, 'map_icons'))

# Global process references to manage background workers
news_process = None
hospital_process = None

def start_news_worker():
    global news_process
    if os.path.exists(WORKER_SCRIPT_PATH):
        news_process = subprocess.Popen([sys.executable, WORKER_SCRIPT_PATH], cwd=BASE_DIR)

def start_hospital_worker():
    global hospital_process
    if os.path.exists(HOSPITAL_WORKER_PATH):
        hospital_process = subprocess.Popen([sys.executable, HOSPITAL_WORKER_PATH], cwd=BASE_DIR)

def stop_workers():
    """Kills background workers when the app shuts down or reloads."""
    if news_process:
        news_process.terminate()
    if hospital_process:
        hospital_process.terminate()

app.on_startup(start_news_worker)
app.on_startup(start_hospital_worker)
app.on_shutdown(stop_workers)

class AppData:
    def __init__(self):
        self.home_address = "No address"
        self.news_data = {"news": [], "last_updated": ""}
        self.summary_data = {"summary": "No summary available.", "last_updated": "N/A"}

    def load_address(self):
        if os.path.exists(ADDRESS_JSON_PATH):
            try:
                with open(ADDRESS_JSON_PATH, 'r') as f:
                    data = json.load(f)
                    full_address = data.get('full_address')
                    if full_address:
                        self.home_address = full_address.split(',')[0]
                    else:
                        self.home_address = "No address"
            except (json.JSONDecodeError, FileNotFoundError):
                self.home_address = "No address"
        else:
            self.home_address = "No address"

    def load_summary(self):
        if os.path.exists(SUMMARY_JSON_PATH):
            try:
                with open(SUMMARY_JSON_PATH, 'r', encoding='utf-8') as f:
                    self.summary_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.summary_data = {"summary": "Could not load summary.", "last_updated": "N/A"}
        else:
            self.summary_data = {"summary": "No summary generated yet. Visit the 311 Summary page.", "last_updated": "N/A"}

    async def load_all(self):
        self.load_address()
        await self.refresh_news()
        # Automatically generate summary if 311 data exists
        await three_one_one_near_me_page.generate_summary_json()
        self.load_summary()

    async def refresh_news(self):
        if os.path.exists(NEWS_JSON_PATH):
            try:
                with open(NEWS_JSON_PATH, 'r', encoding='utf-8') as f:
                    self.news_data = json.load(f)
            except: pass

    def get_time_only(self):
        raw = self.news_data.get('last_updated', '')
        return raw.split(' ')[1] if ' ' in raw else "--:--:--"

engine = AppData()
app.on_startup(engine.load_all)

@ui.page('/')
async def main_dashboard():
    styles.apply_styles()
    engine.load_address()
    engine.load_summary()

    # Background Task: Smart update (checks timestamps internally)
    if engine.home_address != "No address ":
        # Fire and forget - the function handles the "do I need to run?" logic
        asyncio.create_task(three_one_one_near_me_page.generate_summary_json())

    # 1. FIXED TOP BAR
    with ui.header().classes('items-center justify-between q-pa-md bg-[#2D667E] shadow-lg'):
        with ui.row().classes('items-center no-wrap overflow-hidden'):
            ui.icon('home').classes('text-xl shrink-0 cursor-pointer rounded-full bg-[#C99700] p-2 text-white').on('click', lambda: ui.navigate.to('/address'))
            ui.label(engine.home_address).classes('text-sm font-medium text-white q-ml-sm truncate max-w-[250px]').style('border-bottom: 2px solid #C99700')
        with ui.row().classes('items-center gap-1'):
            ui.label('Montgomery').classes('text-lg font-bold text-white')
            ui.label('Connected').classes('text-lg font-bold text-[#C99700]')


    # 2. DYNAMIC CONTENT AREA
    with ui.column().classes('w-full q-pa-md gap-4 items-center'):
        
        # DYNAMIC NEWS CARD
        with ui.card().classes('w-full bg-white border-l-4 border-[#2D667E] shadow-sm').style('max-height: 200px;'):
            with ui.row().classes('w-full justify-between items-center no-wrap q-px-xs'):
                ui.label('NEWSBREAK NEWS').classes('text-sm font-bold text-[#2D667E] tracking-tight shrink-0')
                ui.label(f"Updated: {engine.get_time_only()}").classes('text-sm text-grey-5 shrink-0')
            
            ui.separator()

            with ui.scroll_area().classes('w-full grow'):
                await engine.refresh_news()
                if not engine.news_data['news']:
                    ui.label('Syncing local news...').classes('text-sm italic text-grey-4 q-pa-md')
                else:
                    with ui.column().classes('w-full gap-4 q-pr-sm'):
                        for item in engine.news_data['news']:
                            if any(x in item['title'].lower() for x in ['publisher', 'followers']):
                                continue
                            
                            # --- NEWS ITEM ROW ---
                            with ui.row().classes('w-full no-wrap items-center cursor-pointer border-b border-gray-100 q-pb-md hover:bg-slate-50') \
                                    .on('click', lambda url=item['url']: ui.navigate.to(url, new_tab=True)):
                                
                                # 1. The Title Text
                                with ui.column().classes('grow q-ml-md overflow-hidden'):
                                    ui.label(item['title']).classes('text-sm font-semibold leading-tight text-slate-800 line-clamp-3')


        # Determine subtitle for 311 card
        summary_subtitle = engine.summary_data.get('summary', 'No summary')
        if not summary_subtitle or summary_subtitle.startswith("No summary generated") or summary_subtitle.startswith("Could not load"):
            summary_subtitle = "No summary"

        # DYNAMIC NAVIGATION TILES
        styles.nav_card('311 Near Me', 'support_agent', '/311', summary_subtitle)
        styles.nav_card('Emergency Services', 'medical_services', '/emergency', 'Hospitals, Pharmacies, Police & Shelters')
        styles.nav_card('Transport', 'directions_bus', '/transport', 'Transit & Local Paving')
        styles.nav_card('Recreation', 'forest', '/recreation', 'Parks, Trails & Events')        

ui.run(title='Montgomery Connected', port=8080)