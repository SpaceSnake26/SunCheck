import requests
import yaml
import json
import re
from datetime import datetime, timedelta
from market_parser import MarketParser
from probability_model import calculate_p_yes
from openmeteo_client import OpenMeteoClient

class Backtester:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.parser = MarketParser()
        self.om_client = OpenMeteoClient()
        self.gamma_api_url = "https://gamma-api.polymarket.com"

    def get_resolved_events(self):
        found_events = []
        for kw in ["temperature", "weather"]:
            params = {"query": kw, "closed": "true", "limit": 20}
            r = requests.get(f"{self.gamma_api_url}/events", params=params, timeout=10)
            found_events.extend(r.json())
        seen = {e['id'] for e in found_events}
        unique = []
        for e in found_events:
            if e['id'] in seen:
                unique.append(e)
                seen.remove(e['id'])
        return unique

    def get_historical_result(self, city_name, date_str):
        city = self.om_client.cities.get(city_name.lower())
        if not city:
            try:
                r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city_name, "count": 1})
                res = r.json()["results"][0]
                lat, lon = res["latitude"], res["longitude"]
            except: return None
        else:
            lat, lon = city["lat"], city["lon"]
        
        try:
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {"latitude": lat, "longitude": lon, "daily": "temperature_2m_max", "timezone": "auto", "start_date": date_str, "end_date": date_str}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            return data["daily"]["temperature_2m_max"][0]
        except: return None

    def run_backtest(self):
        print("--- DEBUG BACKTEST ---")
        events = self.get_resolved_events()
        
        signals_count = 0
        bankroll = self.config.get("bankroll_usd", 1000)
        bet_size = bankroll * 0.15 * 0.03
        
        for event in events:
            print(f"Processing Event: {event.get('title')}")
            r = requests.get(f"{self.gamma_api_url}/markets", params={"event_id": event['id']})
            markets = r.json()
            
            for m in markets:
                if not m.get('resolved'): continue
                
                parsed = self.parser.parse_question(m['question'])
                city_name = parsed['city']
                if not city_name:
                    match = re.search(r"in ([A-Z][a-z]+(?: [A-Z][a-z]+)?)", m['question'])
                    if match: city_name = match.group(1).lower().replace(" ", "-")

                if not city_name or not parsed['date']:
                    print(f"  FAILED Parse: {m['question']} (City: {city_name}, Date: {parsed['date']})")
                    continue
                
                actual_c = self.get_historical_result(city_name, parsed['date'])
                if actual_c is None:
                    print(f"  FAILED OmArchive: {city_name} on {parsed['date']}")
                    continue
                
                actual = actual_c if parsed['unit'] == "C" else (actual_c * 9/5) + 32
                prices = m.get("outcomePrices")
                entry_price = float(prices[0]) if prices else 0.5
                
                p_model = calculate_p_yes(actual, parsed['strike'], parsed['direction'])
                edge = p_model - entry_price
                print(f"  SUCCESS Analysis: Edge {edge:.2f} (Model {p_model:.2f} vs Market {entry_price:.2f})")
                
                if edge >= self.config.get("edge_threshold", 0.15):
                    signals_count += 1

        print(f"\nFinal Signal Count: {signals_count}")

if __name__ == "__main__":
    bt = Backtester()
    bt.run_backtest()
