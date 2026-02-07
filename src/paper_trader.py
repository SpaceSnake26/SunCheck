import re
import math
from datetime import datetime

class PaperTrader:
    def __init__(self, weather_engine, poly_client=None):
        self.weather_engine = weather_engine
        self.poly_client = poly_client

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
        # Standardize regex for robust city and negative parsing
        higher_pattern = r"highest temperature in (.+?)\s+be\s+(-?\d+).+?(?:higher|above|greater)"
        lower_pattern = r"highest temperature in (.+?)\s+be\s+(-?\d+).+?(?:below|lower|less)"
        range_pattern = r"highest temperature in (.+?)\s+be\s+between\s+(-?\d+)\s*-\s*(-?\d+)"
        exact_pattern = r"highest temperature in (.+?)\s+be\s+(-?\d+)(?:°?F|F|°?C|C)?(?:\s+on|\s*(\?|$))"

        higher_match = re.search(higher_pattern, question, re.IGNORECASE)
        lower_match = re.search(lower_pattern, question, re.IGNORECASE)
        range_match = re.search(range_pattern, question, re.IGNORECASE)
        exact_match = re.search(exact_pattern, question, re.IGNORECASE)

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

    def analyze_market(self, market, scanner, log=None):
        question = market['question']
        end_date = market['endDate']
        slug = market.get('slug', '')
        
        # 0. Robust City Extraction from Slug
        # Slugs: "highest-temperature-in-new-york-on-..."
        city = "unknown"
        if "highest-temperature-in-" in slug:
            parts = slug.split("-on-")[0].split("-in-")
            if len(parts) > 1:
                city = parts[1].replace("-", " ")
        elif "-in-" in slug:
            parts = slug.split("-in-")
            if len(parts) > 1:
                city = parts[1].split("-")[0]
        
        if city == "unknown": return None

        # 1. Parsing & Date
        _, cond_type, _, event_date = self.parse_question(question, end_date)
        parsed_meta = scanner.parse_market_title(question, city=city)
        market_unit = parsed_meta['unit']
        target_date = event_date if event_date else (end_date.split("T")[0] if end_date else None)

        if not target_date: return None
        
        # Skip past events
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        if target_date < today_str: return None

        outcomes = market.get('outcomes', [])
        prices = market.get('outcomePrices', [])
        token_ids = market.get('clobTokenIds', [])
        market_id = market.get('id', 'Unknown')
        
        if isinstance(token_ids, str):
            import json
            try: token_ids = json.loads(token_ids)
            except: pass

        if not prices or not outcomes: return None

        best_signal = None
        
        if log: log(f"[{city}] Evaluating {len(outcomes)} outcomes for Market {market_id}...")

        # EVALUATE ALL BUCKETS
        for i, outcome_name in enumerate(outcomes):
            name = str(outcome_name).lower()
            gamma_price = float(prices[i]) if i < len(prices) else 0
            
            if gamma_price < 0.01: continue
            
            # --- V5: Parse bucket range ---
            low, high = None, None
            # Range: "70-71" or "70 - 71"
            range_match = re.search(r'(\d+)\s*-\s*(\d+)', name)
            if range_match:
                low, high = float(range_match.group(1)), float(range_match.group(2))
            
            # Comparison: "76 or higher"
            elif "higher" in name or "above" in name or "greater" in name:
                comp_match = re.search(r'(-?\d+)', name)
                if comp_match:
                    low, high = float(comp_match.group(1)), 150.0 # Arbitrary high
            
            # Comparison: "below 50"
            elif "below" in name or "lower" in name or "less" in name:
                comp_match = re.search(r'(-?\d+)', name)
                if comp_match:
                    low, high = -50.0, float(comp_match.group(1)) # Arbitrary low
            
            # Exact/Binary: "Yes" or "75"
            else:
                match = re.search(r'(-?\d+)', name)
                if match:
                    val = float(match.group(1))
                    low, high = val - 0.5, val + 0.5
                elif name in ["yes", "yes!"]:
                    # For binary 'Yes', we use the threshold from the question
                    # e.g., "highest temperature will be 75 or higher"
                    # In this case cond_type and threshold are parsed from question
                    _, q_cond, q_thresh, _ = self.parse_question(question, end_date)
                    if q_cond == "max_temp":
                        low, high = q_thresh - 0.5, q_thresh + 0.5
                    elif q_cond == "max_temp_below":
                        low, high = -50.0, q_thresh
                    elif q_cond == "temp_range":
                        if isinstance(q_thresh, tuple): low, high = q_thresh
                        else: low, high = q_thresh - 0.5, q_thresh + 0.5
                    elif q_cond == "rain":
                        low, high = 0.5, 10.0 # Standard threshold for 'Will it rain?'
                
            if low is None or high is None: continue

            # --- V5: Compute REAL True Prob ---
            forecast_detailed = self.weather_engine.get_forecast_probability_detailed(
                city, target_date, (low, high), market_unit, log=None
            )
            true_prob = forecast_detailed.get("consensus", 0.0)
            
            # --- V5.1: CLOB Real-time Price Sync ---
            # Softened pre-filter (3% instead of 5%)
            current_price = gamma_price
            if true_prob > (gamma_price + 0.03): 
                # CRITICAL: Be extremely paranoid about Token ID order.
                # Standard: Index 0 = No, Index 1 = Yes.
                # Fallback: Assume i matches unless binary.
                t_id = None
                is_binary = (token_ids and len(token_ids) == 2 and outcome_name.lower() in ["yes", "no"])
                
                if is_binary:
                    if outcome_name.lower() == "yes": t_id = token_ids[1]
                    elif outcome_name.lower() == "no": t_id = token_ids[0]
                elif token_ids and len(token_ids) > i:
                    t_id = token_ids[i]
                
                if t_id and self.poly_client:
                    clob_data = self.poly_client.get_clob_price(t_id)
                    if clob_data and clob_data.get('price'):
                        # Sanity Check: If CLOB price is wildly different (>0.4 diff), likely bad mapping.
                        # Use Gamma price as fallback.
                        diff = abs(clob_data['price'] - gamma_price)
                        if diff > 0.4:
                             if log: log(f"  [{name}] CLOB Price Mismatch (Gamma {gamma_price:.2f} vs CLOB {clob_data['price']:.2f}). Fallback to Gamma.")
                             # Do NOT update current_price, keep Gamma.
                        else:
                             current_price = clob_data['price']
                             if log: log(f"  [{name}] CLOB Refresh ({t_id[-4:]}): Gamma {gamma_price*100:.1f}% -> CLOB {current_price*100:.1f}%")

            edge = true_prob - current_price
            
            # --- V5.1 Criteria: 18-cent limit + Meaningful Edge (6% instead of 10%) ---
            if current_price < 0.18 and edge > 0.06: 
                # --- MARKETSCANCRIT.MD Compliance: 15% Proximity check ---
                om_val = forecast_detailed.get("raw_values", {}).get("OpenMeteo")
                legacy_proximity_pass = False
                if om_val is not None:
                    dist_to_bucket = 0
                    if low <= om_val <= high: dist_to_bucket = 0
                    else: dist_to_bucket = min(abs(om_val - low), abs(om_val - high))
                    
                    if dist_to_bucket <= 0.15:
                        legacy_proximity_pass = True
                
                # We prioritize proximity (Legacy Rule), but allow high-edge distribution trades
                # V5.2: Relaxed edge (4%) if proximity passes
                if legacy_proximity_pass or edge > 0.15:
                    if best_signal is None or edge > best_signal['edge']:
                        # Final sanity check: edge must be at least 4% even with proximity
                        if edge < 0.04: continue 
                        
                        best_signal = {
                            "market_id": market_id,
                            "question": question,
                            "city": city,
                            "true_prob": true_prob,
                            "market_prob": current_price,
                            "edge": edge,
                            "action": f"BUY {outcome_name}",
                            "outcome": str(outcome_name),
                            "source_probs": forecast_detailed.get("sources", {}),
                            "om_val": om_val,
                            "target_int": (low, high),
                            "legacy_pass": legacy_proximity_pass
                        }
                        if log: log(f"  --> [OPPORTUNITY FOUND] {name} | True: {true_prob*100:.1f}% | Price: {current_price*100:.1f}% | Edge: {edge*100:.1f}% | Proximity: {legacy_proximity_pass}")
                elif edge > 0.02 and log:
                     log(f"  [NEAR MISS] {name} | Edge: {edge*100:.1f}% | Price: {current_price} (Limit 0.18) | Prox: {legacy_proximity_pass}")

        return best_signal

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
