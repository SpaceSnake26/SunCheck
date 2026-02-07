import requests
import json
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

class MarketScanner:
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.session = requests.Session()


    def parse_market_title(self, title, city=None):
        """
        Extracts City, Date, Unit, and Type from title.
        Example: "Will the highest temperature in Atlanta be between 46-47°F on January 29?"
        """
        title = title.lower().replace("–", "-") # Normalize dashes
        
        # Determine Unit
        unit = None
        if "°c" in title or "celsius" in title:
            unit = "C"
        elif "°f" in title or "fahrenheit" in title:
            unit = "F"
        
        # Default based on city if not explicit
        if unit is None and city:
            international_cities = ["london", "paris", "tokyo", "berlin", "madrid", "rome", "seoul", "toronto", "buenos-aires"]
            if any(ic in city.lower() for ic in international_cities):
                unit = "C"
            else:
                unit = "F"
        elif unit is None:
            unit = "F" # Final fallback
            
        # Regex to find range like "46-47" or single value "11"
        range_match = re.search(r'(\d+)\s*-\s*(\d+)', title)
        single_match = re.search(r'(\d+)', title)
        
        val_min, val_max = None, None
        
        if range_match:
            val_min = float(range_match.group(1))
            val_max = float(range_match.group(2))
        elif single_match:
            val = float(single_match.group(1))
            val_min = val
            val_max = val 
            
        return {"unit": unit, "min": val_min, "max": val_max}

    def scan_for_snipes(self, weather_engine, log_callback=None):
        """
        Finds markets where Price is < 10 cents but Model Prob is high (Lottery Snipe).
        """
        def log(msg):
            if log_callback: log_callback(msg)
            print(msg)

        markets = self.get_weather_markets(log_callback=log_callback)
        opportunities = []

        log(f"Analyzing {len(markets)} markets for Snipes...")

        for m in markets:
            # Only look at "Temperature" markets for now
            if "temperature" not in m['question'].lower(): continue
            
            # Parse Title for Constraints
            parsed = self.parse_market_title(m['question'])
            if parsed['min'] is None: continue

            # Robust City Extraction
            slug_parts = m['slug'].split("-")
            # Usually: highest-temperature-in-CITY-on-MONTH-DAY
            if "in" in slug_parts:
                idx = slug_parts.index("in") + 1
                city = slug_parts[idx]
            else:
                city = "unknown"
                
            if city == "unknown": continue 
            
            # --- STRICT UNIT FILTER ---
            # Reject if unit doesn't match city region
            intl_cities = ["london", "paris", "tokyo", "berlin", "madrid", "rome", "dubai", "singapore", "toronto"]
            is_intl = any(ic in city.lower() for ic in intl_cities)
            
            if is_intl and parsed['unit'] == 'F':
                continue # Skip F markets for Intl
            if not is_intl and parsed['unit'] == 'C':
                continue # Skip C markets for US (mostly)
            # --------------------------

            # Get Forecast from Engine
            prob = weather_engine.get_forecast_probability(
                city, 
                m['endDate'], 
                (parsed['min'], parsed['max']), 
                parsed['unit'],
                log=None # Don't flood logs here
            )
            
            prices = m.get('outcomePrices')
            if not prices or not isinstance(prices, list): continue
            
            try:
                # Polymarket Yes is usually index 0
                yes_price = float(prices[0]) if prices and len(prices) > 0 else 0
                
                # SKIP if price is zero (closed or no liquidity)
                if yes_price < 0.01: continue

                # THE SNIPER FORMULA
                # 1. Price is cheap (Lottery Ticket)
                is_cheap = yes_price <= 0.10  # Max 10 cents
                
                # 2. We have an edge (Model says it's way more likely than price)
                # e.g. Price is 0.02 (2%), Model says 0.15 (15%). EV is 7.5x.
                has_edge = prob > (yes_price * 2.5) 
                
                if is_cheap and has_edge:
                    opportunities.append({
                        "id": m['id'],
                        "question": m['question'],
                        "city": city.capitalize(),
                        "market_price": yes_price,
                        "my_prob": prob,
                        "unit": parsed['unit'],
                        "edge": prob - yes_price,
                        "ev": prob / yes_price if yes_price > 0 else 0,
                        "market": m,
                        "outcome": "YES"
                    })
            except Exception as e:
                continue

        # Sort by best EV
        opportunities.sort(key=lambda x: x['ev'], reverse=True)
        return opportunities

    def _make_request(self, url, params=None, retries=3, backoff=1, log=None):
        """Helper to make robust requests with retries."""
        for attempt in range(retries):
            try:
                r = self.session.get(url, params=params, timeout=15)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                else:
                    if log: log(f"Request failed: {e}")
                    raise e
        return None

    def get_weather_markets(self, limit=150, log_callback=None):
        """
        Fetches active markets focusing ONLY on real weather (Temp, Rain, Snow).
        Uses concurrency for speed.
        """
        def log(msg):
            if log_callback: log_callback(msg)
            print(msg)

        weather_markets = []
        seen_ids = set()

        def process_event(event):
            title = event.get('title', '').lower()
            slug = event.get('slug', '').lower()
            markets = event.get('markets', [])
            
            # 1. STRICT AGGRESSIVE NEGATIVE FILTER
            negative_keywords = [
                'ukraine', 'token', 'coin', 'crypto', 'btc', 'eth', 'solana', 'price of',
                'nba', 'basketball', 'nfl', 'football', 'nhl', 'hockey', 'mlb', 'baseball',
                'vanguard', 's&p', 'stock', 'market cap', 'election', 'president', 'trump', 'biden',
                ' vs ', ' vs.', 'aapl', 'tsla', 'fed ', 'interest rate', 'elon', 'musk', 'pump.fun',
                'zcash', 'aster', 'plasma', 'uni reach', 'hurricane', 'named storm', 'typhoon', 'cyclone'
            ]
            
            if any(nk in title for nk in negative_keywords) or any(nk in slug for nk in negative_keywords):
                return

            # 2. POSITIVE WEATHER ONLY FILTER
            # We explicitly exclude 'hurricane' and 'ice' as requested (unless it's 'snow ice')
            weather_keywords = [
                r'\bweather\b', r'\btemperature\b', r'\bprecipitation\b', 
                r'\bsnow\b', r'\brain\b', r'\bdegree\b', r'\bforecast\b', 
                r'\bhighest temperature\b', r'\bcelsius\b', r'\bfahrenheit\b'
            ]
            
            is_weather = any(re.search(wk, title, re.IGNORECASE) for wk in weather_keywords) or \
                         any(re.search(wk, slug, re.IGNORECASE) for wk in weather_keywords)
            
            # Additional safety: explicitly exclude hurricane or troops/fighting even if title matches 'weather'
            if any(nk in title or nk in slug for nk in ['hurricane', 'troops', 'fighting', 'ceasefire', 'war']):
                is_weather = False
            
            if is_weather:
                for market in markets:
                    mid = market.get('id')
                    if mid in seen_ids: continue
                    
                    # --- STRICT UNIT FILTER (Inside Fetch Loop) ---
                    # 1. Parse Question for Unit
                    try:
                        parsed = self.parse_market_title(market.get('question', ''))
                        unit = parsed.get('unit')
                        
                        # 2. Parse Slug for City
                        # slug: highest-temperature-in-london-on-february-6
                        parts = slug.split("-")
                        city = "unknown"
                        if "in" in parts:
                            idx = parts.index("in") + 1
                            if idx < len(parts): city = parts[idx]
                            
                        # 3. Check Unit Consistency (Robust)
                        intl_cities = ["london", "paris", "tokyo", "berlin", "madrid", "rome", "dubai", "singapore", "toronto"]
                        is_intl = any(ic in city.lower() for ic in intl_cities) or "celsius" in title.lower() or "°c" in title.lower()
                        is_us = any(us in city.lower() for us in ["miami", "york", "chicago", "seattle", "austin", "los angeles", "vegas"]) or "fahrenheit" in title.lower() or "°f" in title.lower()
                        
                        if is_intl and unit == 'F' and not is_us: continue 
                        if not is_intl and unit == 'C': continue 
                    except (KeyError, IndexError, AttributeError):
                        pass
                    # --------------------------------------------
                    
                    outcomes = market.get('outcomes')
                    if isinstance(outcomes, str):
                        try: outcomes = json.loads(outcomes)
                        except json.JSONDecodeError: pass
                        
                    prices = market.get('outcomePrices')
                    if isinstance(prices, str):
                        try: prices = json.loads(prices)
                        except json.JSONDecodeError: pass
                        
                    token_ids = market.get('clobTokenIds')
                    if isinstance(token_ids, str):
                        try: token_ids = json.loads(token_ids)
                        except json.JSONDecodeError: pass

                    weather_markets.append({
                        "id": mid,
                        "question": market.get('question'),
                        "slug": event.get('slug'),
                        "outcomes": outcomes,
                        "outcomePrices": prices,
                        "clobTokenIds": token_ids,
                        "endDate": market.get('endDate')
                    })
                    seen_ids.add(mid)

        cities = ["london", "miami", "seattle", "toronto"]
        today = datetime.now()
        # Look ahead 3 days to match user's previous successful discovery
        optimized_slugs = []
        for city in cities:
            optimized_slugs.append(f"{city}-daily-weather")
            for i in range(3):
                d = today + timedelta(days=i)
                month = d.strftime('%B').lower()
                year = d.year
                day = d.day
                
                # Try multiple slug formats
                date_formats = [
                    f"{month}-{day}",
                    f"{month}-{day:02d}",
                    f"{month}-{day}-{year}",
                    f"{month}-{day:02d}-{year}"
                ]
                for df in date_formats:
                    optimized_slugs.append(f"highest-temperature-in-{city}-on-{df}")
                    optimized_slugs.append(f"highest-temperature-at-{city}-on-{df}")

        log(f"[cyan] Scanning optimized queries for {len(cities)} cities + Weather Tag...[/cyan]")
        
        # CONCURRENT EXECUTION
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 1. TAG SEARCH (Tag 1002 = Weather) - Primary Source - Limit increased to 250
            future_to_tag = {executor.submit(self._make_request, f"{self.gamma_api_url}/events", {"tag_id": 1002, "active": "true", "limit": limit}): "weather_tag"}
            
            # 2. Targeted Queries (City-by-city) - Increased limit
            future_to_query = {executor.submit(self._make_request, f"{self.gamma_api_url}/events", {"query": f"Highest temperature in {c}", "limit": 50}): f"query_{c}" for c in cities}
            
            # 3. Targeted Slugs
            future_to_slug = {executor.submit(self._make_request, f"{self.gamma_api_url}/events", {"slug": s}): s for s in optimized_slugs}

            total_futures = {**future_to_tag, **future_to_query, **future_to_slug}
            for future in as_completed(total_futures):
                try:
                    data = future.result()
                    if data:
                        for e in data:
                            process_event(e)
                except Exception as e:
                    print(f"Warning: Failed to process market event: {e}")

        log(f"[green] Scan complete. Found {len(weather_markets)} unique weather markets.[/green]")
        return weather_markets
