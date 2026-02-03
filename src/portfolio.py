import json
import os
from datetime import datetime

class PortfolioManager:
    def __init__(self, filename="portfolio.json"):
        # Resolve path relative to project root (one level up from src)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filename = os.path.join(base_dir, filename)
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default fresh state
        return {
            "cash": 1000.00,
            "positions": [],
            "history": []
        }

    def _save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)

    def execute_trade(self, market, outcome, price, amount_usd, edge, market_prob=0.0, true_prob=0.0):
        """
        Executes a paper trade.
        Returns True if successful, False if insufficient funds.
        """
        if self.data["cash"] < amount_usd:
            return False

        # Deduct cash
        self.data["cash"] -= amount_usd
        
        # Add position
        position = {
            "market_id": market['id'],
            "question": market['question'],
            "city": market.get('city', 'Unknown'), # Passed from signal
            "outcome": outcome,
            "price": price,
            "shares": amount_usd / price,
            "amount_invested": amount_usd,
            "edge": edge,
            "market_prob": market_prob,
            "true_prob": true_prob,
            "timestamp": datetime.now().isoformat()
        }
        self.data["positions"].append(position)
        
        # Log to history
        self.data["history"].append({
            "action": "BUY",
            "market_id": market['id'],
            "amount": amount_usd,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_data()
        return True

    def record_live_trade(self, market, outcome, price, amount_usd, edge, market_prob=0.0, true_prob=0.0):
        """
        Records a live trade in the portfolio without deducting paper cash.
        """
        # Add position
        position = {
            "market_id": market['id'],
            "question": market['question'],
            "city": market.get('city', 'Unknown'),
            "outcome": outcome,
            "price": price,
            "shares": amount_usd / price,
            "amount_invested": amount_usd,
            "edge": edge,
            "market_prob": market_prob,
            "true_prob": true_prob,
            "is_live": True,
            "timestamp": datetime.now().isoformat()
        }
        self.data["positions"].append(position)
        
        # Log to history
        self.data["history"].append({
            "action": "BUY_LIVE",
            "market_id": market['id'],
            "amount": amount_usd,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_data()
        return True

    def get_status(self):
        """
        Returns dict with current status.
        """
        total_invested = sum(p["amount_invested"] for p in self.data["positions"])
        return {
            "cash": self.data["cash"],
            "invested": total_invested,
            "total_value": self.data["cash"] + total_invested, # Simplistic (mark-to-market would use current price)
            "positions_count": len(self.data["positions"])
        }

    def settle_positions(self, paper_trader):
        """
        Checks open positions and settles them if possible.
        """
        settled_count = 0
        current_year =  datetime.now().year
        
        for p in self.data["positions"]:
            if p.get("status") == "CLOSED":
                continue
                
            question = p["question"]
            
            # Try to determine date from question if not stored
            # Ideally we should store endDate in position
            end_date = p.get("endDate")
            
            if not end_date:
                # Heuristic parsing for "on Month DD"
                import re
                date_match = re.search(r"on (January|February|March|April|May|June|July|August|September|October|November|December) (\d+)", question, re.IGNORECASE)
                if date_match:
                    month_str = date_match.group(1)
                    day = int(date_match.group(2))
                    try:
                        dt = datetime.strptime(f"{current_year} {month_str} {day}", "%Y %B %d")
                        end_date = dt.strftime("%Y-%m-%d")
                    except:
                        pass
            
            if not end_date:
                # Can't settle without date
                continue
            
            # CRITICAL: Only settle if the day is OVER
            today_str = datetime.now().strftime("%Y-%m-%d")
            if end_date >= today_str:
                # Still waiting for this day to finish or it is today.
                continue
                
            # Check outcome
            result = paper_trader.check_trade_outcome(question, end_date)
            
            if result:
                # "YES" or "NO" returned by ground truth check
                # Our position outcome is p["outcome"] (YES or NO)
                
                did_win = (result == p["outcome"])
                
                p["status"] = "CLOSED"
                p["result"] = "WON" if did_win else "LOST"
                p["settled_date"] = datetime.now().isoformat()
                
                payout = 0.0
                if did_win:
                    # Assuming 100% payout ($1 per share)
                     payout = p["shares"] * 1.0
                
                p["payout"] = payout
                self.data["cash"] += payout
                
                print(f"Settled {question[:30]}... Result: {p['result']}, Payout: ${payout:.2f}")
                settled_count += 1
                
                # Log to history
                self.data["history"].append({
                    "action": "SETTLE",
                    "market_id": p["market_id"],
                    "amount": payout,
                    "result": p["result"],
                    "timestamp": datetime.now().isoformat()
                })
        
        if settled_count > 0:
            self._save_data()
        
        return settled_count
