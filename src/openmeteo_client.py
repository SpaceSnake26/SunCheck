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
            "london": {"lat": 51.5030, "lon": 0.0495, "tz": "Europe/London", "unit": "C"},
            "miami": {"lat": 25.7959, "lon": -80.2796, "tz": "America/New_York", "unit": "F"},
            "buenos-aires": {"lat": -34.6037, "lon": -58.3816, "tz": "America/Argentina/Buenos_Aires", "unit": "C"},
            "atlanta": {"lat": 33.6407, "lon": -84.4467, "tz": "America/New_York", "unit": "F"},
            "seoul": {"lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul", "unit": "C"},
            "seattle": {"lat": 47.4404, "lon": -122.2915, "tz": "America/Los_Angeles", "unit": "F"},
            "toronto": {"lat": 43.6817, "lon": -79.6116, "tz": "America/Toronto", "unit": "C"},
            "chicago": {"lat": 41.9777, "lon": -87.9040, "tz": "America/Chicago", "unit": "F"},
            "ankara": {"lat": 39.9334, "lon": 32.8597, "tz": "Europe/Istanbul", "unit": "C"},
            "dallas": {"lat": 32.8453, "lon": -96.8518, "tz": "America/Chicago", "unit": "F"},
            "new york": {"lat": 40.7740, "lon": -73.8726, "tz": "America/New_York", "unit": "F"}
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
            # Cache for 15 minutes
            if datetime.now() - datetime.fromtimestamp(st.st_mtime) < timedelta(minutes=15):
                try:
                    with open(cache_path, 'r') as f:
                        cached = json.load(f)
                        # VALIDATE UNIT
                        expected_unit = city.get("unit", "C")
                        if cached.get("unit") == expected_unit:
                            return cached
                        # Else: Fall through to API call to refresh cache with correct unit
                except:
                    pass

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
            
            # Explicitly request Fahrenheit if configured
            if city.get("unit") == "F":
                params["temperature_unit"] = "fahrenheit"
                
            r = requests.get(self.base_url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if "daily" in data and "temperature_2m_max" in data["daily"]:
                val = data["daily"]["temperature_2m_max"][0]
                res = {"max_temp": val, "unit": city.get("unit", "C")}
                
                # Save to cache
                with open(cache_path, 'w') as f:
                    json.dump(res, f)
                return res
        except Exception as e:
            print(f"Error fetching OpenMeteo for {city_name}: {e}")
            
        return None
