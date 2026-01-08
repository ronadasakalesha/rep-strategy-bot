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
        Checks 5M Entry Triggers based on Mode.
        LONG: RSI Dip 38-40 + Green Candle
        SHORT: RSI Rally > 60 + Cross Below 60 + Red Candle
        """
        if child_df is None or mode is None:
            return False, "Data Missing or No Mode", None
        
        current_close = child_df['close'].iloc[-1]
        current_open = child_df['open'].iloc[-1]
        current_rsi = child_df['rsi'].iloc[-1]

        # 1. LONG SETUP
        if mode == "LONG":
            # Logic: Check last ~6 candles for a dip into 38-40
            last_candles = child_df.tail(6)
            dip_found = False
            for i in range(len(last_candles) - 1): # Check previous
                r = last_candles['rsi'].iloc[i]
                if support_low <= r <= support_high:
                    dip_found = True
                    break
            
            # Also check if current is in zone
            if support_low <= current_rsi <= support_high:
                dip_found = True
            
            if dip_found:
                if current_close > current_open: # Green Confirmation
                    return True, "LONG Setup Found", child_df.iloc[-1]

        # 2. SHORT SETUP
        if mode == "SHORT":
            # Logic: Rally > 60 (Lookback far) THEN Cross Below 60
            # Check last ~50 candles for a peak > 60
            last_candles = child_df.tail(50)
            peak_found = False
            if last_candles['rsi'].max() > resist_low:
                peak_found = True
            
            if peak_found:
                # Trigger: Current RSI is < 60 (Crossed back down)
                if current_rsi < resist_low:
                     if current_close < current_open: # Red Confirmation
                         return True, "SHORT Setup Found", child_df.iloc[-1]

        return False, "No Child Setup", None

    def check_early_warning(self, child_df, parent_df):
        """
        Checks for Early Warning / Approaching Zone.
        Context based on 15M RSI (Parent 2).
        15M > 60 -> Alert if Child touches 40.
        15M < 40 -> Alert if Child touches 60.
        """
        if child_df is None or parent_df is None:
            return False, None

        current_rsi = child_df['rsi'].iloc[-1]
        parent_rsi = parent_df['rsi'].iloc[-1]

        if parent_rsi > 60:
            # Long Context
            if current_rsi <= 42:
                return True, f"⚠️ **Watch Alert**: RSI {current_rsi:.2f} near 40 (Support) | 15M Bullish ({parent_rsi:.2f})"
        
        if parent_rsi < 40:
            # Short Context
            if current_rsi >= 58:
                return True, f"⚠️ **Watch Alert**: RSI {current_rsi:.2f} near 60 (Resistance) | 15M Bearish ({parent_rsi:.2f})"
            
        return False, None

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
