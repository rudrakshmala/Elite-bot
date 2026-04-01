import numpy as np
import pickle
import os

class QLearningAgent:
    def __init__(self, actions=[0, 1, 2], learning_rate=0.1, discount_factor=0.9, epsilon=0.9):
        self.actions = actions  # 0: HOLD, 1: BUY_PAIR, 2: SELL_PAIR
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon  # Exploration rate (1.0 = 100% random, 0.0 = 100% strictly greedy)
        self.q_table = {}       # The "Cheat Sheet" brain

    def get_state_key(self, z_score, sentiment_score=0.5):
        """
        Convert Z-score + sentiment into a Tauric-style state key.
        Example: Z=2.1, sentiment=0.7 -> "Z_2.0_S_Positive"
        sentiment_score: 0-1, bucketed into Positive (>=0.6), Neutral (0.4-0.6), Negative (<=0.4)
        """
        rounded_z = round(z_score * 2) / 2
        if sentiment_score >= 0.6:
            sentiment_bucket = "Positive"
        elif sentiment_score <= 0.4:
            sentiment_bucket = "Negative"
        else:
            sentiment_bucket = "Neutral"
        return f"Z_{rounded_z}_S_{sentiment_bucket}"

    def choose_action(self, z_score, sentiment_score=0.5):
        state = self.get_state_key(z_score, sentiment_score)
        
        # Check if state exists in brain, if not add it
        self.check_state_exist(state)

        # Epsilon Greedy Strategy:
        # Sometimes explore (random move), sometimes exploit (use brain)
        if np.random.uniform() < self.epsilon:
            # Explore: Random move
            action = np.random.choice(self.actions)
        else:
            # Exploit: Pick the best known move for this state
            state_action = self.q_table[state]
            # Find action with highest value (breaking ties randomly)
            action = state_action.idxmax()
            
        return action

    def learn(self, z_score, sentiment_score, action, reward, next_z_score, next_sentiment_score=0.5):
        state = self.get_state_key(z_score, sentiment_score)
        next_state = self.get_state_key(next_z_score, next_sentiment_score)

        self.check_state_exist(state)
        self.check_state_exist(next_state)

        # Q-Learning Formula
        q_predict = self.q_table[state][action]
        q_target = reward + self.gamma * self.q_table[next_state].max()

        # Update the brain
        self.q_table[state][action] += self.lr * (q_target - q_predict)

        # Epsilon decay: decrease by 0.5% each learn, min 0.05
        self.epsilon = max(0.05, self.epsilon * (1 - 0.005))

    def check_state_exist(self, state):
        if state not in self.q_table:
            # Initialize new state with 0 values for all 3 actions
            import pandas as pd
            self.q_table[state] = pd.Series([0.0]*len(self.actions), index=self.actions)

    def save_brain(self, filename="smart_brain.pkl"):
        with open(filename, 'wb') as f:
            pickle.dump(self.q_table, f)
        print("🧠 Brain saved successfully!")

    def load_brain(self, filename="smart_brain.pkl"):
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                self.q_table = pickle.load(f)
            print("🧠 Brain loaded! Ready to trade.")
            self.epsilon = 0.0 # Stop exploring, start exploiting
        else:
            print("⚠️ No brain found. Starting fresh.")