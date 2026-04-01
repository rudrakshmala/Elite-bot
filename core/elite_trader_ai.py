import time
import math
import os
import datetime
import json
import re
import yfinance as yf
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import config

# 🚨 IMPORT YOUR NEW AI TEAM
from crew_trader import evaluate_opportunity

# --- ⚙️ SETTINGS (Elite Trader rules from config) ---
DAILY_PROFIT_GOAL = config.DAILY_PROFIT_TARGET
DAILY_STOP_LOSS = config.DAILY_STOP_LOSS
BASE_TARGET = 150.0         
TRAILING_STEP = 50.0        
JOURNAL_FILE = "trade_journal.txt"

PAIRS_UNIVERSE = [
    ("KO", "PEP"), ("XOM", "CVX"), ("JPM", "BAC"), 
    ("F", "GM"), ("MSFT", "AAPL"), ("V", "MA"), 
    ("LMT", "RTX"), ("GOOGL", "META")
]

print("--- 🧠 ELITE TRADER: MULTIMODAL CREW AI EDITION ---")

client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

# --- 🧮 MATH ENGINE ---
def calculate_z_score(sym_a, sym_b, window=20):
    try:
        data_a = yf.download(sym_a, period="5d", interval="1h", progress=False)['Close'].squeeze()
        data_b = yf.download(sym_b, period="5d", interval="1h", progress=False)['Close'].squeeze()
        
        df = pd.DataFrame({sym_a: data_a, sym_b: data_b}).dropna()
        if len(df) < window: return None, "HOLD"

        df['ratio'] = df[sym_a] / df[sym_b]
        mean = df['ratio'].rolling(window=window).mean()
        std = df['ratio'].rolling(window=window).std()
        df['z_score'] = (df['ratio'] - mean) / std
        
        last_z = df['z_score'].iloc[-1]
        
        signal = "HOLD"
        if last_z < -1.5: signal = "BUY_PAIR"
        elif last_z > 1.5: signal = "SELL_PAIR"
        
        return last_z, signal
    except: return None, "HOLD"

# --- 🧠 AI JSON PARSER ---
def parse_ai_decision(crew_output):
    """Safely extracts the JSON from the CrewAI output. Returns (data_dict, should_trade, signal)."""
    try:
        clean_text = re.sub(r"```json\s*", "", str(crew_output))
        clean_text = re.sub(r"```\s*", "", clean_text)
        data = json.loads(clean_text)
        final_action = data.get("final_action", "WAIT").upper()
        should_trade = final_action in ("BUY", "SELL")
        signal = "BUY_PAIR" if final_action == "BUY" else "SELL_PAIR" if final_action == "SELL" else None
        return data, should_trade, signal
    except Exception as e:
        print(f"      ⚠️ Failed to parse AI JSON: {e}")
        return {"final_action": "WAIT"}, False, None

class EliteBot:
    def __init__(self):
        self.live_pnl = 0.0
        self.daily_profit = self.load_daily_profit()
        self.cooldowns = {} # 👈 API LIMIT PROTECTION: THE PENALTY BOX
        print(f"   📅 Session Loaded. Profit so far: ${self.daily_profit:.2f}")

    def load_daily_profit(self):
        if not os.path.exists(JOURNAL_FILE): return 0.0
        try:
            with open(JOURNAL_FILE, "r") as f:
                line = f.read().strip()
                date, profit = line.split("|")
                if date == str(datetime.date.today()): return float(profit)
        except: pass
        return 0.0

    def save_daily_profit(self):
        with open(JOURNAL_FILE, "w") as f:
            f.write(f"{datetime.date.today()}|{self.daily_profit}")

    def get_buying_power(self):
        try: return float(client.get_account().buying_power)
        except: return 0.0

    def get_price(self, sym):
        try:
            # Bulletproof way to get the latest real-time price
            df = yf.download(sym, period="1d", interval="1m", progress=False)
            if not df.empty:
                return float(df['Close'].iloc[-1].squeeze())
        except Exception as e:
            print(f"      ⚠️ Price fetch failed for {sym}: {e}")
        return 0.0

    def calculate_qty(self, sym, budget):
        price = self.get_price(sym)
        if price <= 0: return 0
        return math.floor((budget * 0.95) / price)

    def close_all(self):
        try: client.close_all_positions(cancel_orders=True)
        except: pass

    def is_active_trade(self, sym_a, sym_b):
        try:
            positions = client.get_all_positions()
            for p in positions:
                if p.symbol in [sym_a, sym_b]: return True
        except: pass
        return False

    def trailing_stop_loop(self):
        max_profit = 0.0
        stop_price = DAILY_STOP_LOSS
        print(f"   🚀 RUNNING TRADE (Stop: ${stop_price:.2f})")
        
        while True:
            try:
                positions = client.get_all_positions()
                if not positions: return
                
                curr_pnl = sum([float(p.unrealized_pl) for p in positions])
                self.live_pnl = curr_pnl
                
                if curr_pnl > max_profit:
                    max_profit = curr_pnl
                    if max_profit >= BASE_TARGET:
                        new_stop = max_profit - TRAILING_STEP
                        if new_stop > stop_price:
                            stop_price = new_stop
                            print(f"\n      🔥 Trailing Stop Raised: ${stop_price:.2f}")

                print(f"\r      💎 PnL: ${curr_pnl:.2f} (Stop: ${stop_price:.2f})   ", end="")

                if curr_pnl <= stop_price:
                    self.close_all()
                    self.daily_profit += curr_pnl
                    self.save_daily_profit()
                    print(f"\n   💰 CLOSED POSITION: ${curr_pnl:.2f}")
                    self.live_pnl = 0.0
                    return
                time.sleep(2)
            except: time.sleep(5)

    def run(self):
        print("   ⏳ Warming up market scanners...")
        time.sleep(3)

        while True:
            if self.daily_profit >= DAILY_PROFIT_GOAL:
                print(f"\n🏆 DAILY GOAL HIT (${self.daily_profit:.2f}). Shutting down.")
                break
            if self.daily_profit <= DAILY_STOP_LOSS:
                print(f"\n🛑 DAILY STOP HIT (${self.daily_profit:.2f}). Shutting down.")
                break

            print(f"\n[{time.strftime('%H:%M:%S')}] 🔭 SCANNING MARKET...")
            best_opp = None
            best_z = 0
            
            for sym_a, sym_b in PAIRS_UNIVERSE:
                pair_key = f"{sym_a}/{sym_b}"
                
                # Check if this pair is currently in the penalty box (1 hour cooldown = 3600 seconds)
                if pair_key in self.cooldowns:
                    if time.time() - self.cooldowns[pair_key] < 3600:
                        continue 

                z, signal = calculate_z_score(sym_a, sym_b)
                if z is None: continue
                
                if abs(z) > 1.5 and abs(z) > abs(best_z):
                    best_z, best_opp = z, (sym_a, sym_b, signal)
            
            if best_opp:
                sym_a, sym_b, signal = best_opp
                pair_key = f"{sym_a}/{sym_b}"

                if self.is_active_trade(sym_a, sym_b):
                    print(f"   ⚠️ Skipping {sym_a}/{sym_b} - Already in position.")
                    time.sleep(10)
                    continue

                print(f"\n   🚨 MATH SIGNAL TRIGGERED: {sym_a}/{sym_b} (Z={best_z:.2f})")
                print("   📞 Calling the CrewAI team for validation...")
                
                try:
                    # --- 🤖 THE MAGIC HAPPENS HERE ---
                    crew_output = evaluate_opportunity(sym_a, sym_b, best_z)
                    data, should_trade, signal = parse_ai_decision(crew_output)
                    
                    # Print the full Trader Agent JSON output to terminal
                    print(f"\n   📋 TRADER AGENT OUTPUT:")
                    print(json.dumps(data, indent=2))
                    
                    if not should_trade:
                        print(f"   🛑 Trade Rejected (final_action: {data.get('final_action', 'WAIT')}). Putting {pair_key} on cooldown for 1 hour.")
                        self.cooldowns[pair_key] = time.time() # 👈 Put it in timeout
                        time.sleep(15) # Brief pause before next scan
                        continue 

                    # --- ⚡ EXECUTION ---
                    cash = self.get_buying_power()
                    if cash < 100: 
                        print(f"   ⚠️ Skipped: Not enough buying power (${cash}).")
                        continue

                    budget = cash * 0.10
                    qty_a = self.calculate_qty(sym_a, budget)
                    qty_b = self.calculate_qty(sym_b, budget)
                    
                    if qty_a > 0 and qty_b > 0 and signal:
                        print(f"   ⚡ EXECUTING: {signal} ({qty_a} {sym_a} / {qty_b} {sym_b})")
                        side_a = OrderSide.BUY if signal == "BUY_PAIR" else OrderSide.SELL
                        side_b = OrderSide.SELL if signal == "BUY_PAIR" else OrderSide.BUY
                        
                        client.submit_order(MarketOrderRequest(symbol=sym_a, qty=qty_a, side=side_a, time_in_force=TimeInForce.GTC))
                        client.submit_order(MarketOrderRequest(symbol=sym_b, qty=qty_b, side=side_b, time_in_force=TimeInForce.GTC))
                        
                        time.sleep(5)
                        self.trailing_stop_loop()
                    else:
                        # This will catch the silent failures!
                        print(f"   ⚠️ Skipped Execution: Calculated quantity is 0!")
                        print(f"      Budget: ${budget:.2f} | {sym_a} Price: ${self.get_price(sym_a)} | {sym_b} Price: ${self.get_price(sym_b)}")
                except Exception as e: 
                    print(f"   ❌ CrewAI or Execution Failed: {e}")
                    print("   ⏳ Sleeping for 60 seconds to reset API limits...")
                    time.sleep(60)
            else:
                print("   💤 No actionable setups found. Retrying in 60s...")
                time.sleep(60)

if __name__ == "__main__":
    try: EliteBot().run()
    except KeyboardInterrupt: print("\n👋 Exiting Bot.")