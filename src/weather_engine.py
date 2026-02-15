import math
import time
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
# Import clients - ensuring we use the updated ones
try:
    # 1. Relative import (for package execution)
    from .nws_client import NWSClient
    from .openmeteo_client import OpenMeteoClient
    from .polymarket_client import PolymarketClient
except (ImportError, ValueError):
    try:
        # 2. Absolute import via src (for root execution)
        from src.nws_client import NWSClient
        from src.openmeteo_client import OpenMeteoClient
        from src.polymarket_client import PolymarketClient
    except ImportError:
        # 3. Direct import (for execution inside src)
        from nws_client import NWSClient
        from openmeteo_client import OpenMeteoClient
        from polymarket_client import PolymarketClient

class WeatherEngine:
    def __init__(self):
        self.nws_client = NWSClient()
        self.om_client = OpenMeteoClient()
        
        # Exact City List & Rules
        self.cities_config = {
            "London": {"api": "OM", "unit": "C", "country": "UK"},
            "Toronto": {"api": "OM", "unit": "C", "country": "CA"},
            "Ankara": {"api": "OM", "unit": "C", "country": "TR"},
            "Seattle": {"api": "OM", "unit": "F", "country": "US"},
            "Miami": {"api": "OM", "unit": "F", "country": "US"},
            "Atlanta": {"api": "OM", "unit": "F", "country": "US"},
            "Chicago": {"api": "OM", "unit": "F", "country": "US"},
            "Dallas": {"api": "OM", "unit": "F", "country": "US"},
            "New York": {"api": "OM", "unit": "F", "country": "US"}
        }
        
        # Cache for forecasts: { "City_Date": {max_temp, unit} }
        self.forecast_cache = {}

    def fetch_forecast(self, city: str, date_str: str) -> Optional[Dict[str, Any]]:
        """
        Fetch forecast respecting the strict API rules.
        """
        # Normalize city key (Title Case for Config)
        # Config keys are "London", "Seattle", etc.
        # Handle "new york" -> "New York" if needed, but config keys are single words mostly.
        # Actually our keys are "London", "Toronto", "Ankara", "Seattle", "Miami", "Atlanta".
        city_key = city.title() 
        
        config = self.cities_config.get(city_key)
        if not config:
            # Try manual map for specific cases if needed
            print(f"[Error] Config not found for {city} (key: {city_key})")
            return None

        # Check Cache
        cache_key = f"{city}_{date_str}"
        if cache_key in self.forecast_cache:
            return self.forecast_cache[cache_key]

        print(f"[Fetch] Getting forecast for {city} on {date_str} using {config['api']}...")
        
        result = None
        if config['api'] == "NWS":
            # NWS requires lat/lon
            result = self.nws_client.get_forecast(config['lat'], config['lon'], date_str)
        elif config['api'] == "OM":
            result = self.om_client.get_forecast(city, date_str)
            
        if result:
            # Validate Unit
            if result['unit'] != config['unit']:
                # This should ideally not happen if APIs are standard, but good to warn
                # Open-Meteo returns 'C' by default. NWS returns 'F' usually.
                # If NWS returns 'C' (unlikely for US points), we might need to handle it or error out.
                # For strictness: verify unit.
                if config['unit'] == 'F' and result['unit'] == 'wmoUnit:degC': # NWS sometimes uses weird unit codes
                     print(f"[Warning] Unit mismatch for {city}. Expected {config['unit']}, got {result['unit']}")
                pass 

            self.forecast_cache[cache_key] = result
            return result
        
        print(f"[Fail] No forecast data for {city}")
        return None

    def compute_bucket(self, temp: float) -> Optional[Dict[str, Any]]:
        """
        Strict Bucket Proximity Rule:
        U = ceil(T)
        delta = U - T
        Candidate if 0 < delta <= 0.3
        """
        try:
            u_bucket = math.ceil(temp)
            delta = u_bucket - temp
            
            # Round delta to avoid floating point weirdness like 0.30000000004
            delta = round(delta, 4)

            if delta == 0:
                return {"target_bucket": u_bucket, "delta": 0, "is_candidate": False, "reason": "Exact Integer"}
            
            if 0 < delta <= 0.3:
                return {"target_bucket": u_bucket, "delta": delta, "is_candidate": True}
            
            return {"target_bucket": u_bucket, "delta": delta, "is_candidate": False, "reason": "Delta > 0.3"}
            
        except Exception as e:
            print(f"[Error] Computing bucket for {temp}: {e}")
            return None

    def get_forecast_probability(self, city, date, outcome_range, unit="F", log=None):
        """
        Compatibility method for MarketScanner.
        Returns 0.99 if forecast is within range, 0.01 otherwise.
        """
        res = self.get_forecast_probability_detailed(city, date, outcome_range, unit, log)
        return res["consensus"]

    def get_forecast_probability_detailed(self, city, date, outcome_range, unit="F", log=None):
        """
        Compatibility method for PaperTrader.
        Returns detailed probability structure using the new strict forecast logic.
        """
        # Convert date "2026-02-12T00:00:00" -> "2026-02-12"
        if "T" in date:
            date = date.split("T")[0]
            
        forecast = self.fetch_forecast(city, date)
        
        # Default/Fallback Structure
        result = {
            "consensus": 0.5,
            "sources": {},
            "raw_values": {}
        }
        
        if not forecast:
            return result
            
        temp = forecast['max_temp']
        f_unit = forecast['unit']
        
        # Source Name based on Config (NWS or OpenMeteo)
        config = self.cities_config.get(city)
        source_name = "NWS" if config and config['api'] == "NWS" else "OpenMeteo"
        
        # record raw value
        result["raw_values"][source_name] = temp
        
        # Check Unit Mismatch
        if unit != f_unit:
            # If units don't match, we return 0 probability to be safe (or 0.5?)
            # PaperTrader expects consensus.
            result["consensus"] = 0.0
            return result

        try:
            min_val = float(outcome_range[0])
            max_val = float(outcome_range[1])
            
            # Simple Binary Probability based on Forecast
            if min_val <= temp <= max_val:
                prob = 0.99
            else:
                prob = 0.01
                
            result["consensus"] = prob
            result["sources"][source_name] = prob
            
        except Exception as e:
            print(f"[Error] Calculating detailed probability: {e}")
            result["consensus"] = 0.5
            
        return result

    def find_polymarket_match(self, city: str, date_str: str, target_bucket: int, unit: str, markets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Search provided markets for specific bucket match.
        """
        try:
            # Filter markets for this city and date
            # MarketScanner has already parsed some info, but let's look at raw questions/slugs
            
            # Date Matching
            # date_str is YYYY-MM-DD
            # PM markets have 'endDate'.
            # Or we match title "... on February 10"
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            month_day = dt.strftime("%B") + " " + str(dt.day) # "February 10" (no leading zero typically in PM titles?)
            # Sometimes "February 04" or "February 4"? PM usually "February 4".
            
            # Let's check matching logic
            potential_markets = []
            for m in markets:
                # Check City (case insensitive)
                if city.lower() not in m['question'].lower() and city.lower() not in m['slug'].lower():
                    continue
                
                # Check Date
                # endDate is often ISO. Title has readable date.
                if month_day.lower() not in m['question'].lower():
                    # Try alternate date format?
                    pass
                
                potential_markets.append(m)

            for m in potential_markets:
                # Check Outcomes
                outcomes = json.loads(m['outcomes']) if isinstance(m['outcomes'], str) else m['outcomes']
                
                for out in outcomes:
                    label = out.lower()
                    u_str = str(target_bucket)
                    
                    # Patterns to match ">= U" or "Over U"
                    # "36 or higher"
                    # "Over 35.5" (if U=36) - Wait, prompt says "Over U" explicitly?
                    # "Over U" -> "Over 36"
                    
                    match_found = False
                    if f">= {u_str}" in label: match_found = True
                    if f"{u_str} or higher" in label: match_found = True
                    if f"over {u_str}" in label: match_found = True
                    
                    if match_found:
                        return {"market_id": m['id'], "outcome": out, "question": m['question'], "market_slug": m['slug']}
                        
            return None
            
        except Exception as e:
            print(f"[Error] PM Search: {e}")
            return None
            
    def discover_opportunities(self, markets: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        """
        Main loop to discover opportunities using strict logic and provided markets.
        """
        opportunities = []
        today = datetime.now()
        dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
        
        print("\n--- Starting Opportunity Discovery ---")
        
        for city in self.cities_config:
            print(f"\nAnalyzing {city}...")
            for d in dates:
                date_str = d.strftime("%Y-%m-%d")
                
                # 1. Fetch Forecast
                forecast = self.fetch_forecast(city, date_str)
                if not forecast:
                    continue
                
                temp = forecast['max_temp']
                unit = forecast['unit']
                
                # 2. Compute Bucket
                bucket_info = self.compute_bucket(temp)
                if not bucket_info:
                    continue
                
                print(f"  [{date_str}] Temp: {temp}°{unit} -> Target: {bucket_info['target_bucket']} (Delta: {bucket_info['delta']})")
                
                if bucket_info['is_candidate']:
                    # 3. Check Polymarket
                    print(f"    -> CANDIDATE! Checking matches in {len(markets)} markets...")
                    
                    match = self.find_polymarket_match(city, date_str, bucket_info['target_bucket'], unit, markets)
                    
                    if match:
                        print(f"    [MATCH FOUND] {match['question']}")
                        opportunities.append({
                            "city": city,
                            "date": date_str,
                            "forecast_max": temp,
                            "unit": unit,
                            "target_bucket": bucket_info['target_bucket'],
                            "delta": bucket_info['delta'],
                            "polymarket_market_id": match['market_id'],
                            "matched_outcome_label": match['outcome'],
                            "question": match['question'],
                            "market_slug": match['market_slug']
                        })
                    else:
                         print(f"    -> No matching Polymarket outcome found for '>= {bucket_info['target_bucket']}'")
                else:
                    print(f"    -> Ignored: {bucket_info.get('reason')}")
                    
        return opportunities

