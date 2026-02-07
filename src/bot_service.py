from market_scanner import MarketScanner
from weather_engine import WeatherEngine
from paper_trader import PaperTrader
from portfolio import PortfolioManager
from poly_client import PolyClient
import time
from datetime import datetime
import uuid
import os
import requests

# System Mode Logic and Data Aggregation
class BotService:
    def __init__(self):
        self.scanner = MarketScanner()
        self.weather = WeatherEngine()
        self.poly_client = PolyClient()
        self.trader = PaperTrader(self.weather, self.poly_client)
        self.portfolio = PortfolioManager()
        self.live_mode = True # Default to Live now as requested
        self.last_run = "Never"
        self.run_status = "Idle"
        self.logs = []
        self.proposed_trades = [] # List of dicts
        
        # UI Filters (Defaults)
        self.min_edge = 0.05
        self.max_settle_days = 5.0
        
        self.log("Bot Service Initialized [v2.fresh].")

    def log(self, message):
        """Adds a log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        self.logs.insert(0, entry) # Prepend for newest first
        if len(self.logs) > 100:
            self.logs.pop()

    def run_cycle(self):
        """Runs one complete bot cycle."""
        if self.run_status == "Running":
            self.log("Skipping cycle: Bot already running.")
            return

        self.run_status = "Running"
        self.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log("Starting bot cycle...")

        try:
            # 1. Settle Positions
            self.log("Step 1/3: Checking settlements...")
            settled_count = self.portfolio.settle_positions(self.trader)
            if settled_count > 0:
                self.log(f"Settled {settled_count} positions.")
            
            # 2. Scan for Opportunities (Snipes + Regular)
            self.log("Step 2/3: Scanning for weather opportunities...")
            # We use get_weather_markets and then analyze so we don't miss anything 
            # (scan_for_snipes is too restrictive for general use)
            markets = self.scanner.get_weather_markets(log_callback=self.log)
            
            if not markets:
                self.log("No markets found.")
            else:
                self.log(f"Found {len(markets)} markets. Analyzing with fresh pricing...")
                
                new_proposals = 0
                for market in markets:
                    # Duplicate Check (Active Positions & Already Proposed)
                    mid = market["id"]
                    if any(p["market_id"] == mid and p.get("status") != "CLOSED" for p in self.portfolio.data["positions"]):
                        continue
                    if any(prop["market"]["id"] == mid for prop in self.proposed_trades):
                        continue
                    
                    # --- FRESH PRICE UPDATE REMOVED ---
                    # Data API was returning inconsistent 1.00 prices. 
                    # check_trade_outcome or Gamma API prices are sufficient.
                    # --------------------------
                    # --------------------------

                    signal = self.trader.analyze_market(market, log=self.log)
                    if signal:
                        # NEW CRITERIA: 15%/15% logic already passed in analyze_market
                        market_price_yes = float(signal['market_prob'])
                        
                        # Calculate EV and Edge
                        ev = signal.get('ev', 0)
                        edge = signal.get('edge', 0)
                        
                        # Calculate Delta(API) for the UI
                        source_probs = signal.get("source_probs", {})
                        om_p = source_probs.get("OpenMeteo")
                        nws_p = source_probs.get("NWS")
                        vc_p = source_probs.get("VisualCrossing")
                        
                        delta_api = None
                        if om_p is not None:
                            if nws_p is not None:
                                delta_api = abs(om_p - nws_p) 
                            elif vc_p is not None:
                                delta_api = abs(om_p - vc_p)
                        
                        proposal = {
                            "id": str(uuid.uuid4()),
                            "market": market,
                            "signal": signal,
                            "outcome": signal.get('outcome', 'YES'),
                            "price": market_price_yes,
                            "edge": edge,
                            "ev": ev,
                            "delta_api": delta_api,
                            "is_snipe": True,
                            "timestamp": datetime.now().isoformat()
                        }
                        self.proposed_trades.append(proposal)
                        new_proposals += 1
                        self.log(f"!!! [OPPORTUNITY] Found arbitrage in {signal['city']} at {signal['target_int']}! Price: {market_price_yes*100:.1f}%")

                self.log(f"Cycle complete. {new_proposals} new opportunities found.")

                self.log(f"Cycle complete. {new_proposals} new opportunities found.")

        except Exception as e:
            self.log(f"ERR: Error in cycle: {e}")
        finally:
            self.run_status = "Idle"

    def approve_trade(self, trade_id, amount=20.0):
        """Approves and executes a proposed trade."""
        proposal = None
        for p in self.proposed_trades:
            if p["id"] == trade_id:
                proposal = p
                break
        
        if not proposal:
            return False, "Trade not found"
            
        # Execute
        market = proposal["market"]
        outcome = proposal["outcome"]
        price = proposal["price"]
        edge = proposal["edge"]
        city = proposal["signal"]["city"]
        
        market_prob = proposal["signal"]["market_prob"]
        true_prob = proposal["signal"]["true_prob"]
        
        if self.live_mode:
            # 1. Execute Real Trade via PolyClient
            success, msg = self.poly_client.execute_trade(market, outcome, price, amount)
            if success:
                self.log(f"LIVE EXECUTION SUCCESS: {outcome} on {city} | {msg}")
                # 2. Record in local portfolio for history/visibility (without deducting paper cash)
                self.portfolio.record_live_trade(market, outcome, price, amount, edge, market_prob=market_prob, true_prob=true_prob)
                self.proposed_trades.remove(proposal)
                return True, "Executed on Polymarket"
            else:
                self.log(f"LIVE EXECUTION FAILED: {msg}")
                return False, f"Exchange Error: {msg}"
        else:
            # Paper Trade
            if self.portfolio.execute_trade(market, outcome, price, amount, edge, market_prob=market_prob, true_prob=true_prob):
                self.log(f"PAPER EXECUTION: {outcome} on {city}")
                self.proposed_trades.remove(proposal)
                return True, "Paper Trade Executed"
            else:
                self.log(f"PAPER FAILED: Insufficient Funds for {city}")
                return False, "Insufficient Funds (Paper)"

    def reject_trade(self, trade_id):
        """Rejects/Deletes a proposed trade."""
        for p in self.proposed_trades:
            if p["id"] == trade_id:
                self.proposed_trades.remove(p)
                self.log(f"Rejected trade: {p['signal']['question']}")
                return True
        return False

    def get_context(self):
        """Returns context for the dashboard with dynamic filtering."""
        status = self.portfolio.get_status()
        
        # 1. Calculate "Settles In" and prepare list
        processed_trades = []
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        
        for p in self.proposed_trades:
            # Polymarket endDate is UTC
            end_date_str = p['market'].get('endDate')
            if end_date_str:
                try:
                    # Parse as UTC-aware
                    end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    diff = end_dt - now_utc
                    hours_left = diff.total_seconds() / 3600
                    
                    # Better handling: If it's today but in the past, it's 'Resolving'
                    if hours_left <= 0:
                        p['settles_in_hours'] = "Resolving"
                        p['settles_in_days'] = 0
                    else:
                        p['settles_in_hours'] = f"{int(hours_left)}h"
                        p['settles_in_days'] = hours_left / 24
                except:
                    p['settles_in_hours'] = "?"
                    p['settles_in_days'] = 999
            else:
                p['settles_in_hours'] = "?"
                p['settles_in_days'] = 999

            # 2. Apply Dynamic Filters
            # Edge filter (absolute)
            if abs(p['edge']) < self.min_edge:
                continue
            # Settle time filter
            if isinstance(p['settles_in_days'], (int, float)) and p['settles_in_days'] > self.max_settle_days:
                continue
                
            processed_trades.append(p)

        # 3. Sort Filtered Trades by Edge (Biggest on TOP)
        processed_trades.sort(key=lambda x: abs(x['edge']), reverse=True)

        if self.live_mode:
            cash = float(self.poly_client.get_balance() or 0)
            positions = self.poly_client.get_active_positions()
            # Current value is the most accurate reflection of portfolio health
            current_market_value = sum(float(p.get("cur_value") or 0) for p in positions)
            total_value = cash + current_market_value
            invested = sum(float(p.get("amount_invested") or 0) for p in positions)
            active_count = len(positions)
        else:
            cash = float(status.get("cash") or 0)
            positions = [p for p in self.portfolio.data["positions"] if not p.get("is_live")]
            invested = sum(float(p.get("amount_invested") or 0) for p in positions)
            total_value = cash + invested
            active_count = len(positions)

        history = self.portfolio.data["history"]
        return {
            "cash": cash,
            "live_mode": self.live_mode,
            "invested": invested,
            "total_value": total_value,
            "active_positions_count": active_count,
            "positions": positions, 
            "history": history,     
            "logs": self.logs,
            "last_run": self.last_run,
            "run_status": self.run_status,
            "proposed_trades": processed_trades,
            "min_edge": self.min_edge,
            "max_settle_days": self.max_settle_days
        }
