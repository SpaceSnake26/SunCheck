import requests
import json

def diagnose():
    url = "https://gamma-api.polymarket.com/events"
    params = {"query": "Miami", "limit": 20}
    
    resp = requests.get(url, params=params).json()
    print(f"Found {len(resp)} events for Miami query.")
    
    for event in resp:
        print(f"\nEvent: {event.get('title')} (Slug: {event.get('slug')})")
        for market in event.get('markets', []):
            print(f"  Market: {market.get('question')}")
            print(f"  ID: {market.get('id')}")
            
            outcomes = market.get('outcomes', [])
            prices = market.get('outcomePrices', [])
            
            # Robust JSON parsing for outcomes/prices if strings
            if isinstance(outcomes, str):
                try: outcomes = json.loads(outcomes)
                except: pass
            if isinstance(prices, str):
                try: prices = json.loads(prices)
                except: pass
                
            print(f"  Outcomes: {outcomes}")
            print(f"  Prices: {prices}")
            
            # Look for 70-71 bucket
            for i, o in enumerate(outcomes):
                if "70-71" in str(o):
                    p = prices[i] if i < len(prices) else "N/A"
                    print(f"  >>> BUCKET MATCH: {o} | Price: {p}")

if __name__ == "__main__":
    diagnose()
