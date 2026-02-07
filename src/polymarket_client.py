import requests
import json
import os
from datetime import datetime, timedelta

class PolymarketClient:
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"

    def get_weather_events(self):
        """
        High-precision discovery using exact slug probes and city-specific queries.
        Targets the 8 cities specified by the user.
        """
        target_cities = ["London", "Miami", "Buenos Aires", "Atlanta", "Seoul", "Seattle", "Toronto", "Chicago"]
        
        all_events = []
        seen_ids = set()
        
        # 1. Exact Slug Probes (Most Reliable)
        today = datetime.now()
        dates_to_check = []
        for i in range(3): # Today, Tomorrow, Day After
            dt = today + timedelta(days=i)
            m = dt.strftime("%B").lower()
            y = dt.year
            d = dt.day
            # Varients: "february-7-2026", "february-07-2026"
            dates_to_check.append(f"{m}-{d}-{y}")
            dates_to_check.append(f"{m}-{d:02d}-{y}")

        for city in target_cities:
            # Hyphenate city names for slugs: "Buenos Aires" -> "buenos-aires"
            city_low = city.lower().replace(" ", "-")
            for d_str in set(dates_to_check):
                slugs = [
                    f"highest-temperature-in-{city_low}-on-{d_str}",
                    f"highest-temperature-at-{city_low}-on-{d_str}" # Some use "at"
                ]
                for slug in slugs:
                    try:
                        r = requests.get(f"{self.gamma_api_url}/events", params={"slug": slug}, timeout=5)
                        if r.status_code == 200:
                            data = r.json()
                            if isinstance(data, list):
                                for e in data:
                                    eid = e.get('id')
                                    if eid and eid not in seen_ids:
                                        print(f"  [DISCOVERY] Found by Slug: {e.get('title')} (ID: {eid})")
                                        all_events.append(e)
                                        seen_ids.add(eid)
                    except: pass

        # 2. General Query Fallback (High Limit)
        try:
            # Search for "Highest temperature" with a high limit to find untracked cities
            params = {"query": "Highest temperature", "limit": 500}
            r = requests.get(f"{self.gamma_api_url}/events", params=params, timeout=10)
            if r.status_code == 200:
                for e in r.json():
                    eid = e.get('id')
                    if eid and eid not in seen_ids:
                        title = e.get('title', '').lower()
                        if "highest temperature" in title:
                            # Verify if it's one of our target cities
                            match = any(c.lower() in title for c in target_cities)
                            if match:
                                print(f"  [DISCOVERY] Found by Query: {e.get('title')} (ID: {eid})")
                                all_events.append(e)
                                seen_ids.add(eid)
        except: pass

        print(f"DEBUG: Found {len(all_events)} relevant weather events.")
        return all_events

    def get_event_markets(self, event_id):
        """Fetches all markets (conditions) for a specific event."""
        try:
            r = requests.get(f"{self.gamma_api_url}/markets", params={"event_id": event_id}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"Error fetching markets for event {event_id}: {e}")
            return []

    def get_prices(self, market_id):
        """Fetches latest prices for a market."""
        try:
            r = requests.get(f"{self.gamma_api_url}/markets/{market_id}", timeout=10)
            r.raise_for_status()
            data = r.json()
            
            # Outcome prices are strings in Gamma API, e.g. ["0.5", "0.5"]
            raw_prices = data.get("outcomePrices")
            prices = [0.5, 0.5] # Default fallback
            
            if isinstance(raw_prices, list):
                for i in range(min(len(raw_prices), 2)):
                    try:
                        val = raw_prices[i]
                        if val and str(val).lower() != "nan":
                            prices[i] = float(val)
                    except (ValueError, TypeError):
                        pass
            
            return {
                "yes": prices[0],
                "no": prices[1]
            }
        except Exception as e:
            print(f"Error fetching prices for market {market_id}: {e}")
            return {"yes": 0.5, "no": 0.5}
