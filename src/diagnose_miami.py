import yaml
import os
import json
from poly_client import PolyClient

def diagnose():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    client = PolyClient(config['polymarket'])
    
    # Query for Miami markets
    print("Querying for Miami markets...")
    markets = client.get_markets(limit=20)
    miami_markets = [m for m in markets if "miami" in m.get("question", "").lower() or "miami" in m.get("title", "").lower()]
    
    for m in miami_markets:
        print(f"\nMarket: {m.get('question')}")
        print(f"Title: {m.get('title')}")
        print(f"Outcomes: {m.get('outcomes')}")
        print(f"OutcomePrices: {m.get('outcomePrices')}")
        print(f"BestBid: {m.get('bestBid')}")
        print(f"BestAsk: {m.get('bestAsk')}")
        
        # Check if it has the CLOB data/Orderbook
        orderbook = m.get('orderbook')
        if orderbook:
            print(f"Orderbook: Found")
        
        # Look for the 70-71 bucket
        if "outcomes" in m:
            for i, o in enumerate(m['outcomes']):
                if "70-71" in str(o):
                    price = m.get('outcomePrices', [])[i] if len(m.get('outcomePrices', [])) > i else "N/A"
                    print(f"--- MATCH found at index {i} (Correct Bucket: {o}), Price: {price}")

if __name__ == "__main__":
    diagnose()
