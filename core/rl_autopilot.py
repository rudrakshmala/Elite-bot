import time
import re
import json
import config
import universe
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetPortfolioHistoryRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from rl_brain import QLearningAgent
import strategy_engine
from crew_trader import evaluate_opportunity

print("--- 🧠 AI TRADER: TAURIC MULTI-AGENT RL MODE ---")

# Kill-switch: massive penalty when PnL hits -$100
DAILY_STOP_LOSS = config.RISK_CONFIG["HARD_STOP_LOSS"]
KILL_SWITCH_PENALTY = -500
FEE_PER_SIDE = config.FEE_PER_SIDE
TRADE_QTY = 5

# 1. Initialize & Load Brain
client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
agent = QLearningAgent()
agent.load_brain("smart_brain.pkl")

# Track last transition for deferred learning
_last_state = None  # (z_score, sentiment_score, action, pnl_at_action)
_total_fees_paid = 0.0  # Running total for Net Profit display

# Mapping Bot Actions to Real Orders
# 0 = HOLD
# 1 = BUY PAIR (Buy A, Sell B)
# 2 = SELL PAIR (Sell A, Buy B)

def estimate_round_trip_fees(sym_a, sym_b, qty=TRADE_QTY):
    """Total fees for Entry + Exit on both tickers (4 sides)."""
    try:
        ticker_a = yf.Ticker(sym_a)
        ticker_b = yf.Ticker(sym_b)
        price_a = float(ticker_a.fast_info.get("last_price", 0) or ticker_a.history(period="1d")["Close"].iloc[-1])
        price_b = float(ticker_b.fast_info.get("last_price", 0) or ticker_b.history(period="1d")["Close"].iloc[-1])
        if price_a <= 0 or price_b <= 0:
            return 0.0
        return 2 * FEE_PER_SIDE * qty * (price_a + price_b)  # 4 sides = 2*entry + 2*exit
    except Exception:
        return 0.0

def get_cumulative_pnl():
    """Today's cumulative PnL. Uses portfolio history; fallback to positions."""
    try:
        history = client.get_portfolio_history(
            GetPortfolioHistoryRequest(period="1D", timeframe="5Min")
        )
        if history.profit_loss and len(history.profit_loss) > 0:
            return float(history.profit_loss[-1])
    except Exception:
        pass
    try:
        positions = client.get_all_positions()
        return sum(float(p.unrealized_pl or 0) for p in positions)
    except Exception:
        pass
    return 0.0

def get_sentiment_from_crew(sym_a, sym_b, z_score):
    """Call crew_trader agents and extract sentiment_score (0-1) from CIO output."""
    try:
        crew_output = evaluate_opportunity(sym_a, sym_b, z_score)
        clean_text = re.sub(r"```json\s*", "", str(crew_output))
        clean_text = re.sub(r"```\s*", "", clean_text)
        data = json.loads(clean_text)
        # Derive 0-1 sentiment: combine signal_strength and confidence
        sig = float(data.get("signal_strength", 0.5))
        conf = float(data.get("confidence", 50)) / 100.0
        return (sig + conf) / 2.0
    except Exception as e:
        print(f"   ⚠️ Crew sentiment failed: {e}, using Neutral (0.5)")
        return 0.5

def get_live_z_score(sym_a, sym_b):
    # Use your existing strategy engine to get just the Z-Score
    try:
        df = strategy_engine.calculate_pairs_strategy(sym_a, sym_b)
        return df.iloc[-1]['Z_Score']
    except:
        return 0

def execute_ai_trade(sym_a, sym_b, action):
    qty = TRADE_QTY

    if action == 1:  # AI says: BUY THE PAIR
        print(f"   🤖 AI SIGNAL: BUY PAIR ({sym_a} Long / {sym_b} Short)")
        try:
            client.submit_order(MarketOrderRequest(symbol=sym_a, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC))
            client.submit_order(MarketOrderRequest(symbol=sym_b, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC))
        except Exception as e:
            print(f"   ❌ Execution Error: {e}")

    elif action == 2: # AI says: SELL THE PAIR
        print(f"   🤖 AI SIGNAL: SELL PAIR ({sym_a} Short / {sym_b} Long)")
        try:
            client.submit_order(MarketOrderRequest(symbol=sym_a, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC))
            client.submit_order(MarketOrderRequest(symbol=sym_b, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC))
        except Exception as e:
            print(f"   ❌ Execution Error: {e}")
            
    else:
        print("   🤖 AI SIGNAL: HOLD (Waiting for better setup)")

def run_ai_cycle():
    global _last_state, _total_fees_paid

    pair = ("MSFT", "AAPL")
    print(f"\n[{time.strftime('%H:%M:%S')}] 🧠 AI Thinking...")

    pnl = get_cumulative_pnl()
    print(f"   Cumulative PnL: ${pnl:.2f} | Net Profit (after fees): ${pnl - _total_fees_paid:.2f}")

    z_score = get_live_z_score(pair[0], pair[1])
    print(f"   Market State: Z-Score is {z_score:.2f}")

    # Get sentiment from crew_trader multi-agent output
    sentiment_score = get_sentiment_from_crew(pair[0], pair[1], z_score)
    print(f"   Sentiment: {sentiment_score:.2f}")

    # Deferred learn: apply reward from previous action (fee-aware)
    pnl = get_cumulative_pnl()
    if _last_state is not None:
        prev_z, prev_sentiment, prev_action, pnl_at_action = _last_state
        gross_reward = pnl - pnl_at_action
        if pnl <= DAILY_STOP_LOSS:
            reward = KILL_SWITCH_PENALTY  # -500: brain learns to fear the stop-loss
            print(f"   🛑 KILL-SWITCH HIT! PnL ${pnl:.2f} <= ${DAILY_STOP_LOSS:.2f} | Penalty: {reward}")
        else:
            fees = estimate_round_trip_fees(pair[0], pair[1]) if prev_action in (1, 2) else 0.0
            _total_fees_paid += fees
            reward = gross_reward - fees
            print(f"   📊 Gross PnL: ${gross_reward:.2f} | Fees: ${fees:.2f} | Net Profit: ${reward:.2f}")
        agent.learn(prev_z, prev_sentiment, prev_action, reward, z_score, sentiment_score)

    # Choose action with Z + sentiment state
    action = agent.choose_action(z_score, sentiment_score)

    execute_ai_trade(pair[0], pair[1], action)

    # Store for next cycle's learn step
    _last_state = (z_score, sentiment_score, action, pnl)

if __name__ == "__main__":
    while True:
        run_ai_cycle()
        print("   ...AI sleeping for 60 seconds...")
        time.sleep(60)