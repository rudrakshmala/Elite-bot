import time
import math
import config
import universe
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import strategy_engine as strategy

# --- 🎯 SNIPER SETTINGS ---
DAILY_GOAL = 100.0       # Stop trading after making $100
PROFIT_PER_TRADE = 20.0  # Close trade when profit hits $20
MAX_TRADES_PER_DAY = 10  # Safety limit
RISK_PER_TRADE = 0.10    # Use 10% of buying power (Need bigger size to hit $20 fast)

print("--- 🎯 ELITE SNIPER BOT: $100/DAY MODE ---")

client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

# Global Tracker for the Day
session_stats = {
    "banked_profit": 0.0,
    "wins": 0
}

# --- HELPER FUNCTIONS ---

def get_account_buying_power():
    try:
        account = client.get_account()
        return float(account.buying_power)
    except:
        return 0.0

def get_current_price_backup(sym):
    try:
        # 1. Try Alpaca
        trade = client.get_latest_trade(sym)
        return float(trade.price)
    except:
        # 2. Try Yahoo
        try:
            ticker = yf.Ticker(sym)
            return ticker.fast_info.get('last_price', 0.0)
        except:
            return 0.0

def close_all_positions():
    """Immediately closes EVERYTHING to bank the profit"""
    try:
        client.close_all_positions(cancel_orders=True)
        print("      ✂️ POSITIONS CLOSED! Profit Secured.")
    except Exception as e:
        print(f"      ❌ Error closing positions: {e}")

def get_live_pnl():
    """Check how much money we are making RIGHT NOW"""
    try:
        positions = client.get_all_positions()
        if not positions:
            return 0.0, False # No positions
        
        total_pnl = 0.0
        for p in positions:
            total_pnl += float(p.unrealized_pl)
            
        return total_pnl, True # True means we are active in a trade
    except Exception as e:
        print(f"Error checking PnL: {e}")
        return 0.0, False

def place_sniper_trade(sym, side, qty):
    try:
        # Market Order - We want in NOW
        req = MarketOrderRequest(
            symbol=sym,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC
        )
        client.submit_order(req)
        return True
    except Exception as e:
        print(f"      ❌ Order Failed for {sym}: {e}")
        return False

# --- MAIN LOGIC ---

def run_sniper_cycle():
    # 1. CHECK IF WE HIT DAILY GOAL
    if session_stats["banked_profit"] >= DAILY_GOAL:
        print(f"\n🎉 DAILY TARGET HIT! Total Profit: ${session_stats['banked_profit']:.2f}")
        print("   Mission Accomplished. Shutting down for the day.")
        exit()

    # 2. CHECK LIVE PNL (Are we in a trade?)
    current_pnl, is_in_trade = get_live_pnl()
    
    if is_in_trade:
        print(f"\r   👀 WATCHING TRADE... Current PnL: ${current_pnl:.2f} / Target: ${PROFIT_PER_TRADE:.2f}", end="")
        
        # --- THE SNIPE LOGIC ---
        if current_pnl >= PROFIT_PER_TRADE:
            print(f"\n\n   🎯 TARGET ACQUIRED! PnL reached ${current_pnl:.2f}")
            close_all_positions()
            
            # Update Stats
            session_stats["banked_profit"] += current_pnl
            session_stats["wins"] += 1
            
            print(f"   💰 BANKED! Daily Total: ${session_stats['banked_profit']:.2f} / ${DAILY_GOAL:.2f}")
            print("   ...Taking a breather for 30 seconds before next hunt...")
            time.sleep(30)
            
        # SAFETY: Stop Loss (Optional, e.g., if we lose -$30, cut it)
        elif current_pnl <= -30.0:
            print(f"\n   🛡️ STOP LOSS HIT at ${current_pnl:.2f}. Aborting trade.")
            close_all_positions()
            time.sleep(10)
            
        else:
            time.sleep(2) # Just wait and watch
            return # Skip the scanning part, just loop back to watch

    else:
        # 3. NO TRADES OPEN? FIND ONE.
        print(f"\n[{time.strftime('%H:%M:%S')}] 🔭 SCANNING FOR OPPORTUNITY (Goal: ${DAILY_GOAL - session_stats['banked_profit']:.2f} more)...")
        
        buying_power = get_account_buying_power()
        trade_budget = buying_power * RISK_PER_TRADE
        
        best_opp = None
        best_score = 0
        
        for sym_a, sym_b in universe.PAIRS_UNIVERSE:
            try:
                df = strategy.calculate_pairs_strategy(sym_a, sym_b)
                if df is None: continue
                z = df.iloc[-1]['Z_Score']
                signal = df.iloc[-1]['Signal']
                
                # We only want High Confidence trades (Z > 1.8 or Z < -1.8)
                if abs(z) > 1.8 and (signal == "BUY_PAIR" or signal == "SELL_PAIR"):
                    if abs(z) > abs(best_score):
                        best_score = z
                        best_opp = (sym_a, sym_b, signal, z)
            except:
                continue
                
        if best_opp:
            sym_a, sym_b, signal, z = best_opp
            print(f"   🚀 EXECUTING: {sym_a} vs {sym_b} (Score: {z:.2f})")
            
            # Calculate Quantity
            price_a = get_current_price_backup(sym_a)
            price_b = get_current_price_backup(sym_b)
            
            if price_a > 0 and price_b > 0:
                qty_a = math.floor(trade_budget / price_a)
                qty_b = math.floor(trade_budget / price_b)
                
                if qty_a > 0 and qty_b > 0:
                    if signal == "BUY_PAIR":
                        place_sniper_trade(sym_a, OrderSide.BUY, qty_a)
                        place_sniper_trade(sym_b, OrderSide.SELL, qty_b)
                    else:
                        place_sniper_trade(sym_a, OrderSide.SELL, qty_a)
                        place_sniper_trade(sym_b, OrderSide.BUY, qty_b)
            else:
                print("      ⚠️ Price data error, skipping.")
        else:
            print("      💤 No high-quality setups found. Waiting...")
            time.sleep(10)

if __name__ == "__main__":
    try:
        # First, ensure we start flat (optional)
        # client.close_all_positions(cancel_orders=True) 
        while True:
            run_sniper_cycle()
    except KeyboardInterrupt:
        print("\n\n👋 Sniper Deactivated.")