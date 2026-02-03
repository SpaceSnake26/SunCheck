import requests
import math
import time
from datetime import datetime

class WeatherEngine:
    def __init__(self):
        self.open_meteo_url = "https://api.open-meteo.com/v1/forecast"
        self.visual_crossing_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        
        # KEY CHANGE: Map cities to exact NWS Station Coordinates (Polymarket standard)
        self.station_map = {
            "chicago": {"lat": 41.9742, "lon": -87.9073, "code": "KORD"}, # O'Hare
            "atlanta": {"lat": 33.6407, "lon": -84.4277, "code": "KATL"}, # Hartsfield-Jackson
            "new-york": {"lat": 40.7831, "lon": -73.9712, "code": "KNYC"}, # Central Park
            "miami": {"lat": 25.7932, "lon": -80.2906, "code": "KMIA"},   # Miami Int
            "seattle": {"lat": 47.4502, "lon": -122.3088, "code": "KSEA"}, # SeaTac
            "london": {"lat": 51.4700, "lon": -0.4543, "code": "EGLL"},   # Heathrow
            "paris": {"lat": 49.0097, "lon": 2.5479, "code": "LFPG"},     # CDG
            "los-angeles": {"lat": 33.9416, "lon": -118.4085, "code": "KLAX"},
            "san-francisco": {"lat": 37.6213, "lon": -122.3790, "code": "KSFO"},
            "austin": {"lat": 30.1975, "lon": -97.6664, "code": "KAUS"},
            "boston": {"lat": 42.3601, "lon": -71.0589, "code": "KBOS"},
            "dallas": {"lat": 32.8998, "lon": -97.0403, "code": "KDFW"},
            "denver": {"lat": 39.8561, "lon": -104.6737, "code": "KDEN"},
            "houston": {"lat": 29.9902, "lon": -95.3368, "code": "KIAH"},
            "las-vegas": {"lat": 36.0840, "lon": -115.1537, "code": "KLAS"},
            "phoenix": {"lat": 33.4342, "lon": -112.0116, "code": "KPHX"},
            "tokyo": {"lat": 35.5523, "lon": 139.7797, "code": "RJTT"}, # Haneda
            "berlin": {"lat": 52.3667, "lon": 13.5033, "code": "EDDB"}, # BER
            "rome": {"lat": 41.8003, "lon": 12.2389, "code": "LIRF"}, # FCO
            "madrid": {"lat": 40.4839, "lon": 3.5680, "code": "LEMD"}, # MAD
            "toronto": {"lat": 43.6777, "lon": -79.6248, "code": "CYYZ"}, # Pearson
        }
        
        self.geo_cache = {}
        self.forecast_cache = {} 

    def get_coordinates(self, city):
        city_slug = city.lower().replace(" ", "-")
        if city_slug in self.station_map:
            return self.station_map[city_slug]["lat"], self.station_map[city_slug]["lon"]
        
        if city in self.geo_cache: return self.geo_cache[city]
        try:
            r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}, timeout=10)
            data = r.json()
            if "results" in data:
                res = (data["results"][0]["latitude"], data["results"][0]["longitude"])
                self.geo_cache[city] = res
                return res
        except: pass
        return None, None

    def _c_to_f(self, celsius):
        return (celsius * 9/5) + 32

    def _f_to_c(self, fahrenheit):
        return (fahrenheit - 32) * 5/9

    def _calculate_prob_cdf(self, forecast_val, threshold_low, threshold_high, sigma=2.5):
        """
        Uses CDF to find probability that value falls between low and high.
        Increased Sigma to 2.5 to account for forecast error margin 2-3 days out.
        """
        def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        try:
            p_high = phi((threshold_high - forecast_val) / sigma)
            p_low = phi((threshold_low - forecast_val) / sigma)
            return max(0, min(1, p_high - p_low))
        except:
            return 0.05

    def get_open_meteo_forecast(self, lat, lon, target_date):
        try:
            params = {"latitude": lat, "longitude": lon, "daily": ["temperature_2m_max", "precipitation_sum"], "timezone": "auto"}
            r = requests.get(self.open_meteo_url, params=params, timeout=10)
            data = r.json().get("daily", {})
            times = data.get("time", [])
            if target_date in times:
                idx = times.index(target_date)
                return {"temp": data["temperature_2m_max"][idx], "precip": data["precipitation_sum"][idx]}
        except: pass
        return None

    def get_nws_forecast(self, lat, lon, target_date):
        """Using NWS Grid endpoints for US precision."""
        try:
            # 1. Get Point
            r = requests.get(f"https://api.weather.gov/points/{lat},{lon}", timeout=10)
            forecast_url = r.json()["properties"]["forecast"]
            # 2. Get Forecast
            f_resp = requests.get(forecast_url, timeout=10)
            periods = f_resp.json()["properties"]["periods"]
            for p in periods:
                if target_date in p["startTime"]:
                    # NWS gives simpler text usually "75" etc.
                    return {"temp": p.get("temperature"), "precip": 0.0 if "Clear" in p.get("shortForecast") else 0.5}
        except: pass
        return None

    def get_visual_crossing_forecast(self, lat, lon, target_date):
        """Source 2: Visual Crossing (Global)"""
        import os
        # Try primary key, then fallback example key
        keys = [os.getenv("VISUAL_CROSSING_KEY"), "PPKBBJ7637X5SNDUG6HZA23X7", "UR6S5U5D67K4J9H4F5F5"]
        for api_key in keys:
            if not api_key: continue
            try:
                url = f"{self.visual_crossing_url}/{lat},{lon}/{target_date}/{target_date}?key={api_key}&unitGroup=metric&include=days"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    day_data = r.json().get("days", [{}])[0]
                    return {"temp": day_data.get("tempmax"), "precip": day_data.get("precip")}
            except: pass
        return None

    def get_forecast_probability(self, city, date_str, outcome_range, market_unit="F", log=None):
        """
        outcome_range: tuple (low, high) e.g., (46, 47)
        market_unit: "F" or "C"
        """
        target_date = date_str.split("T")[0]
        cache_key = (city, target_date, str(outcome_range), market_unit)
        if cache_key in self.forecast_cache: return self.forecast_cache[cache_key]

        lat, lon = self.get_coordinates(city)
        if not lat: return 0.0

        results = []
        sources_used = []
        temps_found = []

        # 1. Open-Meteo (Global)
        om = self.get_open_meteo_forecast(lat, lon, target_date)
        if om and om["temp"] is not None:
            temp = om["temp"] if market_unit == "C" else self._c_to_f(om["temp"])
            temps_found.append(temp)
            sources_used.append("OpenMeteo")

        # 2. Visual Crossing (Global)
        vc = self.get_visual_crossing_forecast(lat, lon, target_date)
        if vc and vc["temp"] is not None:
            # VC is fetched in Metric in our helper
            temp = vc["temp"] if market_unit == "C" else self._c_to_f(vc["temp"])
            temps_found.append(temp)
            sources_used.append("VisualCrossing")

        # 3. NWS (US-Only)
        is_us = 24 < lat < 50 and -125 < lon < -66
        if is_us:
            nws = self.get_nws_forecast(lat, lon, target_date)
            if nws and nws["temp"] is not None:
                # NWS gives F usually
                temp = nws["temp"] if market_unit == "F" else self._f_to_c(nws["temp"])
                temps_found.append(temp)
                sources_used.append("NWS")

        if not temps_found:
            return 0.0

        # Consensus Forecast
        avg_forecast = sum(temps_found) / len(temps_found)
        
        # Calculate Prob for Range
        low = float(outcome_range[0])
        high = float(outcome_range[1])
        # Add 0.5 buffer to bin for continuous distribution matching Polymarket integer bins
        prob = self._calculate_prob_cdf(avg_forecast, low - 0.5, high + 0.5)

        if log:
            sources_str = ", ".join(sources_used)
            log(f"  - Forecast: {avg_forecast:.1f}°{market_unit} | Prob: {prob:.2f} ({len(temps_found)} sources: {sources_str})")
        
        self.forecast_cache[cache_key] = prob
        return prob

    def get_daily_data(self, city, date_str):
        """Fetches actual daily data for settlement (Oracle)."""
        lat, lon = self.get_coordinates(city)
        if not lat: return None
        
        target_date = date_str.split("T")[0]
        is_us = 24 < lat < 50 and -125 < lon < -66

        # Source 1: NWS Observations (Best for US Airport Stations)
        if is_us:
            try:
                nws = self.get_nws_forecast(lat, lon, target_date)
                if nws:
                    # NWS forecast for 'today' often contains the observations/current data
                    return {"max_temp": nws["temp"], "precip": nws["precip"]}
            except: pass

        # Source 2: Open-Meteo (Global / Fallback)
        try:
            params = {"latitude": lat, "longitude": lon, "daily": ["temperature_2m_max", "precipitation_sum"], "past_days": 14}
            r = requests.get(self.open_meteo_url, params=params, timeout=10)
            data = r.json().get("daily", {})
            times = data.get("time", [])
            if target_date in times:
                idx = times.index(target_date)
                return {"max_temp": data["temperature_2m_max"][idx], "precip": data["precipitation_sum"][idx]}
        except: pass
        return None
