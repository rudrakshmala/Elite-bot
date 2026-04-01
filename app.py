from contextlib import asynccontextmanager
from fastapi import FastAPI
import threading
import uvicorn
import sys

try:
    from crypto_trader_ai import CryptoBot as CryptoEngine
except ImportError:
    print("❌ Error: Could not find 'CryptoBot' class in crypto_trader_ai.py")
    sys.exit(1)

try:
    from elite_trader_ai import EliteBot as ForexEngine 
except ImportError:
    print("❌ Error: Could not find 'EliteBot' class in elite_trader_ai.py")
    sys.exit(1)

crypto_bot = CryptoEngine()
forex_bot = ForexEngine()

# State Tracker to know if they are sleeping or running
engine_status = {
    "crypto": "💤 Sleeping",
    "forex": "💤 Sleeping"
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🦅 ELITE-BOT: Backend Online. Waiting for user commands...")
    yield 
    print("🛑 Shutting down backend...")

app = FastAPI(title="Elite-Bot Multi-Asset Hub", lifespan=lifespan)

# --- 🎮 THE NEW CONTROL ENDPOINTS ---

@app.post("/start/{market}")
def start_engine(market: str):
    """Wakes up the selected bot."""
    if market == "crypto" and engine_status["crypto"] == "💤 Sleeping":
        threading.Thread(target=crypto_bot.run, daemon=True).start()
        engine_status["crypto"] = "🟢 Running"
        return {"msg": "Crypto Started"}
        
    elif market == "forex" and engine_status["forex"] == "💤 Sleeping":
        threading.Thread(target=forex_bot.run, daemon=True).start()
        engine_status["forex"] = "🟢 Running"
        return {"msg": "Forex Started"}
        
    return {"msg": "Already running or invalid market."}

@app.get("/telemetry")
def get_telemetry():
    """Provides live data. Fixed the KeyError by adding 'goal'."""
    return {
        "crypto": {
            "pnl": getattr(crypto_bot, 'daily_profit', 0.0),
            "status": engine_status["crypto"],
            "goal": getattr(crypto_bot, 'DAILY_PROFIT_GOAL', 500.0) # Fixed KeyError
        },
        "forex": {
            "pnl": getattr(forex_bot, 'daily_profit', 0.0),
            "status": engine_status["forex"],
            "goal": getattr(forex_bot, 'DAILY_PROFIT_GOAL', 500.0) # Fixed KeyError
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)