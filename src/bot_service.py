from market_scanner import MarketScanner
from weather_engine import WeatherEngine
from paper_trader import PaperTrader
from portfolio import PortfolioManager
from poly_client import PolyClient
from notifier import Notifier, NotificationType
import time
from datetime import datetime
import uuid
import os
import requests
from discover_ops import OpportunityFinder

# System Mode Logic and Data Aggregation
class BotService:
    def __init__(self):
        self.scanner = MarketScanner()
        self.weather = WeatherEngine()
        self.poly_client = PolyClient()
        self.trader = PaperTrader(self.weather, self.poly_client)
        self.portfolio = PortfolioManager()
        self.finder = OpportunityFinder(self.weather.om_client)
        
        self.live_mode = True # Default to Live now as requested
        self.last_run = "Never"
        self.run_status = "Idle"
        self.logs = []
        self.proposed_trades = [] # List of dicts
        self.proposals_by_id = {} # O(1) lookup
        
        # UI Filters (Defaults)
        self.min_edge = 0.0
        self.max_price = 0.25
        self.max_settle_days = 5.0
        
        # Initialize notifier with log callback
        self.notifier = Notifier(log_callback=self._add_log_entry)
        
        self.log("Bot Service Initialized [v3.strict].")

    def log(self, message):
        """Adds a log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        self._add_log_entry(entry)
    
    def _add_log_entry(self, entry):
        """Internal method to add pre-formatted log entry."""
        self.logs.insert(0, entry)  # Prepend for newest first
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
            self.log("Step 1/2: Checking settlements...")
            settled_count = self.portfolio.settle_positions(self.trader)
            if settled_count > 0:
                self.log(f"Settled {settled_count} positions.")
            
            # 2. Scan & Discover (New Logic)
            self.log("Step 2/2: Discovering opportunities (Strict V3 Rules)...")
            
            # Fetch generic weather markets
            markets = self.scanner.get_weather_markets(limit=250, log_callback=self.log)
            
            if not markets:
                self.log("No markets found.")
            else:
                self.log(f"Found {len(markets)} candidate markets.")
                
                # Use OpportunityFinder
                new_opps = self.finder.discover(markets, log_callback=self.log)
                
                generated_count = 0
                for opp in new_opps:
                    # Price Filter
                    if opp['price'] > self.max_price:
                        # self.log(f"Skipping expensive opp: {opp['price']} > {self.max_price}")
                        continue

                    mid = opp["market_id"]
                    
                    # Duplicate Check
                    if any(p['market']['id'] == mid for p in self.proposed_trades):
                        continue
                        
                    # Prepare Proposal Object matches UI expectations
                    # The UI expects: id, market, signal (dict), outcome, price, edge, ev...
                    # We map our clean 'opp' to this messy structure for now
                    
                    # Mock signal object for compatibility
                    signal = {
                        "city": opp['city'],
                        "true_prob": 0.99, # implied by candidate status
                        "market_prob": opp['price'],
                        "edge": 0.99 - opp['price'],
                        "target_int": (opp['target_bucket'], opp['target_bucket']),
                        "om_val": opp['forecast_max'],
                        "question": opp['market']['question']
                    }
                    
                    proposal = {
                        "id": opp['id'],
                        "market": opp['market'],
                        "signal": signal,
                        "outcome": opp['outcome'],
                        "price": opp['price'],
                        "edge": 0.99 - opp['price'],
                        "ev": 0.0,
                        "delta_api": 0.0, # Not used in new logic
                        "is_snipe": True,
                        "timestamp": datetime.now().isoformat(),
                        
                        # New fields for UI display
                        "vale_api": opp['forecast_max'],
                        "int_pm": f"≥ {opp['target_bucket']}",
                        "settles_in_hours": "24h", # placeholder
                        "settles_in_days": 1
                    }
                    
                    self.proposed_trades.append(proposal)
                    generated_count += 1
                    
                    self.notifier.opportunity(
                        f"Op found! {opp['city']} {opp['date']} | T={opp['forecast_max']} -> Play {opp['outcome']}"
                    )

                self.log(f"Cycle complete. New Opportunities: {generated_count}")

        except Exception as e:
            self.log(f"ERR: Error in cycle: {e}")
            import traceback
            traceback.print_exc()
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
                self.notifier.trade(f"LIVE EXECUTION: {outcome} on {city} @ ${amount:.2f} | {msg}")
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
                self.notifier.trade(f"PAPER EXECUTION: {outcome} on {city} @ ${amount:.2f}")
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

    def get_opportunities_fast(self):
        """Returns filtered opportunities for fast polling."""
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
                        p['settles_in_hours'] = f"{int(hours_left)}" # Removed 'h' to avoid double 'hh'
                        p['settles_in_days'] = hours_left / 24
                except (ValueError, TypeError):
                    p['settles_in_hours'] = "?"
                    p['settles_in_days'] = 999
            else:
                p['settles_in_hours'] = "?"
                p['settles_in_days'] = 999

            # 3. Calculate New Metrics & Flags
            signal = p.get('signal', {})
            city = signal.get('city', '')
            p['city_flag'] = self._get_city_flag(city)
            
            om_val = signal.get('om_val')
            target_int = signal.get('target_int')
            
            p['vale_api'] = om_val
            
            # Format int(pm)
            if target_int:
                low, high = target_int
                if high >= 150: # TEMP_UPPER_BOUND
                    p['int_pm'] = f">{low}"
                elif low <= -50: # TEMP_LOWER_BOUND
                    p['int_pm'] = f"<{high}"
                else:
                    p['int_pm'] = f"{low}-{high}"
                
                # Calculate delta(api)
                if om_val is not None:
                    if low <= om_val <= high:
                        p['delta_api'] = 0.0
                    else:
                        p['delta_api'] = min(abs(om_val - low), abs(om_val - high))
                else:
                    p['delta_api'] = None
            else:
                 p['int_pm'] = "?"
                 p['delta_api'] = None

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
        return processed_trades

    def _get_city_flag(self, city):
        """Returns the ISO country code for a given city."""
        # Returns 2-letter ISO code for flagcdn usage
        flags = {
            "seattle": "us", "new york": "us", "chicago": "us", "miami": "us", 
            "los angeles": "us", "san francisco": "us", "austin": "us", "boston": "us", "las vegas": "us", "phoenix": "us", "denver": "us",
            "london": "gb", "tokyo": "jp", "toronto": "ca", "mumbai": "in", 
            "sao paulo": "br", "paris": "fr", "berlin": "de", "sydney": "au", 
            "dubai": "ae", "singapore": "sg", "seoul": "kr", "rome": "it", "madrid": "es"
        }
        return flags.get(city.lower(), "")

    def get_context(self):
        """Returns context for the dashboard with dynamic filtering."""
        status = self.portfolio.get_status()
        
        # Use fast method for trades to avoid duplication
        processed_trades = self.get_opportunities_fast()

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
