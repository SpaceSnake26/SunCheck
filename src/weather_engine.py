import requests
import math
import time
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

# Cache TTL constants (in hours)
CACHE_TTL_HOURS = 1  # Forecast cache TTL
CACHE_HISTORICAL_TTL_HOURS = 24  # Historical data cache TTL


class WeatherEngine:
    def __init__(self):
        self.open_meteo_url = "https://api.open-meteo.com/v1/forecast"
        self.visual_crossing_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        self.session = requests.Session()
        
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
        self.cache_file = os.path.join(os.path.dirname(__file__), "weather_cache.json")
        self.forecast_cache = self._load_cache() 

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from file, filtering out expired entries."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    raw_cache = json.load(f)
                # Filter expired entries
                return self._filter_expired_cache(raw_cache)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load cache: {e}")
                return {}
        return {}
    
    def _filter_expired_cache(self, cache: Dict[str, Any]) -> Dict[str, Any]:
        """Remove expired entries from cache."""
        now = datetime.utcnow()
        filtered = {}
        
        for key, value in cache.items():
            if isinstance(value, dict) and "_cached_at" in value:
                cached_at = datetime.fromisoformat(value["_cached_at"])
                ttl_hours = value.get("_ttl_hours", CACHE_TTL_HOURS)
                if now - cached_at < timedelta(hours=ttl_hours):
                    filtered[key] = value
            else:
                # Legacy cache entry without timestamp - keep but mark for refresh
                filtered[key] = value
        
        return filtered
    
    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached value if not expired."""
        if key not in self.forecast_cache:
            return None
        
        value = self.forecast_cache[key]
        
        # Check expiration for timestamped entries
        if isinstance(value, dict) and "_cached_at" in value:
            cached_at = datetime.fromisoformat(value["_cached_at"])
            ttl_hours = value.get("_ttl_hours", CACHE_TTL_HOURS)
            if datetime.utcnow() - cached_at >= timedelta(hours=ttl_hours):
                # Expired - remove from cache
                del self.forecast_cache[key]
                return None
            # Return the actual data (without metadata)
            return {k: v for k, v in value.items() if not k.startswith("_")}
        
        return value
    
    def _set_cached(self, key: str, value: Dict[str, Any], ttl_hours: int = CACHE_TTL_HOURS) -> None:
        """Set cached value with expiration timestamp."""
        cached_value = {
            **value,
            "_cached_at": datetime.utcnow().isoformat(),
            "_ttl_hours": ttl_hours
        }
        self.forecast_cache[key] = cached_value
        self._save_cache()

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.forecast_cache, f)
        except IOError as e:
            print(f"Warning: Failed to save cache: {e}")
    
    def clear_expired_cache(self) -> int:
        """Manually clear expired cache entries. Returns count of removed entries."""
        original_count = len(self.forecast_cache)
        self.forecast_cache = self._filter_expired_cache(self.forecast_cache)
        removed = original_count - len(self.forecast_cache)
        if removed > 0:
            self._save_cache()
        return removed

    def get_coordinates(self, city):
        city_slug = city.lower().replace(" ", "-")
        if city_slug in self.station_map:
            return self.station_map[city_slug]["lat"], self.station_map[city_slug]["lon"]
        
        if city in self.geo_cache: return self.geo_cache[city]
        try:
            r = self.session.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}, timeout=10)
            data = r.json()
            if "results" in data:
                res = (round(data["results"][0]["latitude"], 4), round(data["results"][0]["longitude"], 4))
                self.geo_cache[city] = res
                return res
        except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Warning: Geocoding failed for {city}: {e}")
        return None, None

    def _c_to_f(self, celsius):
        return (celsius * 9/5) + 32

    def _f_to_c(self, fahrenheit):
        return (fahrenheit - 32) * 5/9

    def _calculate_prob_cdf(self, forecast_val, threshold_low, threshold_high, sigma=None, lead_days=0):
        """
        Uses CDF to find probability that value falls between low and high.
        Dynamic Sigma scales with lead time.
        """
        if sigma is None:
            # V5.2: Optimistic Sigma (base 0.8 + 0.3 per day)
            # This allows for higher peak probabilities on near-term forecasts.
            sigma = 0.8 + (0.3 * lead_days)
            
        def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        try:
            p_high = phi((threshold_high - forecast_val) / sigma)
            p_low = phi((threshold_low - forecast_val) / sigma)
            return max(0, min(1, p_high - p_low))
        except:
            return 0.05

    def get_open_meteo_forecast(self, lat: float, lon: float, target_date: str) -> Optional[Dict[str, Any]]:
        """Fetch forecast from Open-Meteo API with caching."""
        cache_key = f"om_{lat}_{lon}_{target_date}"
        
        # Check cache first
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            params = {"latitude": lat, "longitude": lon, "daily": ["temperature_2m_max", "precipitation_sum"], "timezone": "auto"}
            r = self.session.get(self.open_meteo_url, params=params, timeout=10)
            data = r.json().get("daily", {})
            times = data.get("time", [])
            if target_date in times:
                idx = times.index(target_date)
                res = {"temp": data["temperature_2m_max"][idx], "precip": data["precipitation_sum"][idx]}
                self._set_cached(cache_key, res, ttl_hours=CACHE_TTL_HOURS)
                return res
        except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Warning: Open-Meteo forecast failed: {e}")
        return None

    def get_nws_forecast(self, lat, lon, target_date):
        """Using NWS Grid endpoints for US precision."""
        try:
            # 1. Get Point
            r = self.session.get(f"https://api.weather.gov/points/{lat},{lon}", timeout=10)
            forecast_url = r.json()["properties"]["forecast"]
            # 2. Get Forecast
            f_resp = self.session.get(forecast_url, timeout=10)
            periods = f_resp.json()["properties"]["periods"]
            for p in periods:
                if target_date in p["startTime"]:
                    # NWS gives simpler text usually "75" etc.
                    return {"temp": p.get("temperature"), "precip": 0.0 if "Clear" in p.get("shortForecast", "") else 0.5}
        except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Warning: NWS forecast failed: {e}")
        return None

    def get_visual_crossing_forecast(self, lat, lon, target_date):
        """Source 2: Visual Crossing (Global)"""
        import os
        # Try primary key from environment
        keys = [os.getenv("VISUAL_CROSSING_KEY")]
        for api_key in keys:
            if not api_key: continue
            try:
                url = f"{self.visual_crossing_url}/{lat},{lon}/{target_date}/{target_date}?key={api_key}&unitGroup=metric&include=days"
                r = self.session.get(url, timeout=10)
                if r.status_code == 200:
                    day_data = r.json().get("days", [{}])[0]
                    return {"temp": day_data.get("tempmax"), "precip": day_data.get("precip")}
            except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
                print(f"Warning: Visual Crossing forecast failed: {e}")
        return None

    def get_forecast_probability_detailed(self, city, date_str, outcome_range, market_unit="F", log=None):
        """
        Returns a dict with consensus prob AND individual source probs.
        """
        target_date = date_str.split("T")[0]
        lat, lon = self.get_coordinates(city)
        if not lat: return {"consensus": 0.0, "sources": {}}

        source_probs = {}
        
        # Helper to get prob for a source
        def calc_source_prob(forecast_data, name):
            if forecast_data and forecast_data["temp"] is not None:
                temp = forecast_data["temp"]
                # Unit conversion if needed
                if name == "OpenMeteo":
                    temp = temp if market_unit == "C" else self._c_to_f(temp)
                elif name == "VisualCrossing":
                    temp = temp if market_unit == "C" else self._c_to_f(temp)
                elif name == "NWS":
                    temp = temp if market_unit == "F" else self._f_to_c(temp)
                
                low = float(outcome_range[0])
                high = float(outcome_range[1])
                
                # Calculate Lead Days
                try:
                    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                    today_dt = datetime.utcnow()
                    lead_days = max(0, (target_dt - today_dt).days)
                except ValueError:
                    lead_days = 0
                    
                return self._calculate_prob_cdf(temp, low, high, lead_days=lead_days)
            return None

        # 1. Open-Meteo
        om_data = self.get_open_meteo_forecast(lat, lon, target_date)
        om_prob = calc_source_prob(om_data, "OpenMeteo")
        if om_prob is not None: source_probs["OpenMeteo"] = om_prob

        # 2. Visual Crossing
        vc_data = self.get_visual_crossing_forecast(lat, lon, target_date)
        vc_prob = calc_source_prob(vc_data, "VisualCrossing")
        if vc_prob is not None: source_probs["VisualCrossing"] = vc_prob

        # 3. NWS
        is_us = 24 < lat < 50 and -125 < lon < -66
        nws_prob = None
        if is_us:
            nws_data = self.get_nws_forecast(lat, lon, target_date)
            nws_prob = calc_source_prob(nws_data, "NWS")
            if nws_prob is not None: source_probs["NWS"] = nws_prob

        if not source_probs:
            return {"consensus": 0.0, "sources": {}}

        # Consensus is average of available probs
        consensus = sum(source_probs.values()) / len(source_probs)
        
        # KEY CHANGE: Expose RAW values for Proximity Strategy
        raw_values = {}
        if om_prob is not None and "temp" in om_data:
            # Re-apply unit conversion to get the display value
            val = om_data["temp"]
            if market_unit == "F": val = self._c_to_f(val) 
            raw_values["OpenMeteo"] = val
            
        return {
            "consensus": consensus,
            "sources": source_probs,
            "raw_values": raw_values
        }

    def get_forecast_probability(self, city, date_str, outcome_range, market_unit="F", log=None):
        """Legacy wrapper for simple prob call."""
        res = self.get_forecast_probability_detailed(city, date_str, outcome_range, market_unit, log)
        return res["consensus"]

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
            except (requests.RequestException, KeyError) as e:
                print(f"Warning: NWS daily data failed: {e}")

        # Source 2: Open-Meteo (Global / Fallback)
        try:
            params = {"latitude": lat, "longitude": lon, "daily": ["temperature_2m_max", "precipitation_sum"], "past_days": 14}
            r = self.session.get(self.open_meteo_url, params=params, timeout=10)
            data = r.json().get("daily", {})
            times = data.get("time", [])
            if target_date in times:
                idx = times.index(target_date)
                return {"max_temp": data["temperature_2m_max"][idx], "precip": data["precipitation_sum"][idx]}
        except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Warning: Open-Meteo daily data failed: {e}")
        return None
