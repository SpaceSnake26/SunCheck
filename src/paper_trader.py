import re
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
        
        # 0. Robust City Extraction for Defaulting
        # Extract city from slug: highest-temperature-in-chicago-on-january-30
        slug_parts = market.get('slug', '').split("-")
        if "in" in slug_parts:
            idx = slug_parts.index("in") + 1
            city_slug = slug_parts[idx]
        else:
            city_slug = "unknown"

        # 1. Parse Question for Constraints and Unit
        parsed = scanner.parse_market_title(question, city=city_slug)
        city, condition, threshold, event_date = self.parse_question(question, end_date)
        
        # Ensure we use the scanner's unit detection for consistency
        market_unit = parsed['unit']
        
        target_date = event_date if event_date else (end_date.split("T")[0] if end_date else None)
        
        if not city or not condition: return None

        # 1. ALLOW SAME-DAY (Polymarket often has liquid same-day weather)
        # We only skip if the event_date is clearly in the past
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        if target_date and target_date < today_str:
            return None

        # 2. Extract Range
        if condition == "temp_range":
            outcome_range = threshold # (low, high)
        elif condition == "max_temp":
            outcome_range = (threshold, 150) # Assume upper bound far away
        elif condition == "max_temp_below":
            outcome_range = (-100, threshold) # Assume lower bound far away
        elif condition == "rain":
            outcome_range = (threshold, 100) # 0.5 inches or more
        else:
            return None

        if log: log(f"Analyzing Weather: {city} | Range: {outcome_range}°{market_unit} on {target_date}")
        
        # New Engine Call
        true_prob = self.weather_engine.get_forecast_probability(
            city, 
            target_date, 
            outcome_range, 
            market_unit=market_unit, 
            log=log
        )
        
        if true_prob is None: return None

        try:
            # FIX: Find the correct index for "Yes" price
            # Polymarket outcomePrices map to the outcomes array
            outcomes = market.get('outcomes', [])
            prices = market.get('outcomePrices', [])
            if not prices or not outcomes: return None
            
            yes_idx = -1
            for i, o in enumerate(outcomes):
                if o.lower() == "yes":
                    yes_idx = i
                    break
            
            if yes_idx == -1: return None # Not a binary YES/NO market
            
            market_prob = float(prices[yes_idx])
            if market_prob < 0.01: return None
            
            # 2. SKIP EXTREME PRICES unless we have massive edge
            # 2. SKIP EXTREME PRICES unless we have clear edge
            if (market_prob <= 0.03 or market_prob >= 0.97) and (abs(true_prob - market_prob) < 0.10):
                return None
        except Exception as e:
            if log: log(f"Error parsing market price: {e}")
            return None
            
        edge = true_prob - market_prob
        action = "HOLD"
        # Braver threshold for "OPPS"
        if edge > 0.08: action = "BUY_YES"
        elif edge < -0.08: action = "BUY_NO"
            
        return {
            "market_id": market['id'],
            "question": question,
            "city": city,
            "true_prob": true_prob,
            "market_prob": market_prob,
            "edge": edge,
            "action": action
        }

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
