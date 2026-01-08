import pandas_ta as ta
import pandas as pd
from logzero import logger

class REPStrategy:
    def __init__(self, rsi_period=14):
        self.rsi_period = rsi_period

    def calculate_rsi(self, df):
        if df is None or len(df) < self.rsi_period:
            return None
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        return df

    def check_parent_conditions(self, parent1_df, parent2_df, threshold_long=60, threshold_short=40, lookback=10):
        """
        Checks parent timeframes.
        Logic: 
        - Parent 1 (1H): STRICT. Current RSI must be > threshold_long or < threshold_short.
        - Parent 2 (15M): RECENT. Look back 'lookback' candles.
        Returns: (bool, str, mode)
        """
        if parent1_df is None or parent2_df is None:
            return False, "Data Missing", None

        # 1. Check Parent 1 (1H) - STRICT (Current Candle)
        p1_rsi = parent1_df['rsi'].iloc[-1]
        p1_mode = "NEUTRAL"
        if p1_rsi > threshold_long:
            p1_mode = "LONG"
        elif p1_rsi < threshold_short:
            p1_mode = "SHORT"
        
        if p1_mode == "NEUTRAL":
             return False, f"Parent 1 (1H) Neutral (RSI: {p1_rsi:.2f})", None

        # 2. Check Parent 2 (15M) - RELAXED (Recent Lookback)
        # Helper to find trend in recent history
        def get_trend_recent(df, t_long, t_short, lb):
            subset = df.tail(lb)
            for i in range(len(subset) - 1, -1, -1):
                rsi = subset['rsi'].iloc[i]
                if rsi > t_long:
                    return "LONG"
                if rsi < t_short:
                    return "SHORT"
            return "NEUTRAL"

        p2_mode = get_trend_recent(parent2_df, threshold_long, threshold_short, lookback)

        # 3. Validation: Both must agree
        if p1_mode == "LONG" and p2_mode == "LONG":
            return True, f"Parents Bullish (P1 Strict, P2 Recent)", "LONG"
        
        if p1_mode == "SHORT" and p2_mode == "SHORT":
            return True, f"Parents Bearish (P1 Strict, P2 Recent)", "SHORT"

        return False, f"Parents Mismatch (P1:{p1_mode}, P2:{p2_mode})", None

    def check_child_condition(self, child_df, mode, support_low=38, support_high=40, resist_low=60, resist_high=62):
        """
            # We iterate to find the cross
            for i in range(len(last_candles) - 1):
                prev_rsi = last_candles['rsi'].iloc[i]
                # Check if this candle or previous ones were > 60.
                # Actually, simpler: Look for a transition from > 60 to < 60.
                
                # If we just check if ANY candle > 60 recently, and NOW/Recently we are < 60.
                if prev_rsi > 60:
                     # Now look for a cross down in subsequent candles
                     for j in range(i + 1, len(last_candles)):
                         curr_rsi = last_candles['rsi'].iloc[j]
                         if curr_rsi < 60:
                             # CROSS DOWN HAPPENED at index j
                             # Check for Red Candle at index j? User didn't explicitly demand Red, but it's safe.
                             # User: "come down below 60... take a short trade"
                             cand = last_candles.iloc[j]
                             if cand['close'] < cand['open']: # Red candle confirmation
                                  return True, f"Child SHORT Setup: RSI Cross Below 60 & Red Candle", cand
            
            # Additional check: Maybe the cross just happened at the very last candle? 
            # (Covered by loop if loop covers -1, which tail(6) does).
        
        return False, f"Child No Setup ({mode})", None

    def check_exit_condition(self, child_df, parent_df):
        """
        Checks for Exit Alerts.
        Buy Exit: 15M > 60 AND 5M touches 60.
        Sell Exit: 15M < 40 AND 5M touches 40.
        """
        if child_df is None or parent_df is None:
            return False, None
            
        current_5m_rsi = child_df['rsi'].iloc[-1]
        current_15m_rsi = parent_df['rsi'].iloc[-1]
        
        # Buy Exit (Both High)
        if current_15m_rsi > 60 and current_5m_rsi >= 60:
             return True, f"🚨 **Buy Exit Alert**: 5M RSI ({current_5m_rsi:.2f}) touched 60 while 15M > 60"

        # Sell Exit (Both Low)
        if current_15m_rsi < 40 and current_5m_rsi <= 40:
             return True, f"🚨 **Sell Exit Alert**: 5M RSI ({current_5m_rsi:.2f}) touched 40 while 15M < 40"
             
        return False, None
