import re
import math
from datetime import datetime

class PaperTrader:
    def __init__(self, weather_engine):
        self.weather_engine = weather_engine

    def _parse_friendly_date(self, date_text):
        try:
             year = datetime.now().year
             full_date_str = f"{date_text} {year}"
             dt = datetime.strptime(full_date_str, "%B %d %Y")
             return dt.strftime("%Y-%m-%d")
        except:
             return None

    def parse_question(self, question, endDate):
        """Extracts City, Condition Type, Threshold, and Event Date from question."""
        city = None
        condition = None
        threshold_val = None
        event_date = None
        
        # 1. Highest Temperature (Seattle/London style)
        higher_match = re.search(r"highest temperature in (.+?) be (\d+).+?(?:higher|above|greater)", question, re.IGNORECASE)
        lower_match = re.search(r"highest temperature in (.+?) be (\d+).+?(?:below|lower|less)", question, re.IGNORECASE)
        range_match = re.search(r"highest temperature in (.+?) be between (\d+)\s*-\s*(\d+)", question, re.IGNORECASE)
        exact_match = re.search(r"highest temperature in (.+?) be (\d+)(?:°?F|F|°?C|C)?(?:\s+on|\s*(\?|$))", question, re.IGNORECASE)
        
        # Fallback recursive search if prefix like "Will the" exists
        if not exact_match and not higher_match and not range_match:
             higher_match = re.search(r"highest temperature in (.+?) be (\d+).+?(?:higher|above|greater)", question, re.IGNORECASE)
             lower_match = re.search(r"highest temperature in (.+?) be (\d+).+?(?:below|lower|less)", question, re.IGNORECASE)
             range_match = re.search(r"highest temperature in (.+?) be between (\d+)\s*-\s*(\d+)", question, re.IGNORECASE)
             exact_match = re.search(r"highest temperature in (.+?) be (\d+)(?:°?F|F|°?C|C)?(?:\s+on|\s*(\?|$))", question, re.IGNORECASE)

        if higher_match:
            city, val, condition = higher_match.group(1).strip(), int(higher_match.group(2)), "max_temp"
        elif lower_match:
            city, val, condition = lower_match.group(1).strip(), int(lower_match.group(2)), "max_temp_below"
        elif range_match:
            city, low, high, condition = range_match.group(1).strip(), int(range_match.group(2)), int(range_match.group(3)), "temp_range"
            val = (low, high)
        elif exact_match:
            city, val, condition = exact_match.group(1).strip(), int(exact_match.group(2)), "temp_range"
            val = (val - 0.5, val + 0.5)

        if condition:
            threshold_val = val
            
            # Extract Date
            date_match = re.search(r"on ([A-Z][a-z]+ \d{1,2})", question)
            if date_match: event_date = self._parse_friendly_date(date_match.group(1))

        # 2. Rain
        elif "rain" in question.lower() or "precipitation" in question.lower():
            city_match = re.search(r"in ([A-Z][a-z\s]+)\??", question)
            if city_match:
                city = city_match.group(1).strip()
                condition = "rain"
                threshold_val = 0.5

        return city, condition, threshold_val, event_date

    def analyze_market(self, market, log=None):
        from market_scanner import MarketScanner
        scanner = MarketScanner()
        
        question = market['question']
        end_date = market['endDate']
        slug = market.get('slug', '')
        
        # 0. Robust City Extraction
        slug_parts = slug.split("-")
        city = "unknown"
        if "in" in slug_parts:
            city = slug_parts[slug_parts.index("in") + 1]
        elif "at" in slug_parts:
            city = slug_parts[slug_parts.index("at") + 1]
        
        if city == "unknown": return None

        # 1. Parsing & Date
        _, cond_type, threshold, event_date = self.parse_question(question, end_date)
        parsed = scanner.parse_market_title(question, city=city)
        market_unit = parsed['unit']
        target_date = event_date if event_date else (end_date.split("T")[0] if end_date else None)

        if not cond_type or not target_date: 
            return None
        
        # 2. Market Strike Detection
        # Extract the strike value the market is actually betting on
        market_strike = None
        if isinstance(threshold, (int, float)):
            market_strike = int(threshold)
        elif isinstance(threshold, tuple) and len(threshold) == 2:
            # For ranges like 75-79, we'll check if our target falls inside
            pass 
        else:
            return None

        # 3. Forecast Check
        outcome_range = (0, 100)
        forecast_detailed = self.weather_engine.get_forecast_probability_detailed(
            city, target_date, outcome_range, market_unit=market_unit, log=None # Silent forecast
        )
        
        raw_values = forecast_detailed.get("raw_values", {})
        if "OpenMeteo" not in raw_values:
            return None
            
        om_val = raw_values["OpenMeteo"]
        target_int = math.ceil(om_val)

        # Skip past events
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        if target_date < today_str: return None

        # --- SMART LOGGING: Only log if this market matches our target strike ---
        is_target_match = False
        if market_strike == target_int:
            is_target_match = True
        elif isinstance(threshold, tuple) and threshold[0] <= target_int <= threshold[1]:
            is_target_match = True

        if not is_target_match:
            return None # SILENT SKIP for non-target markets

        # 4. Proximity Logic
        if target_int == om_val: 
            proximity = 0.0
        else:
            proximity = (target_int - om_val) / abs(om_val) if om_val != 0 else 0
            
        if proximity > 0.15:
            if log: log(f"[{city}] REJECTED: Forecast {om_val:.2f} too far from {target_int} ({proximity*100:.1f}%)")
            return None

        if log: log(f"[{city}] STEP 1 OK: Forecast {om_val:.2f} matches Strike {target_int} (Prox: {proximity*100:.1f}%)")

        # 5. Outcome & Price Check
        outcomes = market.get('outcomes', [])
        prices = market.get('outcomePrices', [])
        if not prices or not outcomes: 
            if log: log(f"[{city}] REJECTED: No PM data found.")
            return None

        found_idx = -1
        # Case A: Binary Market (Yes/No)
        if len(outcomes) == 2 and (outcomes[0].lower() in ["yes", "yes!"] or outcomes[1].lower() in ["no"]):
            found_idx = 0 # Bet on YES
        # Case B: Categorical Market (List of temperatures)
        else:
            for i, o in enumerate(outcomes):
                name = str(o).lower()
                
                # Try range match first: "70-71"
                range_match = re.search(r'(\d+)-(\d+)', name)
                if range_match:
                    low = int(range_match.group(1))
                    high = int(range_match.group(2))
                    if low <= target_int <= high:
                        found_idx = i
                        break
                
                # Try comparison matches: "76 or higher"
                if "higher" in name or "above" in name or "greater" in name:
                    comp_match = re.search(r'(\d+)', name)
                    if comp_match and target_int >= int(comp_match.group(1)):
                        found_idx = i
                        break
                        
                if "below" in name or "lower" in name or "less" in name:
                    comp_match = re.search(r'(\d+)', name)
                    if comp_match and target_int <= int(comp_match.group(1)):
                        found_idx = i
                        break

                # Fallback to simple integer exact match
                match = re.search(r'(\d+)', name)
                if match and int(match.group(1)) == target_int:
                    found_idx = i
                    break
        
        if found_idx == -1:
            if log: log(f"[{city}] REJECTED: Strike {target_int} not found in any outcome bucket.")
            return None
        
        # Step 3: Check PM Price ($0.18 limit)
        pm_prob = float(prices[found_idx])
        if pm_prob >= 0.18:
            if log: log(f"[{city}] REJECTED: PM Price {pm_prob*100:.1f}% >= 18%")
            return None
            
        if pm_prob < 0.01:
            return None # No liquidity

        # Arbitrage FOUND!
        if log: log(f"!!! [ARBITRAGE] Match in {city} for {target_int}!")

        # Arbitrage FOUND!
        if log: log(f"!!! [ARBITRAGE] Found opportunity in {city} for {target_int}{market_unit}!")
        
        true_prob = 0.99 
        return {
            "market_id": market['id'],
            "question": question,
            "city": city,
            "true_prob": true_prob,
            "market_prob": pm_prob,
            "edge": true_prob - pm_prob,
            "action": f"BUY {outcomes[found_idx]}",
            "outcome": str(outcomes[found_idx]),
            "source_probs": forecast_detailed.get("sources", {}),
            "proximity_match": True,
            "om_val": om_val,
            "target_int": target_int
        }

        return None

    def check_trade_outcome(self, question, end_date):
        """Checks if the trade won or lost based on actual weather data."""
        city, condition, threshold, event_date = self.parse_question(question, end_date)
        target_date_str = event_date if event_date else (end_date.split("T")[0] if end_date else None)
        if not city or not target_date_str: return None

        # Oracle Check: Use Open-Meteo as the settlement authority
        actual = self.weather_engine.get_daily_data(city, target_date_str)
        if not actual: return None

        max_t = actual['max_temp']
        rain = actual['precip']

        if condition == "max_temp": return "YES" if max_t >= threshold else "NO"
        if condition == "max_temp_below": return "YES" if max_t <= threshold else "NO"
        if condition == "temp_range": return "YES" if threshold[0] <= max_t <= threshold[1] else "NO"
        if condition == "rain": return "YES" if rain >= threshold else "NO"
        return None
