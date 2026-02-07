import requests
import json
import os
from datetime import datetime, timedelta

class OpenMeteoClient:
    def __init__(self, cache_dir="cache"):
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        self.cities = {
            "london": {"lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
            "miami": {"lat": 25.7617, "lon": -80.1918, "tz": "America/New_York"},
            "buenos-aires": {"lat": -34.6037, "lon": -58.3816, "tz": "America/Argentina/Buenos_Aires"},
            "atlanta": {"lat": 33.7490, "lon": -84.3880, "tz": "America/New_York"},
            "seoul": {"lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul"},
            "seattle": {"lat": 47.6062, "lon": -122.3321, "tz": "America/Los_Angeles"},
            "toronto": {"lat": 43.6532, "lon": -79.3832, "tz": "America/Toronto"},
            "chicago": {"lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago"}
        }

    def get_forecast(self, city_name, date_str):
        """
        Fetches max temperature for a specific city and date.
        date_str: YYYY-MM-DD
        """
        city = self.cities.get(city_name.lower())
        if not city:
            return None
            
        # Cache check
        cache_key = f"{city_name}_{date_str}.json"
        cache_path = os.path.join(self.cache_dir, cache_key)
        
        if os.path.exists(cache_path):
            st = os.stat(cache_path)
            # Cache for 1 hour
            if datetime.now() - datetime.fromtimestamp(st.st_mtime) < timedelta(hours=1):
                with open(cache_path, 'r') as f:
                    return json.load(f)

        # API Call
        try:
            params = {
                "latitude": city["lat"],
                "longitude": city["lon"],
                "daily": "temperature_2m_max",
                "timezone": city["tz"],
                "start_date": date_str,
                "end_date": date_str
            }
            r = requests.get(self.base_url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if "daily" in data and "temperature_2m_max" in data["daily"]:
                val = data["daily"]["temperature_2m_max"][0]
                res = {"max_temp": val, "unit": "C"}
                
                # Save to cache
                with open(cache_path, 'w') as f:
                    json.dump(res, f)
                return res
        except Exception as e:
            print(f"Error fetching OpenMeteo for {city_name}: {e}")
            
        return None
