"""Paper trading and market analysis module."""
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List, Callable

# Trading thresholds (can be moved to config.py)
MAX_PRICE_THRESHOLD = 0.18
MIN_EDGE_THRESHOLD = 0.06
HIGH_EDGE_THRESHOLD = 0.15
MIN_EDGE_WITH_PROXIMITY = 0.04
PROXIMITY_THRESHOLD = 0.15
CLOB_PRICE_MISMATCH_THRESHOLD = 0.4
TEMP_UPPER_BOUND = 150.0
TEMP_LOWER_BOUND = -50.0


class PaperTrader:
    """Analyzes markets and manages paper trading logic."""
    
    def __init__(self, weather_engine, poly_client=None):
        self.weather_engine = weather_engine
        self.poly_client = poly_client

    def _parse_friendly_date(self, date_text: str) -> Optional[str]:
        """Parse 'January 29' format to 'YYYY-MM-DD'."""
        try:
            year = datetime.now().year
            full_date_str = f"{date_text} {year}"
            dt = datetime.strptime(full_date_str, "%B %d %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
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
            city, val, condition = higher_match.group(1).strip(), int(higher_match.group(2)), "max_temp_above"
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
    
    # =========================================================================
    # REFACTORED HELPER METHODS
    # =========================================================================
    
    def _extract_city_from_slug(self, slug: str) -> str:
        """Extract city name from market slug."""
        if "highest-temperature-in-" in slug:
            parts = slug.split("-on-")[0].split("-in-")
            if len(parts) > 1:
                return parts[1].replace("-", " ")
        elif "-in-" in slug:
            parts = slug.split("-in-")
            if len(parts) > 1:
                return parts[1].split("-")[0]
        return "unknown"
    
    def _parse_outcome_range(
        self, 
        outcome_name: str, 
        question: str, 
        end_date: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Parse outcome name to extract temperature range.
        
        Returns (low, high) tuple or (None, None) if unparseable.
        """
        name = outcome_name.lower()
        
        # Range: "70-71" or "70 - 71"
        range_match = re.search(r'(-?\d+)\s*-\s*(-?\d+)', name)
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))
        
        # Comparison: "76 or higher" / "above 76" / "greater than 76"
        if any(word in name for word in ["higher", "above", "greater"]):
            comp_match = re.search(r'(-?\d+)', name)
            if comp_match:
                return float(comp_match.group(1)), TEMP_UPPER_BOUND
        
        # Comparison: "below 50" / "lower than 50" / "less than 50"
        if any(word in name for word in ["below", "lower", "less"]):
            comp_match = re.search(r'(-?\d+)', name)
            if comp_match:
                return TEMP_LOWER_BOUND, float(comp_match.group(1))
        
        # Exact value: "75"
        exact_match = re.search(r'(-?\d+)', name)
        if exact_match:
            val = float(exact_match.group(1))
            return val - 0.5, val + 0.5
        
        # Binary "Yes" - parse from question
        if name in ["yes", "yes!"]:
            _, q_cond, q_thresh, _ = self.parse_question(question, end_date)
            if q_cond == "max_temp" and q_thresh:
                return q_thresh - 0.5, q_thresh + 0.5
            elif q_cond == "max_temp_above" and q_thresh:
                return q_thresh, TEMP_UPPER_BOUND
            elif q_cond == "max_temp_below" and q_thresh:
                return TEMP_LOWER_BOUND, q_thresh
            elif q_cond == "temp_range":
                if isinstance(q_thresh, tuple):
                    return q_thresh
                elif q_thresh:
                    return q_thresh - 0.5, q_thresh + 0.5
            elif q_cond == "rain":
                return 0.5, 10.0
        
        return None, None
    
    def _format_log_details(self, city, low, high, date_str):
        """Formats log details: Tor(CA)-16°-9Feb2026"""
        # 1. Shorten City & Add Country
        exclude = ["The", "Of", "City"]
        short_city = city[:3]
        
        # Simple map for country codes (duplicates bot_service but safer for decoupling)
        cc_map = {
            "seattle": "US", "new york": "US", "chicago": "US", "miami": "US", 
            "los angeles": "US", "san francisco": "US", "austin": "US", "boston": "US", 
            "las vegas": "US", "phoenix": "US", "denver": "US",
            "london": "GB", "tokyo": "JP", "toronto": "CA", "mumbai": "IN", 
            "sao paulo": "BR", "paris": "FR", "berlin": "DE", "sydney": "AU", 
            "dubai": "AE", "singapore": "SG", "seoul": "KR", "rome": "IT", "madrid": "ES"
        }
        cc = cc_map.get(city.lower(), "??")
        
        # 2. Integer Target
        # If range is -15.5 to -14.5, target is -15.
        # If range is 9.5 to 10.5, target is 10.
        target = int((low + high) / 2) if low is not None and high is not None else "?"
        
        # 3. Date Format: YYYY-MM-DD -> 9Feb2026
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            fmt_date = dt.strftime("%d%b%Y")
        except:
            fmt_date = date_str
            
        return f"{short_city}({cc})-{target}°- {fmt_date}"

    def _get_token_id(
        self, 
        outcome_name: str, 
        index: int, 
        token_ids: List[str]
    ) -> Optional[str]:
        """Get the correct token ID for an outcome."""
        if not token_ids:
            return None
        
        # Binary markets have special handling
        is_binary = len(token_ids) == 2 and outcome_name.lower() in ["yes", "no"]
        
        if is_binary:
            if outcome_name.lower() == "yes":
                return token_ids[1]
            elif outcome_name.lower() == "no":
                return token_ids[0]
        elif len(token_ids) > index:
            return token_ids[index]
        
        return None
    
    def _fetch_clob_price(
        self, 
        token_id: str, 
        gamma_price: float,
        log: Optional[Callable] = None
    ) -> float:
        """
        Fetch real-time CLOB price, falling back to Gamma price if unavailable or mismatched.
        """
        if not self.poly_client or not token_id:
            return gamma_price
        
        clob_data = self.poly_client.get_clob_price(token_id)
        if not clob_data or not clob_data.get('price'):
            return gamma_price
        
        clob_price = clob_data['price']
        diff = abs(clob_price - gamma_price)
        
        # Sanity check: reject if prices differ too much
        if diff > CLOB_PRICE_MISMATCH_THRESHOLD:
            if log:
                log(f"  CLOB Price Mismatch (Gamma {gamma_price:.2f} vs CLOB {clob_price:.2f}). Using Gamma.")
            return gamma_price
        
        if log:
            log(f"  CLOB Refresh ({token_id[-4:]}): {gamma_price*100:.1f}% -> {clob_price*100:.1f}%")
        return clob_price
    
    def _check_proximity(
        self, 
        om_val: Optional[float], 
        low: float, 
        high: float
    ) -> bool:
        """Check if forecast value is within proximity threshold of the bucket."""
        if om_val is None:
            return False
        
        if low <= om_val <= high:
            return True
        
        dist_to_bucket = min(abs(om_val - low), abs(om_val - high))
        return dist_to_bucket <= PROXIMITY_THRESHOLD
    
    def _evaluate_outcome(
        self,
        outcome_name: str,
        index: int,
        gamma_price: float,
        city: str,
        target_date: str,
        market_unit: str,
        question: str,
        end_date: str,
        token_ids: List[str],
        log: Optional[Callable] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single outcome for trading opportunity.
        
        Returns signal dict if opportunity found, None otherwise.
        """
        # Skip dust prices
        if gamma_price < 0.01:
            return None
        
        # Parse outcome range
        low, high = self._parse_outcome_range(outcome_name, question, end_date)
        if low is None or high is None:
            return None
        
        # Get forecast probability
        forecast = self.weather_engine.get_forecast_probability_detailed(
            city, target_date, (low, high), market_unit, log=None
        )
        true_prob = forecast.get("consensus", 0.0)
        
        # Get real-time price if we have potential edge
        current_price = gamma_price
        if true_prob > (gamma_price + 0.03):
            token_id = self._get_token_id(outcome_name, index, token_ids)
            if token_id:
                current_price = self._fetch_clob_price(token_id, gamma_price, log)
        
        edge = true_prob - current_price
        
        # Check trading criteria
        if current_price >= MAX_PRICE_THRESHOLD or edge <= MIN_EDGE_THRESHOLD:
            if edge > 0.02 and log:
                log_details = self._format_log_details(city, low, high, target_date)
                log(f"  [NEAR MISS] {log_details} | {outcome_name} | Edge: {edge*100:.1f}% | Price: {current_price:.2f}")
            return None
        
        # Check proximity
        om_val = forecast.get("raw_values", {}).get("OpenMeteo")
        proximity_pass = self._check_proximity(om_val, low, high)
        
        # Must pass proximity OR have high edge
        if not proximity_pass and edge <= HIGH_EDGE_THRESHOLD:
            return None
        
        # Final edge sanity check
        if edge < MIN_EDGE_WITH_PROXIMITY:
            return None
        
        return {
            "true_prob": true_prob,
            "market_prob": current_price,
            "edge": edge,
            "action": f"BUY {outcome_name}",
            "outcome": str(outcome_name),
            "source_probs": forecast.get("sources", {}),
            "om_val": om_val,
            "target_int": (low, high),
            "legacy_pass": proximity_pass
        }
    
    # =========================================================================
    # MAIN ANALYSIS METHOD
    # =========================================================================

    def analyze_market(
        self, 
        market: Dict[str, Any], 
        scanner, 
        log: Optional[Callable] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a market for trading opportunities.
        
        Args:
            market: Market data dict from scanner
            scanner: MarketScanner instance for parsing
            log: Optional logging callback
        
        Returns:
            Signal dict if opportunity found, None otherwise
        """
        question = market['question']
        end_date = market.get('endDate', '')
        slug = market.get('slug', '')
        market_id = market.get('id', 'Unknown')
        
        # Extract city from slug
        city = self._extract_city_from_slug(slug)
        if city == "unknown":
            return None
        
        # Parse market metadata
        _, _, _, event_date = self.parse_question(question, end_date)
        parsed_meta = scanner.parse_market_title(question, city=city)
        market_unit = parsed_meta['unit']
        target_date = event_date or (end_date.split("T")[0] if end_date else None)
        
        if not target_date:
            return None
        
        # Skip past events
        if target_date < datetime.utcnow().strftime("%Y-%m-%d"):
            return None
        
        # Parse market data
        outcomes = market.get('outcomes', [])
        prices = market.get('outcomePrices', [])
        token_ids = market.get('clobTokenIds', [])
        
        if isinstance(token_ids, str):
            try:
                token_ids = json.loads(token_ids)
            except json.JSONDecodeError:
                token_ids = []
        
        if not prices or not outcomes:
            return None
        
        if log:
            log(f"[{city}] Evaluating {len(outcomes)} outcomes for Market {market_id}...")
        
        # Evaluate all outcomes and find best signal
        best_signal = None
        
        for i, outcome_name in enumerate(outcomes):
            gamma_price = float(prices[i]) if i < len(prices) else 0
            
            signal = self._evaluate_outcome(
                outcome_name=outcome_name,
                index=i,
                gamma_price=gamma_price,
                city=city,
                target_date=target_date,
                market_unit=market_unit,
                question=question,
                end_date=end_date,
                token_ids=token_ids,
                log=log
            )
            
            if signal and (best_signal is None or signal['edge'] > best_signal['edge']):
                signal['market_id'] = market_id
                signal['question'] = question
                signal['city'] = city
                best_signal = signal
                
                if log:
                    log(f"  --> [OPPORTUNITY] {outcome_name} | True: {signal['true_prob']*100:.1f}% | "
                        f"Price: {signal['market_prob']*100:.1f}% | Edge: {signal['edge']*100:.1f}%")
        
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
