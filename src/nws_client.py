import requests
import json
import os
from datetime import datetime, timedelta

class NWSClient:
    def __init__(self, cache_dir="cache"):
        self.base_url = "https://api.weather.gov"
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        self.headers = {
            "User-Agent": "SunCheckWeatherBot/1.0 (contact: your@email.com)"
        }
        
    def get_forecast(self, lat, lon, target_date_str):
        """
        Fetches max temperature for a specific coordinate and date from weather.gov.
        target_date_str: YYYY-MM-DD
        """
        # Cache check
        cache_key = f"nws_{lat}_{lon}_{target_date_str}.json"
        cache_path = os.path.join(self.cache_dir, cache_key)
        
        if os.path.exists(cache_path):
            st = os.stat(cache_path)
            # Cache for 1 hour
            if datetime.now() - datetime.fromtimestamp(st.st_mtime) < timedelta(hours=1):
                with open(cache_path, 'r') as f:
                    return json.load(f)

        try:
            # 1. Resolve points to get forecast URL
            r_points = requests.get(f"{self.base_url}/points/{lat},{lon}", headers=self.headers, timeout=10)
            r_points.raise_for_status()
            points_data = r_points.json()
            forecast_url = points_data.get("properties", {}).get("forecast")
            
            if not forecast_url:
                return None
                
            # 2. Fetch forecast
            r_forecast = requests.get(forecast_url, headers=self.headers, timeout=10)
            r_forecast.raise_for_status()
            forecast_data = r_forecast.json()
            
            periods = forecast_data.get("properties", {}).get("periods", [])
            for p in periods:
                start_time = p.get("startTime", "")
                # Format: 2026-02-07T06:00:00-05:00
                if start_time.startswith(target_date_str) and p.get("isDaytime"):
                    temp = p.get("temperature")
                    unit = p.get("temperatureUnit")
                    
                    # Return raw value and unit
                    res = {"max_temp": temp, "unit": unit}
                    
                    with open(cache_path, 'w') as f:
                        json.dump(res, f)
                    return res
                    
        except Exception as e:
            print(f"Error fetching NWS for {lat},{lon}: {e}")
            
        return None
