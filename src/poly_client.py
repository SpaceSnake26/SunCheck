import os
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, AssetType, BalanceAllowanceParams
from py_clob_client.constants import POLYGON
from dotenv import load_dotenv
from eth_account import Account

class PolyClient:
    def __init__(self):
        load_dotenv()
        self.host = "https://clob.polymarket.com"
        self.chain_id = POLYGON # 137
        self.client = None # Initialize client to None by default

        try:
            # 1. Load and clean all credentials
            self.key = os.getenv("POLY_API_KEY", "").strip().strip('"').strip("'")
            raw_secret = os.getenv("POLY_SECRET", "").strip().strip('"').strip("'")
            self.passphrase = os.getenv("POLY_PASSPHRASE", "").strip().strip('"').strip("'")
            self.address = os.getenv("POLY_ADDRESS", "").strip().strip('"').strip("'")
            self.private_key = os.getenv("POLY_PRIVATE_KEY", "").strip().strip('"').strip("'")

            # Standardize Secret (Polymarket often gives URL-safe Base64 with _ and -)
            # Standard Base64 uses / and +
            self.secret = raw_secret.replace('_', '/').replace('-', '+')

            if not self.key or not self.secret:
                print("Warning: Missing Poly API Credentials (POLY_API_KEY or POLY_SECRET) in .env.")
                return

            if not self.private_key:
                print("Warning: POLY_PRIVATE_KEY missing in .env. Client will be read-only.")
                creds = ApiCreds(api_key=self.key, api_secret=self.secret, api_passphrase=self.passphrase)
                self.client = ClobClient(self.host, chain_id=self.chain_id, creds=creds)
                return

            # 2. Setup Signing Address and Signature Type
            pk_hex = self.private_key if self.private_key.startswith("0x") else "0x" + self.private_key
            signer_account = Account.from_key(pk_hex)
            derived_addr = signer_account.address.lower()
            
            # Use provided POLY_ADDRESS if present, otherwise default to derived EOA address
            target_addr = self.address.lower() if self.address else derived_addr

            # Decide Sig Type: If target_addr != derived, it's a Proxy (1). Otherwise EOA (0).
            if target_addr != derived_addr:
                sig_type = 1 # POLY_PROXY
                funder = target_addr
                print(f"Auth: Using Proxy Settings (Funder: {target_addr}, Signer: {derived_addr})")
            else:
                sig_type = 0 # EOA
                funder = None
                print(f"Auth: Using EOA Settings (Address: {derived_addr})")

            creds = ApiCreds(
                api_key=self.key,
                api_secret=self.secret,
                api_passphrase=self.passphrase
            )

            self.client = ClobClient(
                self.host,
                chain_id=self.chain_id,
                creds=creds,
                key=self.private_key,
                signature_type=sig_type,
                funder=funder
            )
            print(f"Polymarket Client Authenticated (Key ID: {self.key[:6]}...)")

        except Exception as e:
            print(f"PolyClient Init Error: {e}")
            self.client = None

    def get_balance(self):
        """
        Gets USDC balance using a robust on-chain RPC check (Bypasses CLOB 401).
        The CLOB API often 401s for proxy accounts, but the money is at the Funder address.
        """
        if not self.address:
            return 0.0
        
        try:
            # 1. On-Chain Fallback (Reliable for Proxy/Funder accounts)
            addr = self.address.strip().lower()
            usdc_token = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174".lower()
            rpc_url = "https://polygon-rpc.com/"
            
            # eth_call for balance(address) -> selector 70a08231 + 32-byte address
            data = f"0x70a08231000000000000000000000000{addr[2:]}"
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": usdc_token, "data": data}, "latest"],
                "id": 1
            }
            
            import requests
            resp = requests.post(rpc_url, json=payload, timeout=10).json()
            if "result" in resp:
                bal = int(resp["result"], 16) / 1_000_000
                return bal
        except Exception as e:
            print(f"On-chain balance fetch failed: {e}")

        # 2. Try CLOB as secondary 
        if self.client:
            try:
                from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
                params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=1)
                resp = self.client.get_balance_allowance(params=params)
                return float(resp.get("balance", 0)) / 1_000_000
            except: pass
            
        return 0.0


    def execute_trade(self, market, outcome, price, amount_usd):
        """
        Executes a real trade using direct token IDs from the scanner.
        """
        if not self.client:
            return False, "Client not initialized"
        
        if not self.private_key:
            return False, "Missing Private Key - Cannot Sign Order"

        try:
            # 1. Extract Token IDs from market (provided by MarketScanner)
            token_ids = market.get('clobTokenIds', [])
            
            # Robust Parsing for scanner-provided strings
            if isinstance(token_ids, str):
                import json
                try: token_ids = json.loads(token_ids)
                except: pass

            # 2. Fallback to API check if missing or malformed
            if not token_ids or not isinstance(token_ids, list) or len(token_ids) < 2:
                print(f"Fetching fresh market data for ID: {market.get('id')}")
                market_data = self.client.get_market(market.get('id'))
                if market_data:
                    # CLOB API 'tokens' list is the ultimate source of truth
                    token_ids = [t.get('token_id') for t in market_data.get('tokens', [])]
            
            if not token_ids or len(token_ids) < 2:
                return False, f"Could not identify CLOB Token IDs for {market.get('id')}. IDs found: {token_ids}"

            # 3. Map Outcome to Token ID (Standard Binary: [NO, YES])
            target_token = token_ids[1] if outcome.upper() == "YES" else token_ids[0]
            
            print(f"Executing LIVE BET on {market.get('question')} | Outcome: {outcome} | Token: {target_token} | Price: {price} | Amt: ${amount_usd}")

            # 3. Build Order
            from py_clob_client.clob_types import OrderArgs
            size = round(amount_usd / price, 2)
            
            order_args = OrderArgs(
                price=price,
                size=size,
                side="BUY",
                token_id=target_token
            )

            # 4. Post Order (Using Signature Type 1 as per snap)
            print(f"Posting order for {size} shares at {price}")
            resp = self.client.create_and_post_order(order_args)
            
            if resp and resp.get('success'):
                return True, f"Order Success! ID: {resp.get('orderID')}"
            else:
                return False, f"Exchange Error: {resp}"

        except Exception as e:
            print(f"Trade Execution Exception: {e}")
            return False, str(e)

    def get_clob_price(self, token_id):
        # ... (cached/existing)
        pass

    def get_active_positions(self):
        """
        Fetches real open positions from the Polymarket Data API.
        Filters out dust/zero-value positions.
        """
        if not self.address:
            return []
        
        try:
            url = f"https://data-api.polymarket.com/positions?user={self.address.strip()}"
            import requests
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                raw_positions = r.json()
                processed = []
                for p in raw_positions:
                    size = float(p.get('size', 0))
                    cur_price = float(p.get('curPrice', 0))
                    
                    # 1. Filter out zero-value or tiny positions
                    if size <= 0 or cur_price <= 0.001: 
                        continue 
                    
                    # 2. Calculate Current Value
                    cur_value = size * cur_price
                    # Don't show positions worth less than $0.10 in the active list
                    if cur_value < 0.10:
                        continue

                    processed.append({
                        "market_id": p.get('conditionId'),
                        "question": p.get('title'),
                        "outcome": p.get('outcome'),
                        "price": float(p.get('avgPrice', 0)),
                        "shares": size,
                        "amount_invested": float(p.get('size', 0)) * float(p.get('avgPrice', 0)),
                        "cur_value": cur_value,
                        "is_live": True,
                        "pnl": float(p.get('cashPnl', 0)),
                        "cur_price": cur_price,
                        "timestamp": p.get('lastTradeTime') or datetime.now().isoformat()
                    })
                return processed
        except Exception as e:
            print(f"Data API Position Fetch Error: {e}")
        return []
