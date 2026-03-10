import requests
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime
import os

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'json_data', 'hospitals.json')
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

print(f"🏥 Hospital Update Worker Running. Saving to: {OUTPUT_FILE}")

def geocode_address(address):
    """Fetch coordinates from Nominatim with rate limiting."""
    try:
        # Append context to ensure we find the location in Montgomery
        query = f"{address}, Montgomery, AL" if "montgomery" not in address.lower() else address
        url = "https://nominatim.openstreetmap.org/search"
        params = {'q': query, 'format': 'json', 'limit': 1}
        headers = {'User-Agent': 'MontgomeryConnectedApp/1.0'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200 and response.json():
            return float(response.json()[0]['lat']), float(response.json()[0]['lon'])
    except Exception as e:
        print(f"⚠️ Geocoding error for '{address}': {e}")
    return None, None

def scrape_hospitals():
    url = "https://npino.com/hospitals/al/montgomery/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"⚠️ Failed to fetch URL: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        hospital_list = []

        address_containers = soup.find_all('p', class_='text-xs text-gray-600 mt-1')

        for container in address_containers:
            raw_text = container.get_text(strip=True)
            if "Address:" in raw_text:
                # 1. Basic cleaning
                addr = raw_text.replace("Address:", "").strip()
                
                # 2. Surgical Noise Removal (Strip Floor, Suite, Wing, Campus, Bld)
                addr = re.sub(r'(?i),?\s*\d+(st|nd|rd|th)\s+Floor', '', addr)
                addr = re.sub(r'(?i),?\s*Suite\s+\w+', '', addr)
                addr = re.sub(r'(?i),?\s*(North|South|East|West)\s+(Wing|Campus)', '', addr)
                addr = re.sub(r'(?i)\bBld\s+\d+\b', '', addr)
                
                # 3. Final polish (remove double commas and trailing spaces)
                addr = re.sub(r',\s*,', ',', addr)
                clean_addr = addr.strip().strip(',')

                # Find Hospital Name
                parent_block = container.find_parent('div')
                name_tag = parent_block.find(['a', 'h2', 'h3']) if parent_block else None
                name = name_tag.get_text(strip=True) if name_tag else "Unknown Hospital"

                hospital_list.append({'name': name, 'address': clean_addr})
        
        return hospital_list

    except Exception as e:
        print(f"❌ Error scraping hospitals: {e}")
        return []

try:
    while True:
        new_hospitals = scrape_hospitals()
        
        if new_hospitals:
            # 1. Load existing coordinates to avoid re-geocoding (Smart Caching)
            existing_coords = {}
            if os.path.exists(OUTPUT_FILE):
                try:
                    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for h in data.get('hospitals', []):
                            if 'lat' in h and 'lon' in h:
                                existing_coords[h['address']] = (h['lat'], h['lon'])
                except: pass

            # 2. Enrich new data with coordinates
            for hospital in new_hospitals:
                addr = hospital['address']
                if addr in existing_coords:
                    hospital['lat'], hospital['lon'] = existing_coords[addr]
                else:
                    print(f"📍 Geocoding: {hospital['name']}")
                    lat, lon = geocode_address(addr)
                    if lat and lon:
                        hospital['lat'] = lat
                        hospital['lon'] = lon
                    time.sleep(1.1) # Respect Nominatim rate limit (1 req/sec)

            should_save = True
            
            # Check against existing file to prevent unnecessary writes
            if os.path.exists(OUTPUT_FILE):
                try:
                    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if existing_data.get('hospitals') == new_hospitals:
                            should_save = False
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ℹ️ Hospital data unchanged. Skipping write.")
                except Exception as e:
                    print(f"⚠️ Error reading existing file: {e}")

            if should_save:
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump({
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "hospitals": new_hospitals
                    }, f, indent=4, ensure_ascii=False)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Saved {len(new_hospitals)} hospitals to {OUTPUT_FILE}")
        
        # Sleep for 12 hours (43200 seconds) as hospital data changes rarely
        time.sleep(43200)

except KeyboardInterrupt:
    print("\n🛑 Hospital Worker stopped.")