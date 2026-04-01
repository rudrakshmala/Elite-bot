import time
import math
import os
import datetime
import pickle
import numpy as np
import pandas as pd
import config
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- ⚙️ PRO SETTINGS ---
DAILY_PROFIT_GOAL = 500.0   
BASE_TARGET = 40.0          
TRAILING_STEP = 10.0        
HARD_STOP_LOSS = -30.0      
BRAIN_FILE = "crypto_brain.pkl"
JOURNAL_FILE = "crypto_journal.txt"

# 💎 THE ALPACA UNIVERSE
CRYPTO_PAIRS = [
    ("BTC/USD", "ETH/USD"),
    ("ETH/USD", "SOL/USD"),
    ("BTC/USD", "LTC/USD"),
    ("DOGE/USD", "SHIB/USD"), 
    ("ETH/USD", "AVAX/USD"),
    ("BCH/USD", "LTC/USD")
]

print("--- 🪙 CRYPTO ELITE: FINAL DATA FIX ---")

# Connect
trade_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
data_client = CryptoHistoricalDataClient(config.API_KEY, config.SECRET_KEY) 

# --- 🧠 STRATEGY ENGINE ---
def get_alpaca_data(symbol, hours=100):
    """Fetches real hourly bars from Alpaca directly."""
    # ✅ FIX: Calculate specific start time (5 days ago)
    # Alpaca REQUIRES a start time or it returns empty.
    start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
    
    req = CryptoBarsRequest(
        symbol_or_symbols=[symbol],
        timeframe=TimeFrame.Hour,
        limit=hours,
        start=start_time # <--- CRITICAL FIX
    )
    try:
        bars = data_client.get_crypto_bars(req)
        df = bars.df
        
        if df.empty:
            return pd.Series()

        # Extract symbol data
        df = df.xs(symbol) 
        return df['close']
    except Exception as e:
        print(f"   ⚠️ DEBUG: Data error for {symbol} -> {e}") 
        return pd.Series()

def calculate_z_score(sym_a, sym_b, window=20):
    try:
        data_a = get_alpaca_data(sym_a)
        data_b = get_alpaca_data(sym_b)
        
        if data_a.empty or data_b.empty:
            return None, "HOLD"

        # Align Dataframes
        df = pd.DataFrame({sym_a: data_a, sym_b: data_b}).dropna()
        
        if len(df) < window: return None, "HOLD"

        # Calculate Z-Score
        df['ratio'] = df[sym_a] / df[sym_b]
        mean = df['ratio'].rolling(window=window).mean()
        std = df['ratio'].rolling(window=window).std()
        df['z_score'] = (df['ratio'] - mean) / std
        
        last_z = df['z_score'].iloc[-1]
        
        signal = "HOLD"
        # Threshold 1.5 for easier testing
        if last_z < -1.5: signal = "BUY_PAIR"
        elif last_z > 1.5: signal = "SELL_PAIR"
        
        return last_z, signal
    except Exception as e:
        return None, "HOLD"

class CryptoBrain:
    def __init__(self):
        self.actions = ["SKIP", "TRADE"]
        self.lr, self.gamma, self.epsilon = 0.1, 0.9, 0.2
        self.q_table = pd.DataFrame(columns=self.actions, dtype=np.float64)
        self.load_memory()

    def get_state(self, z_score): return f"Z_{round(z_score, 1)}"
    
    def check_state_exist(self, state):
        if state not in self.q_table.index:
            new_row = pd.DataFrame([[0.0, 0.0]], columns=self.actions, index=[state])
            self.q_table = pd.concat([self.q_table, new_row])

    def choose_action(self, z_score):
        state = self.get_state(z_score)
        self.check_state_exist(state)
        if np.random.uniform() < self.epsilon: return np.random.choice(self.actions)
        return self.q_table.loc[state].idxmax()

    def learn(self, z_score, action, reward):
        state = self.get_state(z_score)
        self.check_state_exist(state)
        curr = self.q_table.loc[state, action]
        self.q_table.loc[state, action] += self.lr * (reward - curr)
        self.save_memory()

    def save_memory(self):
        with open(BRAIN_FILE, 'wb') as f: pickle.dump(self.q_table, f)

    def load_memory(self):
        if os.path.exists(BRAIN_FILE):
            with open(BRAIN_FILE, 'rb') as f: self.q_table = pickle.load(f)

class CryptoBot:
    def __init__(self):
        self.brain = CryptoBrain()
        self.daily_profit = self.load_daily_profit()
        print(f"   📅 Crypto Session Loaded. Profit: ${self.daily_profit:.2f}")

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
        try: return float(trade_client.get_account().buying_power)
        except: return 0.0

    def get_current_price(self, sym):
        try:
            # ✅ FIX: Added start time here too
            start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
            req = CryptoBarsRequest(symbol_or_symbols=[sym], timeframe=TimeFrame.Minute, limit=1, start=start_time)
            bars = data_client.get_crypto_bars(req)
            return bars.df['close'].iloc[-1]
        except: return 0.0

    def calculate_size(self, sym, budget, z_score):
        confidence = 0.15 if abs(z_score) > 2.5 else 0.05
        real_budget = budget * confidence
        price = self.get_current_price(sym)
        if price <= 0: return 0.0
        qty = real_budget / price
        return round(qty, 4)

    def close_all(self):
        try: trade_client.close_all_positions(cancel_orders=True)
        except: pass

    def trailing_stop_loop(self, z_score_entry):
        max_profit = 0.0
        stop_price = HARD_STOP_LOSS
        print(f"   🚀 RIDE STARTED (Stop: ${stop_price:.2f})")
        
        while True:
            try:
                positions = trade_client.get_all_positions()
                if not positions: 
                    print("\n   ⚠️ Positions closed. Trade ended.")
                    return 
                
                curr_pnl = sum([float(p.unrealized_pl) for p in positions])
                
                if curr_pnl > max_profit:
                    max_profit = curr_pnl
                    if max_profit >= BASE_TARGET:
                        new_stop = max_profit - TRAILING_STEP
                        if new_stop > stop_price:
                            stop_price = new_stop
                            print(f"\n      🔥 PUMP! Profit ${max_profit:.2f} -> Locking ${stop_price:.2f}")

                print(f"\r      💎 PnL: ${curr_pnl:.2f} (High: ${max_profit:.2f} | Stop: ${stop_price:.2f})  ", end="")

                if curr_pnl <= stop_price:
                    self.close_all()
                    self.daily_profit += curr_pnl
                    self.save_daily_profit()
                    reward = 10.0 if curr_pnl > 0 else -10.0
                    self.brain.learn(z_score_entry, "TRADE", reward)
                    print(f"\n   💰 PROFIT SECURED: ${curr_pnl:.2f}" if curr_pnl > 0 else f"\n   📉 STOP LOSS HIT: ${curr_pnl:.2f}")
                    return

                time.sleep(2)
            except: time.sleep(5)

    def run(self):
        print("   ⏳ Connecting to Alpaca Data Stream...")
        time.sleep(2)

        while True:
            if self.daily_profit >= DAILY_PROFIT_GOAL:
                print(f"\n🏆 MOON MISSION COMPLETE (${self.daily_profit:.2f}).")
                break

            print(f"\n[{time.strftime('%H:%M:%S')}] 📡 SCANNING (via Alpaca Data API)...")
            best_opp = None
            best_z = 0
            
            for sym_a, sym_b in CRYPTO_PAIRS:
                z, signal = calculate_z_score(sym_a, sym_b)
                
                if z is None: 
                    print(f"   ⚠️ Skipping {sym_a}/{sym_b} (Empty Data)")
                    continue
                
                print(f"   Checked {sym_a}/{sym_b}: Z={z:.2f}")

                if abs(z) > 1.5 and abs(z) > abs(best_z):
                    best_z, best_opp = z, (sym_a, sym_b, signal)
            
            if best_opp:
                sym_a, sym_b, signal = best_opp
                print(f"   🪙 OPPORTUNITY: {sym_a}/{sym_b} (Z={best_z:.2f})")
                
                if self.brain.choose_action(best_z) == "SKIP":
                    print("   🛑 Brain says: 'Skip this one.'")
                    time.sleep(2)
                    continue 

                cash = self.get_buying_power()
                qty_a = self.calculate_size(sym_a, cash, best_z)
                qty_b = self.calculate_size(sym_b, cash, best_z)
                
                if qty_a > 0 and qty_b > 0:
                    print(f"   ⚡ EXECUTING: {signal} ({qty_a} / {qty_b} units)")
                    try:
                        side_a = OrderSide.BUY if signal == "BUY_PAIR" else OrderSide.SELL
                        side_b = OrderSide.SELL if signal == "BUY_PAIR" else OrderSide.BUY
                        
                        trade_client.submit_order(MarketOrderRequest(symbol=sym_a, qty=qty_a, side=side_a, time_in_force=TimeInForce.GTC))
                        trade_client.submit_order(MarketOrderRequest(symbol=sym_b, qty=qty_b, side=side_b, time_in_force=TimeInForce.GTC))
                        
                        time.sleep(2)
                        self.trailing_stop_loop(best_z)
                        print("   ...Cooldown 60s...")
                        time.sleep(60)
                    except Exception as e: 
                        print(f"   ❌ Order Failed: {e}")
                else:
                    print("   ⚠️ Insufficient Funds.")
            else:
                print("   💤 No setups. Retrying in 10s...")
                time.sleep(10)

if __name__ == "__main__":
    try: CryptoBot().run()
    except KeyboardInterrupt: print("\n👋 Exiting.")