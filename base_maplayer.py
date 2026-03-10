from nicegui import ui
import os
import json

def create_base_map():
    """Creates a Leaflet map centered on Montgomery or Home Address."""
    center = (32.3668, -86.3006)
    zoom = 12

    base_dir = os.path.dirname(os.path.abspath(__file__))
    address_path = os.path.join(base_dir, 'json_data', 'home_address.json')

    if os.path.exists(address_path):
        try:
            with open(address_path, 'r') as f:
                data = json.load(f)
                if 'lat' in data and 'lon' in data:
                    center = (data['lat'], data['lon'])
                    zoom = 14
        except:
            pass

    return ui.leaflet(center=center, zoom=zoom)