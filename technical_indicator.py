import numpy as np
from typing import List, Dict, Tuple, Optional

class TechnicalIndicators:
    @staticmethod
    def calculate_moving_averages(prices: np.array, periods: List[int] = [5, 10, 20, 50, 200]) -> Dict[int, float]:
        """여러 기간의 이동평균 계산"""
        mas = {}
        for period in periods:
            if len(prices) >= period:
                mas[period] = np.mean(prices[:period])
        return mas

    @staticmethod
    def calculate_ema(prices: np.array, period: int) -> float:
        """지수이동평균(EMA) 계산"""
        if len(prices) < period:
            return None
        
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        ema = np.sum(prices[:period] * weights)
        return ema

    @staticmethod
    def calculate_wma(prices: np.array, period: int) -> float:
        """가중이동평균(WMA) 계산"""
        if len(prices) < period:
            return None
            
        weights = np.arange(period, 0, -1)
        wma = np.average(prices[:period], weights=weights)
        return wma

    @staticmethod
    def calculate_rsi(prices: np.array, period: int = 14) -> float:
        """RSI(Relative Strength Index) 계산"""
        if len(prices) < period + 1:
            return None
            
        # 가격 변화 계산 (최신 데이터가 앞에 있으므로 부호를 반대로)
        deltas = -np.diff(prices)
        gain = np.where(deltas > 0, deltas, 0)
        loss = np.where(deltas < 0, -deltas, 0)
        
        # 첫 period 동안의 평균 상승/하락 계산
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_bollinger_bands(prices: np.array, period: int = 20, num_std: float = 2) -> Tuple[float, float, float]:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            return None, None, None
        
        sma = np.mean(prices[:period])
        std = np.std(prices[:period])
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        return upper_band, sma, lower_band

    @staticmethod
    def calculate_stochastic(high: np.array, low: np.array, close: np.array, 
                            k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Stochastic Oscillator 계산"""
        if len(high) < k_period or len(low) < k_period or len(close) < k_period:
            return None, None
            
        k_values = []
        
        for i in range(d_period):
            period_high = np.max(high[i:k_period+i])
            period_low = np.min(low[i:k_period+i])
            
            if period_high - period_low == 0:
                k_values.append(50)
            else:
                k = 100 * (close[i] - period_low) / (period_high - period_low)
                k_values.append(k)
        
        latest_k = k_values[0]
        d = np.mean(k_values)
        
        return latest_k, d

    @staticmethod
    def calculate_dmi(high: np.array, low: np.array, close: np.array, period: int = 14) -> Tuple[float, float, float]:
        """DMI(Directional Movement Index) 계산"""
        if len(high) < period + 1:
            return None, None, None
            
        tr = np.zeros(len(high) - 1)
        plus_dm = np.zeros(len(high) - 1)
        minus_dm = np.zeros(len(high) - 1)
        
        for i in range(len(high) - 1):
            tr[i] = max(high[i] - low[i],
                       abs(high[i] - close[i+1]),
                       abs(low[i] - close[i+1]))
            
            up_move = high[i] - high[i+1]
            down_move = low[i+1] - low[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            elif down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
        
        atr = np.mean(tr[:period])
        plus_di = 100 * np.mean(plus_dm[:period]) / atr if atr != 0 else 0
        minus_di = 100 * np.mean(minus_dm[:period]) / atr if atr != 0 else 0
        adx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) != 0 else 0
        
        return plus_di, minus_di, adx

    @staticmethod
    def calculate_atr(high: np.array, low: np.array, close: np.array, period: int = 14) -> float:
        """ATR(Average True Range) 계산"""
        if len(high) < period + 1:
            return None
            
        tr = np.zeros(len(high) - 1)
        for i in range(len(high) - 1):
            tr[i] = max(high[i] - low[i],
                       abs(high[i] - close[i+1]),
                       abs(low[i] - close[i+1]))
        
        return np.mean(tr[:period])

    @staticmethod
    def calculate_obv(close: np.array, volume: np.array) -> float:
        """OBV(On Balance Volume) 계산"""
        if len(close) < 2 or len(volume) < 2:
            return None
                
        # 누적 합계를 사용하는 방식으로 변경
        obv = 0
        for i in range(len(close)-1):
            if close[i] > close[i+1]:  # 현재가가 이전가보다 높으면
                obv += volume[i]
            elif close[i] < close[i+1]:  # 현재가가 이전가보다 낮으면
                obv -= volume[i]
        return obv

    @staticmethod
    def calculate_vwap(high: np.array, low: np.array, close: np.array, volume: np.array, period: int = 20) -> float:
        """VWAP(Volume Weighted Average Price) 계산"""
        if len(high) < period:
            return None
                
        # period 기간 동안의 VWAP 계산
        typical_price = (high[:period] + low[:period] + close[:period]) / 3
        vwap = np.sum(typical_price * volume[:period]) / np.sum(volume[:period])
        return vwap

    @staticmethod
    def calculate_mfi(high: np.array, low: np.array, close: np.array, volume: np.array, period: int = 14) -> float:
        """MFI(Money Flow Index) 계산"""
        if len(high) < period + 1:
            return None
            
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        positive_flow = np.zeros(len(high) - 1)
        negative_flow = np.zeros(len(high) - 1)
        
        for i in range(len(typical_price) - 1):
            if typical_price[i] > typical_price[i+1]:
                positive_flow[i] = money_flow[i]
            else:
                negative_flow[i] = money_flow[i]
        
        positive_mf = np.sum(positive_flow[:period])
        negative_mf = np.sum(negative_flow[:period])
        
        if negative_mf == 0:
            return 100
            
        mfr = positive_mf / negative_mf
        return 100 - (100 / (1 + mfr))

    @staticmethod
    def calculate_williams_r(high: np.array, low: np.array, close: np.array, period: int = 14) -> float:
        """Williams %R 계산"""
        if len(high) < period:
            return None
            
        highest_high = np.max(high[:period])
        lowest_low = np.min(low[:period])
        
        if highest_high - lowest_low == 0:
            return -50
            
        wr = (highest_high - close[0]) / (highest_high - lowest_low) * -100
        return wr

    @staticmethod
    def calculate_cci(high: np.array, low: np.array, close: np.array, period: int = 20) -> float:
        """CCI(Commodity Channel Index) 계산"""
        if len(high) < period:
            return None
            
        typical_price = (high + low + close) / 3
        sma_tp = np.mean(typical_price[:period])
        mean_deviation = np.mean(np.abs(typical_price[:period] - sma_tp))
        
        if mean_deviation == 0:
            return 0
            
        cci = (typical_price[0] - sma_tp) / (0.015 * mean_deviation)
        return cci