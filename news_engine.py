import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'json_data', 'latest_news.json')
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

url = "https://www.newsbreak.com/montgomery"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

print(f"🔄 News Update Worker Running. Saving to: {OUTPUT_FILE}")

try:
    while True:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        news_links = soup.find_all('a', href=True)
        news_list = []

        for link in news_links:
            h3 = link.find('h3')
            if h3:
                title = h3.get_text(strip=True)
                
                # --- SEARCH FOR THE TIMESTAMP ---
                # We look for small text like '1d' or '2h' in siblings or child spans
                published = ""
                # Search for any span/div containing 'h' (hours) or 'd' (days) with numbers
                time_info = link.find_next(['span', 'div', 'time'], string=lambda s: s and any(u in s for u in ['h', 'd', 'm']) and len(s) < 6)
                
                if time_info:
                    published = time_info.get_text(strip=True)
                
                # Filter noise
                if (len(title) > 20 and 'publisher' not in title.lower()):
                    href = link['href']
                    if href.startswith('/'):
                        href = 'https://www.newsbreak.com' + href
                    
                    news_list.append({
                        'title': title[:150], 
                        'url': href,
                        'published': published # This will now hold '1d', '2h', etc.
                    })

        # Clean and Deduplicate
        news_list = list({news['url']: news for news in news_list}.values())

        # Save to JSON
        data_to_save = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "news": news_list[:15] 
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Saved {len(news_list[:15])} articles to {OUTPUT_FILE}")
        
        # Keep the loop going every 30 mins
        time.sleep(1800) 

except KeyboardInterrupt:
    print("\n🛑 Worker stopped.")