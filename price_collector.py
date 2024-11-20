import numpy as np
import pandas as pd
from typing import Dict, Optional
import os
import pyupbit
from queue import Queue
from datetime import datetime
from dotenv import load_dotenv
from technical_indicator import TechnicalIndicators
import time

class MarketDataAnalyzer:
    def __init__(self):
        self.data_queue = Queue()
        self.indicators = TechnicalIndicators()

    def analyze_market_data(self, prices: np.array, high: np.array, low: np.array, 
                          close: np.array, volume: np.array) -> Dict:
        """모든 기술적 지표 계산"""
        return {
            'moving_averages': self.indicators.calculate_moving_averages(prices, [5, 10, 20, 50, 200]),
            'ema': {
                '12': self.indicators.calculate_ema(prices, 12),
                '26': self.indicators.calculate_ema(prices, 26)
            },
            'wma': {
                '20': self.indicators.calculate_wma(prices, 20)
            },
            'rsi': self.indicators.calculate_rsi(prices),
            'bollinger_bands': self.indicators.calculate_bollinger_bands(prices),
            'stochastic': self.indicators.calculate_stochastic(high, low, close),
            'dmi': self.indicators.calculate_dmi(high, low, close),
            'atr': self.indicators.calculate_atr(high, low, close),
            'obv': self.indicators.calculate_obv(close, volume),
            'vwap': self.indicators.calculate_vwap(high, low, close, volume),
            'mfi': self.indicators.calculate_mfi(high, low, close, volume),
            'williams_r': self.indicators.calculate_williams_r(high, low, close),
            'cci': self.indicators.calculate_cci(high, low, close)
        }

class UpbitTrader:
    def __init__(self):
        """업비트 트레이더 초기화"""
        load_dotenv()
        self.symbol = os.getenv('COIN', 'BTC')
        self.market = f"KRW-{self.symbol}"
        self.analyzer = MarketDataAnalyzer()

    def get_current_price(self) -> Optional[Dict]:
        """현재가 정보 조회"""
        try:
            ticker = pyupbit.get_current_price(self.market)
            if ticker:
                return {
                    'closing_price': ticker,
                    'opening_price': ticker,
                    'max_price': ticker,
                    'min_price': ticker
                }
            return None
        except Exception as e:
            print(f"현재가 조회 실패: {e}")
            return None

    def get_minute_candles(self, unit: int = 1, count: int = 200) -> Optional[pd.DataFrame]:
        """분봉 데이터 조회"""
        try:
            df = pyupbit.get_ohlcv(self.market, interval=f"minute{unit}", count=count)
            return df
        except Exception as e:
            print(f"{unit}분봉 데이터 조회 실패: {e}")
            return None
        
    def calculate_price_change_rate(self, current_price: float, comparison_price: float) -> float:
        """특정 시점 가격 대비 현재 가격의 변동률 계산"""
        if comparison_price == 0:
            return 0.0
        return ((current_price - comparison_price) / comparison_price) * 100

    def collect_market_data(self) -> Dict:
        """시장 데이터 수집"""
        try:
            current_price = self.get_current_price()
            if not current_price:
                return None

            analysis_results = {}
            
            # 분봉 데이터 수집 및 분석
            for unit in [1, 3, 5, 10, 15, 30]:
                try:
                    df = self.get_minute_candles(unit, count=200)
                    if df is not None and not df.empty:
                        prices = df['close'].values
                        highs = df['high'].values
                        lows = df['low'].values
                        volumes = df['volume'].values

                        change_rate = ((prices[-1] - prices[-unit]) / prices[-unit] * 100 
                                     if len(prices) >= unit else 0)

                        analysis_results[f'{unit}m'] = {
                            'moving_averages': self.analyzer.indicators.calculate_moving_averages(prices),
                            'ema': {
                                '12': self.analyzer.indicators.calculate_ema(prices, 12),
                                '26': self.analyzer.indicators.calculate_ema(prices, 26)
                            },
                            'rsi': self.analyzer.indicators.calculate_rsi(prices),
                            'bollinger_bands': self.analyzer.indicators.calculate_bollinger_bands(prices),
                            'stochastic': self.analyzer.indicators.calculate_stochastic(highs, lows, prices),
                            'dmi': self.analyzer.indicators.calculate_dmi(highs, lows, prices),
                            'atr': self.analyzer.indicators.calculate_atr(highs, lows, prices),
                            'obv': self.analyzer.indicators.calculate_obv(prices, volumes),
                            'vwap': self.analyzer.indicators.calculate_vwap(highs, lows, prices, volumes),
                            'mfi': self.analyzer.indicators.calculate_mfi(highs, lows, prices, volumes),
                            'williams_r': self.analyzer.indicators.calculate_williams_r(highs, lows, prices),
                            'cci': self.analyzer.indicators.calculate_cci(highs, lows, prices),
                            'change_rate': change_rate
                        }
                except Exception as e:
                    print(f"{unit}분봉 처리 중 오류: {e}")
                    analysis_results[f'{unit}m'] = {'change_rate': 0.0}

            # 24시간 데이터 추가
            day_df = pyupbit.get_ohlcv(self.market, interval="day", count=1)
            if day_df is not None and not day_df.empty:
                day_change = ((day_df['close'].iloc[-1] - day_df['open'].iloc[-1]) / 
                            day_df['open'].iloc[-1] * 100)
                analysis_results['24h'] = {'change_rate': day_change}
            else:
                analysis_results['24h'] = {'change_rate': 0.0}

            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'market': self.market,
                'current_price': current_price['closing_price'],
                'analysis': analysis_results
            }

        except Exception as e:
            print(f"시장 데이터 수집 중 오류: {e}")
            return None

    def run_trading_bot(self, interval: int = 60):
        """데이터 수집 봇 실행"""
        print(f"데이터 수집 시작 - {self.symbol}")
        print(f"수집 간격: {interval}초")
        
        while True:
            try:
                market_data = self.collect_market_data()
                if market_data:
                    print(f"\n{market_data['timestamp']} - 데이터 수집 및 분석 완료")
                    print(f"현재가: {market_data['current_price']:,.0f} KRW")
                    
                    # 변동률 출력
                    print("\n각 시간대별 변동률:")
                    for timeframe in ['1m', '3m', '5m', '10m', '15m', '30m', '24h']:
                        if timeframe in market_data['analysis']:
                            print(f"{timeframe}: {market_data['analysis'][timeframe]['change_rate']:.2f}%")
                    
                    # 기술적 지표 출력
                    for timeframe in ['1m', '3m', '5m', '10m', '15m', '30m']:
                        if timeframe in market_data['analysis']:
                            analysis = market_data['analysis'][timeframe]
                            print(f"\n{timeframe} 기술적 지표:")
                            
                            if 'rsi' in analysis:
                                print(f"RSI(14): {analysis['rsi']:.2f}")
                            
                            if 'bollinger_bands' in analysis and all(x is not None for x in analysis['bollinger_bands']):
                                bb = analysis['bollinger_bands']
                                print(f"볼린저 밴드: {bb[0]:,.0f} / {bb[1]:,.0f} / {bb[2]:,.0f}")
                            
                            if 'moving_averages' in analysis:
                                print("이동평균선:")
                                for period, value in analysis['moving_averages'].items():
                                    print(f"  MA{period}: {value:,.0f}")
                            
                            if 'stochastic' in analysis and all(x is not None for x in analysis['stochastic']):
                                k, d = analysis['stochastic']
                                print(f"Stochastic: %K={k:.2f}, %D={d:.2f}")

                            if 'ema' in analysis:
                                print("지수이동평균선:")
                                for period, value in analysis['ema'].items():
                                    print(f"  EMA{period}: {value:,.0f}")

                            if 'dmi' in analysis and all(x is not None for x in analysis['dmi']):
                                plus_di, minus_di, adx = analysis['dmi']
                                print(f"DMI: +DI={plus_di:.2f}, -DI={minus_di:.2f}, ADX={adx:.2f}")

                            if 'mfi' in analysis:
                                print(f"MFI: {analysis['mfi']:.2f}")

                            if 'williams_r' in analysis:
                                print(f"Williams %R: {analysis['williams_r']:.2f}")

                            if 'cci' in analysis:
                                print(f"CCI: {analysis['cci']:.2f}")
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"봇 실행 중 오류 발생: {e}")
                print("1분 후 재시도")
                time.sleep(60)

if __name__ == "__main__":
    trader = UpbitTrader()
    trader.run_trading_bot(interval=60)