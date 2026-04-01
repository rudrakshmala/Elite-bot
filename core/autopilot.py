import time
import math
import config
import universe
import yfinance as yf  # <--- We now import this for backup price data
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetPortfolioHistoryRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import strategy_engine as strategy

# --- 🧠 BRAIN SETTINGS ---
RISK_PER_TRADE = 0.05  # Use 5% of cash per trade
STOP_LOSS_PCT = 0.02   
TAKE_PROFIT_PCT = 0.04 

# --- Daily limits (from config) - checked immediately, not on next cycle ---
DAILY_STOP_LOSS = config.RISK_CONFIG["HARD_STOP_LOSS"]   # -100
DAILY_PROFIT_TARGET = config.RISK_CONFIG["DAILY_PROFIT_TARGET"]  # 1000

print("--- 🤖 ELITE AUTOPILOT: BULLETPROOF EDITION ---")
client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

# --- HELPER FUNCTIONS ---

def get_cumulative_pnl():
    """Get today's cumulative PnL. Uses portfolio history; fallback to positions' unrealized PnL."""
    try:
        history = client.get_portfolio_history(
            GetPortfolioHistoryRequest(period="1D", timeframe="5Min")
        )
        if history.profit_loss and len(history.profit_loss) > 0:
            return float(history.profit_loss[-1])
    except Exception:
        pass
    # Fallback: sum unrealized PnL from open positions
    try:
        positions = client.get_all_positions()
        return sum(float(p.unrealized_pl or 0) for p in positions)
    except Exception:
        pass
    return 0.0

def close_all_positions():
    """Immediately liquidate all open positions."""
    try:
        client.close_all_positions(cancel_orders=True)
        print("   🔴 ALL POSITIONS CLOSED.")
    except Exception as e:
        print(f"   ⚠️ Error closing positions: {e}")

def check_daily_limits():
    """Returns (should_stop, reason). If limits hit, closes all and returns True."""
    pnl = get_cumulative_pnl()
    if pnl <= DAILY_STOP_LOSS:
        print(f"\n   🛑 DAILY STOP HIT: PnL ${pnl:.2f} <= ${DAILY_STOP_LOSS:.2f}")
        close_all_positions()
        return True, "daily_stop_loss"
    if pnl >= DAILY_PROFIT_TARGET:
        print(f"\n   🏆 DAILY TARGET HIT: PnL ${pnl:.2f} >= ${DAILY_PROFIT_TARGET:.2f}")
        close_all_positions()
        return True, "daily_profit_target"
    return False, None

def get_account_buying_power():
    try:
        account = client.get_account()
        return float(account.buying_power)
    except:
        return 0.0

def get_current_price(sym):
    """
    Get live price. 
    Priority 1: Alpaca (Official Broker)
    Priority 2: Yahoo Finance (Backup)
    """
    # 1. Try Alpaca
    try:
        trade = client.get_latest_trade(sym)
        price = float(trade.price)
        if price > 0:
            return price
    except:
        pass # Alpaca failed, move to backup

    # 2. Try Yahoo Finance (Backup)
    try:
        # print(f"      (Using Yahoo Backup for {sym} price...)")
        ticker = yf.Ticker(sym)
        # We try to get the 'fast' price first, then the latest minute data
        price = ticker.fast_info.get('last_price', 0.0)
        if price == 0:
             # Fallback to history if fast_info fails
             hist = ticker.history(period="1d")
             price = hist['Close'].iloc[-1]
        return float(price)
    except Exception as e:
        print(f"      ❌ Price Fetch Error: {e}")
        return 0.0

def calculate_safe_quantity(symbol, allocatable_cash):
    price = get_current_price(symbol)
    
    # If price is 0 (broken data), we return 0 so the bot knows to skip it.
    if price is None or price == 0: 
        return 0, 0
    
    qty = math.floor(allocatable_cash / price)
    if qty < 1: qty = 1
    
    return qty, price

def place_smart_trade(sym, side, qty, price):
    try:
        # Calculate Safety Levels
        if side == OrderSide.BUY:
            sl = round(price * (1 - STOP_LOSS_PCT), 2)
            tp = round(price * (1 + TAKE_PROFIT_PCT), 2)
        else:
            sl = round(price * (1 + STOP_LOSS_PCT), 2)
            tp = round(price * (1 - TAKE_PROFIT_PCT), 2)

        req = MarketOrderRequest(
            symbol=sym,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC,
            stop_loss=StopLossRequest(stop_price=sl),
            take_profit=TakeProfitRequest(limit_price=tp)
        )
        client.submit_order(req)
        print(f"      ✅ EXECUTED: {side} {qty} {sym} @ ~${price} (SL: {sl} | TP: {tp})")
        return True
    except Exception as e:
        print(f"      ❌ Execution Error for {sym}: {e}")
        return False

def scan_and_trade():
    print(f"\n[{time.strftime('%H:%M:%S')}] 🛰️ SCANNING MARKET UNIVERSE...")
    
    buying_power = get_account_buying_power()
    trade_budget = buying_power * RISK_PER_TRADE
    print(f"   💰 Buying Power: ${buying_power:,.2f} | 🛡️ Budget: ${trade_budget:,.2f}")

    opportunities = []

    # 1. SCAN PHASE
    for sym_a, sym_b in universe.PAIRS_UNIVERSE:
        try:
            df = strategy.calculate_pairs_strategy(sym_a, sym_b)
            if df is None: continue
            
            last_row = df.iloc[-1]
            z_score = last_row['Z_Score']
            signal = last_row['Signal']
            
            print(f"      👉 {sym_a}/{sym_b}: Z={z_score:.2f} ({signal})")
            
            if signal == "BUY_PAIR" or signal == "SELL_PAIR":
                opportunities.append({
                    'pair': (sym_a, sym_b),
                    'signal': signal,
                    'z_score': z_score,
                    'strength': abs(z_score)
                })
                
        except Exception as e:
            print(f"      Error scanning {sym_a}/{sym_b}: {e}")

    # 2. SORT PHASE
    opportunities.sort(key=lambda x: x['strength'], reverse=True)

    # 3. EXECUTION PHASE
    if not opportunities:
        print("   💤 No opportunities found. Waiting...")
        return False

    print(f"\n   📋 Found {len(opportunities)} potential trades. Attempting execution...")

    for opp in opportunities:
        # Check limits immediately before any execution (do not wait for next cycle)
        stop, _ = check_daily_limits()
        if stop:
            return True  # Signal main loop to exit

        sym_a, sym_b = opp['pair']
        signal = opp['signal']
        z = opp['z_score']
        
        print(f"   ➤ Attempting Best Trade: {sym_a} vs {sym_b} (Score: {z:.2f})")
        
        # Calculate Quantities
        qty_a, price_a = calculate_safe_quantity(sym_a, trade_budget)
        qty_b, price_b = calculate_safe_quantity(sym_b, trade_budget)

        if price_a == 0 or price_b == 0:
            print(f"      ⚠️ Data Error: Could not fetch price (even with Backup).")
            print("      ↪️ SKIP! Trying next best opportunity...")
            continue 

        # EXECUTE
        success_a = False
        success_b = False

        if signal == "BUY_PAIR":
            success_a = place_smart_trade(sym_a, OrderSide.BUY, qty_a, price_a)
            success_b = place_smart_trade(sym_b, OrderSide.SELL, qty_b, price_b)
        elif signal == "SELL_PAIR":
            success_a = place_smart_trade(sym_a, OrderSide.SELL, qty_a, price_a)
            success_b = place_smart_trade(sym_b, OrderSide.BUY, qty_b, price_b)
        
        if success_a and success_b:
            print("   🚀 SUCCESS: Trade Strategy Executed.")
            break
        else:
            print("   ⚠️ Order execution incomplete.")
            break
    return False

# --- MAIN LOOP ---
if __name__ == "__main__":
    while True:
        # Check limits immediately at start of each cycle (do not wait)
        stop, reason = check_daily_limits()
        if stop:
            print(f"\n   👋 Script stopping for the day. Reason: {reason}")
            break

        if scan_and_trade():
            print(f"\n   👋 Script stopping for the day. Daily limits hit during scan.")
            break

        # Cooldown: check PnL every 10s so we don't wait for next cycle
        print("   ...cooling down scanner for 2 minutes (PnL checked every 10s)...")
        for _ in range(12):  # 12 x 10s = 120s
            time.sleep(10)
            stop, reason = check_daily_limits()
            if stop:
                print(f"\n   👋 Script stopping for the day. Reason: {reason}")
                break
        if stop:
            break