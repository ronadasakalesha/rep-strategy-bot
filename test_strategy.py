import unittest
import pandas as pd
import numpy as np
from strategy_rep import REPStrategy

class TestREPStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = REPStrategy()

    def create_mock_df(self, rsi_values, close_values=None):
        df = pd.DataFrame()
        df['rsi'] = rsi_values
        # Fill required columns with dummy data if not provided
        if close_values is None:
            df['close'] = [100] * len(rsi_values)
            df['open'] = [99] * len(rsi_values)
            df['high'] = [101] * len(rsi_values)
            df['low'] = [98] * len(rsi_values)
        else:
            df['close'] = close_values
            # Assume green candles for simplicity unless close < open
            df['open'] = [x - 1 for x in close_values] 
            df['high'] = [x + 1 for x in close_values]
            df['low'] = [x - 2 for x in close_values]
            
        return df

    def test_parents_bullish(self):
        parent1 = self.create_mock_df([65])
        parent2 = self.create_mock_df([62])
        ok, msg = self.strategy.check_parent_conditions(parent1, parent2)
        self.assertTrue(ok)

    def test_parents_bearish(self):
        parent1 = self.create_mock_df([55])
        parent2 = self.create_mock_df([62])
        ok, msg = self.strategy.check_parent_conditions(parent1, parent2)
        self.assertFalse(ok)

    def test_child_dip_and_green_candle(self):
        # Last candle: RSI 39 (in zone), Green Candle (Close > Open)
        # We manually construct this
        df = pd.DataFrame({
            'rsi': [50, 45, 39],
            'open': [100, 100, 100],
            'close': [101, 101, 102], # Green
            'high': [102, 102, 103],
            'low': [99, 99, 99]
        })
        ok, msg, candle = self.strategy.check_child_condition(df)
        self.assertTrue(ok)
        self.assertIsNotNone(candle)

    def test_child_dip_but_red_candle(self):
        # RSI 39 (in zone), Red Candle
        df = pd.DataFrame({
            'rsi': [50, 45, 39],
            'open': [102, 102, 102],
            'close': [103, 103, 100], # Last one is Red (100 < 102)
            'high': [104, 104, 103],
            'low': [98, 98, 98]
        })
        ok, msg, candle = self.strategy.check_child_condition(df)
        self.assertFalse(ok)

if __name__ == '__main__':
    unittest.main()
