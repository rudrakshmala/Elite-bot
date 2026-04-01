import yfinance as yf
import pandas as pd
import numpy as np
import universe
import strategy_engine
from rl_brain import QLearningAgent

# --- CONFIGURATION ---
SYMBOL_A = "MSFT"
SYMBOL_B = "AAPL"
EPISODES = 500  # How many times the bot plays the "game"

def get_training_data():
    print(f"📥 Downloading training data for {SYMBOL_A} vs {SYMBOL_B}...")
    data_a = yf.download(SYMBOL_A, period="2y", interval="1d", progress=False)['Close']
    data_b = yf.download(SYMBOL_B, period="2y", interval="1d", progress=False)['Close']
    
    # Align data
    df = pd.DataFrame({'A': data_a, 'B': data_b}).dropna()
    
    # Calculate Z-Scores using your strategy engine logic manually here for speed
    df['Spread'] = df['A'] - (1.4 * df['B']) # Simplified hedge ratio for speed
    df['Mean'] = df['Spread'].rolling(window=20).mean()
    df['Std'] = df['Spread'].rolling(window=20).std()
    df['Z_Score'] = (df['Spread'] - df['Mean']) / df['Std']
    return df.dropna()

def train():
    df = get_training_data()
    agent = QLearningAgent()
    
    print("🏋️ STARTED TRAINING... (This might take a moment)")
    
    for episode in range(EPISODES):
        state_idx = 0
        total_reward = 0
        
        # Start "Fresh" every episode
        position = 0 # 0=None, 1=Long Pair, -1=Short Pair
        entry_price_spread = 0
        
        # Iterate through the history (Day by Day)
        for i in range(len(df) - 1):
            current_z = df.iloc[i]['Z_Score']
            next_z = df.iloc[i+1]['Z_Score']
            current_spread = df.iloc[i]['Spread']
            next_spread = df.iloc[i+1]['Spread']
            
            # Bot chooses action (0=Hold, 1=Buy Pair, 2=Sell Pair)
            action = agent.choose_action(current_z)
            
            reward = 0
            
            # --- GAME RULES ---
            
            # Rule 1: If we buy the pair
            if action == 1: 
                if position == 0:
                    position = 1
                    entry_price_spread = current_spread
                elif position == -1: # We were short, now we buy to close
                    reward = entry_price_spread - current_spread # Profit calculation
                    position = 0
            
            # Rule 2: If we sell the pair
            elif action == 2:
                if position == 0:
                    position = -1
                    entry_price_spread = current_spread
                elif position == 1: # We were long, now we sell to close
                    reward = current_spread - entry_price_spread # Profit calculation
                    position = 0
            
            # Rule 3: Holding (Small penalty to discourage doing nothing forever)
            elif action == 0:
                reward = -0.1 

            # Teach the bot (use Neutral sentiment during training)
            agent.learn(current_z, 0.5, action, reward, next_z, 0.5)
            total_reward += reward

        # Decrease exploration (Bot becomes more confident)
        if agent.epsilon > 0.01:
            agent.epsilon *= 0.99
            
        if episode % 50 == 0:
            print(f"   Episode {episode}/{EPISODES}: Total Reward: ${total_reward:.2f} | Epsilon: {agent.epsilon:.2f}")

    print("✅ Training Complete!")
    agent.save_brain("smart_brain.pkl")

if __name__ == "__main__":
    train()