import time
import yaml
import os
from datetime import datetime, timedelta
from polymarket_client import PolymarketClient
from openmeteo_client import OpenMeteoClient
from nws_client import NWSClient
from market_parser import MarketParser
from storage import Storage
from notifier import Notifier

class WeatherScanner:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.pm_client = PolymarketClient()
        self.om_client = OpenMeteoClient()
        self.nws_client = NWSClient()
        self.parser = MarketParser()
        self.storage = Storage()
        self.notifier = Notifier(
            self.config.get("telegram_token"),
            self.config.get("telegram_chat_id")
        )
        
        # Coordinates for US cities (NWS)
        self.us_cities = {
            "miami": {"lat": 25.7617, "lon": -80.1918},
            "atlanta": {"lat": 33.7490, "lon": -84.3880},
            "seattle": {"lat": 47.6062, "lon": -122.3321},
            "chicago": {"lat": 41.8781, "lon": -87.6298}
        }
        # Non-US (Open-Meteo)
        self.intl_cities = ["london", "buenos aires", "seoul", "toronto"]

    def get_forecast_hybrid(self, city, date_str):
        """Routes to NWS for US cities and Open-Meteo for international."""
        city_low = city.lower()
        if city_low in self.us_cities:
            coords = self.us_cities[city_low]
            res = self.nws_client.get_forecast(coords["lat"], coords["lon"], date_str)
            if res:
                temp = res["max_temp"]
                # Convert F to C if NWS returned F (standard NWS unit)
                if res["unit"] == "F":
                    temp = (temp - 32) * 5/9
                return {"max_temp": temp, "unit": "C"}
        else:
            # International or fallback
            return self.om_client.get_forecast(city, date_str)
        return None

    def calculate_bet_size(self):
        bankroll = self.config.get("bankroll_usd", 1000)
        # bankroll * 0.15 * 0.03 rule
        return bankroll * 0.15 * 0.03

    def run_scan(self):
        self.notifier.notify("Starting weather arbitrage scan...")
        
        events = self.pm_client.get_weather_events()
        if not events:
            self.notifier.notify("No weather events found on Polymarket.")
            return

        opportunities = []
        watchlist = []

        total_bankroll = self.config.get("bankroll_usd", 1000)
        risk_cap = total_bankroll * 0.15
        edge_threshold = self.config.get("edge_threshold", 0.15)
        watchlist_delta = self.config.get("close_call_delta", 0.5)
        sigma = self.config.get("sigma", 1.0)

        for event in events:
            # Strictly filter for titles starting with "Highest temperature"
            if not event.get('title', '').lower().startswith("highest temperature"):
                continue

            markets = event.get('markets', [])
            print(f"  [PROCESSING] Event: {event['title']} ({len(markets)} markets)")
            for market in markets:
                q_text = market['question']
                if market.get('closed') or market.get('resolved'):
                    continue
                    
                parsed = self.parser.parse_question(q_text, context=event['title'])
                city = parsed['city']
                strike = parsed['strike']
                direction = parsed['direction']
                target_date = parsed['date']
                
                if not city or strike is None or not target_date:
                    continue

                # Filter: Today, Tomorrow and Day After
                today_dt = datetime.now()
                today_str = today_dt.strftime("%Y-%m-%d")
                tomorrow = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                day_after = (today_dt + timedelta(days=2)).strftime("%Y-%m-%d")
                allowed = [today_str, tomorrow, day_after]
                
                if target_date not in allowed:
                    print(f"    [SKIP DATE] {city} {target_date} not in {allowed}")
                    continue

                # Get Forecast using hybrid engine
                print(f"    [FETCHING] {city} for {target_date}...")
                forecast = self.get_forecast_hybrid(city, target_date)
                if not forecast:
                    print(f"    [SKIP FORECAST] {city} forecast returned None")
                    continue
                
                mu = forecast['max_temp']
                pm_prices = self.pm_client.get_prices(market['id'])
                p_pm = pm_prices['yes']
                
                # Convert strike to Celsius for the proximity check if it's in F
                strike_c = strike
                if parsed['unit'] == "F":
                    strike_c = (strike - 32) * 5/9

                # 15% Proximity Rule: abs(Forecast - Strike) / (Strike) < 0.15
                # (User's "under 15%" hint)
                temp_diff = abs(mu - strike_c)
                temp_proximity = temp_diff / (abs(strike_c) if strike_c != 0 else 1)
                is_close = temp_proximity < 0.15
                
                # 13% Price Rule: p_pm < 0.13
                is_cheap = p_pm < 0.13

                print(f"  [SIGNAL] {city}: Forecast {mu:.1f}°C, Strike {strike_c:.1f}°C | Diff: {temp_diff:.2f}, Price: {p_pm:.2f}")

                if is_close and is_cheap:
                    bet_size = self.calculate_bet_size()
                    signal_data = {
                        "market_id": market['id'],
                        "question": market['question'],
                        "city": city,
                        "date": target_date,
                        "forecast": mu,
                        "strike": strike_c,
                        "price": p_pm,
                        "diff": temp_diff,
                        "bet_size_usd": bet_size
                    }
                    opportunities.append(signal_data)
                    self.notifier.notify(
                        f"Opportunity in {city} ({target_date}): Diff {temp_diff:.2f} | Price {p_pm:.2f} | Bet: ${bet_size:.2f}",
                        tag="OPPORTUNITY"
                    )
                    self.storage.log_opportunity(signal_data)

        self.notifier.notify(f"Scan complete. {len(opportunities)} opportunities and {len(watchlist)} watchlist items found.")

if __name__ == "__main__":
    scanner = WeatherScanner()
    scanner.run_scan()
