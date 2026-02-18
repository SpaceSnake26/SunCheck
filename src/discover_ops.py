import math
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class OpportunityFinder:
    """
    Implements the STRICT opportunity discovery logic (v3).
    Source: Open-Meteo ONLY.
    Rule: U = ceil(T), 0 < delta <= 0.3.
    """
    def __init__(self, openmeteo_client):
        self.om = openmeteo_client
        self.cities_config = {
            "london": {"unit": "C"},
            "toronto": {"unit": "C"},
            "ankara": {"unit": "C"},
            "seattle": {"unit": "F"},
            "miami": {"unit": "F"},
            "atlanta": {"unit": "F"},
            "dallas": {"unit": "F"},
            "chicago": {"unit": "F"},
            "new york": {"unit": "F"}
        }

    def _log(self, msg, callback=None):
        if callback:
            callback(msg)
        else:
            print(msg)

    def compute_bucket(self, temp: float) -> Dict[str, Any]:
        """
        Core Rule:
        Target the nearest integer.
        If distance (delta) is <= 0.3 (and > 0), it is a candidate.
        This supports both rounding up (e.g. 62.8 -> 63) and rounding down (e.g. 61.2 -> 61).
        """
        floor_val = math.floor(temp)
        delta_floor = round(temp - floor_val, 4)
        
        ceil_val = math.ceil(temp)
        delta_ceil = round(ceil_val - temp, 4)
        
        # Pick the closer one
        if delta_floor <= delta_ceil:
            best_target = floor_val
            best_delta = delta_floor
        else:
            best_target = ceil_val
            best_delta = delta_ceil

        # "If 0 < delta <= 0.3 -> candidate"
        is_candidate = (0 < best_delta <= 0.3)
        
        return {
            "target_bucket": best_target,
            "delta": best_delta,
            "is_candidate": is_candidate
        }

    def find_polymarket_match(self, city: str, date_obj: datetime, target_bucket: int, markets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Matches a specific bucket (e.g. 72) to Polymarket outcomes.
        Target Date: YYYY-MM-DD
        """
    def find_polymarket_match(self, city: str, date_obj: datetime, target_bucket: int, markets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Matches a specific bucket (e.g. 72) to Polymarket outcomes.
        Target Date: YYYY-MM-DD
        """
        # Date Logic: Flexible
        target_month = date_obj.strftime("%B") # February
        target_day = str(date_obj.day) # 13
        
        # City Aliases
        aliases = {
            "new york": ["new york", "nyc", "ny"],
            "london": ["london"],
            "toronto": ["toronto"],
            "miami": ["miami"],
            "atlanta": ["atlanta"],
            "seattle": ["seattle"],
            "dallas": ["dallas"],
            "chicago": ["chicago"],
            "ankara": ["ankara"]
        }
        city_search_terms = aliases.get(city.lower(), [city.lower()])

        matched_market = None
        matched_outcome = None
        
        for m in markets:
            q = m['question'].lower()
            slug = m.get('slug', '').lower()
            
            # City Match (ANY alias)
            if not any(alias in q or alias in slug for alias in city_search_terms):
                continue
                
            # Date Match (Month AND Day)
            # Handle "Feb" vs "February" via substring logic?
            # "February" contains "Feb", so let's check short month.
            short_month = date_obj.strftime("%b").lower() # feb
            if short_month not in q:
                continue
            
            # Day check: "13" needs to be distinct (not 130).
            # Simple check: "13" in q. 
            if target_day not in q:
                continue
            
            # Outcome Logic - Check labels first
            outcomes = m['outcomes']
            if isinstance(outcomes, str): outcomes = json.loads(outcomes)
            
            u_val = target_bucket
            
            # Helper to check a string for the target bucket rules
            def check_label_for_match(label_text, val):
                lbl = label_text.lower().replace("°", "").replace("f", "").replace("c", "").strip()
                import re
                # Case 1: Range "40-41", "40 to 41"
                rm = re.search(r'(-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(-?\d+(?:\.\d+)?)', lbl)
                if rm:
                    try:
                        low = float(rm.group(1))
                        high = float(rm.group(2))
                        if low <= val <= high:
                            return True
                    except: pass
                        
                # Case 2: "41 or higher" / ">= 41"
                if "or higher" in lbl or "above" in lbl or ">=" in lbl or "over" in lbl:
                    nm = re.search(r'(-?\d+(?:\.\d+)?)', lbl)
                    if nm:
                        try:
                            cutoff = float(nm.group(1))
                            if val >= cutoff:
                                return True
                        except: pass

                # Case 3: "41 or lower" / "<= 41"
                if "or lower" in lbl or "below" in lbl or "<=" in lbl or "under" in lbl:
                    nm = re.search(r'(-?\d+(?:\.\d+)?)', lbl)
                    if nm:
                        try:
                            cutoff = float(nm.group(1))
                            if val <= cutoff:
                                return True
                        except: pass
                return False

            # 1. Check Outcomes (e.g. "40-41")
            for out in outcomes:
                if check_label_for_match(out, u_val):
                    matched_outcome = out
                    matched_market = m
                    break
            
            # 2. Check Question (e.g. "Will NY be 40-41?") -> Outcome "Yes"
            if not matched_outcome:
                # Only if outcomes are Yes/No style
                lower_outcomes = [o.lower() for o in outcomes]
                if "yes" in lower_outcomes:
                    # Check if Question contains the range matching U
                    # Be careful not to match "Feb 13" as a range!
                    # Only match if close to target bucket? (e.g. look for digits near U)
                    if check_label_for_match(q, u_val):
                         # Make sure we pick 'Yes' casing from list
                         idx = lower_outcomes.index("yes")
                         matched_outcome = outcomes[idx]
                         matched_market = m
                            
            if matched_outcome:
                break
                
        if matched_market and matched_outcome:
            return {
                "market": matched_market,
                "outcome_label": matched_outcome
            }
        # Debug: Print why we failed for City/Date matches
        # if city_search_terms[0] in q.lower():
        #     print(f"DEBUG: Failed match for {q} (Target U={target_bucket})")
        return None

    def discover(self, markets: List[Dict[str, Any]], log_callback=None) -> List[Dict[str, Any]]:
        opportunities = []
        today = datetime.now()
        
        # 3 Days tracking as requested
        dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
        
        for city_name, config in self.cities_config.items():
            for d in dates:
                d_str = d.strftime("%Y-%m-%d")
                
                # 1. Fetch Forecast
                forecast = self.om.get_forecast(city_name, d_str)
                if not forecast:
                    self._log(f"[{city_name}] No forecast for {d_str}", log_callback)
                    continue
                    
                temp = forecast['max_temp']
                unit = forecast['unit']
                
                # Verify Unit
                expected_unit = config['unit']
                if unit != expected_unit:
                    self._log(f"[{city_name}] Unit mismatch! Got {unit}, want {expected_unit}", log_callback)
                    continue
                    
                # 2. Compute Bucket
                res = self.compute_bucket(temp)
                u = res['target_bucket']
                delta = res['delta']
                is_candidate = res['is_candidate']
                
                self._log(f"[{city_name} {d_str}] T={temp}°{unit} -> U={u} (Δ={delta}) -> {'CANDIDATE' if is_candidate else 'Ignore'}", log_callback)
                
                if is_candidate:
                    # 3. Find Polymarket Match
                    match = self.find_polymarket_match(city_name, d, u, markets)
                    
                    if match:
                        market = match['market']
                        outcome_label = match['outcome_label']
                        
                        # Get price
                        prices = market.get('outcomePrices', [])
                        outcomes = market.get('outcomes', [])
                        try:
                            if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                            if isinstance(prices, str): prices = json.loads(prices)
                            
                            idx = outcomes.index(outcome_label)
                            price = float(prices[idx]) if idx < len(prices) else 0.0
                        except:
                            price = 0.0
                            
                        opp = {
                            "type": "weather_arbitrage_v3",
                            "city": city_name,
                            "date": d_str,
                            "forecast_max": temp,
                            "unit": unit,
                            "target_bucket": u,
                            "delta": delta,
                            "market_id": market['id'],
                            "question": market['question'],
                            "outcome": outcome_label,
                            "price": price,
                            "market": market,
                            "id": str(uuid.uuid4())
                        }
                        opportunities.append(opp)
                        self._log(f"  --> FOUND OPP: {market['question']} | {outcome_label} @ {price}", log_callback)
                    else:
                        self._log(f"  --> No matching market found for >= {u}", log_callback)

        return opportunities
