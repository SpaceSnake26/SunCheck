import requests
import json

def diagnose():
    # Try the most likely slug
    slug = "highest-temperature-in-miami-on-february-9"
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    
    resp = requests.get(url).json()
    if not resp:
        print(f"No match for slug: {slug}")
        # Try search
        params = {"query": "Highest temperature in Miami on February 9", "limit": 5}
        resp = requests.get("https://gamma-api.polymarket.com/events", params=params).json()

    for event in resp:
        print(f"\nEVENT: {event.get('title')}")
        for m in event.get('markets', []):
            print(f"MARKET: {m.get('question')}")
            print(f"OUTCOMES {type(m.get('outcomes'))}: {m.get('outcomes')}")
            print(f"PRICES {type(m.get('outcomePrices'))}: {m.get('outcomePrices')}")
            
            # Print index/outcome pairs
            outcomes = m.get('outcomes', [])
            if isinstance(outcomes, str): outcomes = json.loads(outcomes)
            prices = m.get('outcomePrices', [])
            if isinstance(prices, str): prices = json.loads(prices)
            
            for i in range(len(outcomes)):
                p = prices[i] if i < len(prices) else "MISSING"
                print(f"  [{i}] {outcomes[i]} -> {p}")

if __name__ == "__main__":
    diagnose()
