# price_collector.py
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import os
from queue import Queue
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from technical_indicator import TechnicalIndicators

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

class BithumbTrader:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://api.bithumb.com"
        self.headers = {"accept": "application/json"}
        self.analyzer = MarketDataAnalyzer()
        self.symbol = os.getenv('COIN', 'BTC')

    def get_current_price(self) -> Optional[Dict]:
        """현재가 정보 조회"""
        try:
            url = f"{self.base_url}/public/ticker/{self.symbol}_KRW"
            print(f"요청 URL: {url}")
            
            response = requests.get(url, headers=self.headers)  
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != '0000':
                print(f"API 에러: {data.get('message', '알 수 없는 에러')}")
                return None
            
            return data['data']
        except Exception as e:
            print(f"현재가 조회 실패: {e}")
            return None

    def get_minute_candles(self, market: str, unit: int, count: int = 200) -> Optional[List[Dict]]:
        """분봉 데이터 조회 (v2 API)"""
        try:
            url = f"{self.base_url}/v1/candles/minutes/{unit}"
            params = {
                "market": f"KRW-{market}",
                "count": count
            }
            
            print(f"요청 URL: {url}")
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            return data
            
        except Exception as e:
            print(f"{unit}분봉 데이터 조회 실패: {e}")
            return None

    def get_daily_candles(self, market: str, count: int = 200) -> Optional[List[Dict]]:
        """일봉 데이터 조회 (v2 API)"""
        try:
            url = f"{self.base_url}/v1/candles/days"
            params = {
                "market": f"KRW-{market}",
                "count": count
            }
            
            print(f"요청 URL: {url}")
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            return data
            
        except Exception as e:
            print(f"일봉 데이터 조회 실패: {e}")
            return None
        
    def calculate_price_change_rate(self, current_price: float, comparison_price: float) -> float:
        """특정 시점 가격 대비 현재 가격의 변동률 계산"""
        if comparison_price == 0:
            return 0.0
        return ((current_price - comparison_price) / comparison_price) * 100

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
                    for timeframe in ['1m', '3m', '5m', '10m', '15m', '30m', '60m']:
                        if timeframe in market_data['analysis']:
                            print(f"{timeframe}: {market_data['analysis'][timeframe]['change_rate']:.2f}%")
                    
                    # 기술적 지표 출력
                    for timeframe in ['1m', '3m', '5m', '10m', '15m', '30m', '60m']:
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
                                print("지수이동평균(EMA):")
                                for period, value in analysis['ema'].items():
                                    if value is not None:
                                        print(f"  EMA{period}: {value:,.0f}")
                            
                            if 'wma' in analysis:
                                print("가중이동평균(WMA):")
                                for period, value in analysis['wma'].items():
                                    if value is not None:
                                        print(f"  WMA{period}: {value:,.0f}")
                            
                            if 'dmi' in analysis and all(x is not None for x in analysis['dmi']):
                                plus_di, minus_di, adx = analysis['dmi']
                                print(f"DMI: +DI={plus_di:.2f}, -DI={minus_di:.2f}, ADX={adx:.2f}")
                            
                            if 'atr' in analysis:
                                print(f"ATR: {analysis['atr']:,.0f}")
                            
                            if 'obv' in analysis:
                                print(f"OBV: {analysis['obv']:,.0f}")
                            
                            if 'vwap' in analysis:
                                print(f"VWAP: {analysis['vwap']:,.0f}")
                            
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

    def collect_market_data(self) -> Dict:
        try:
            # 현재가 정보 조회
            current_price_data = self.get_current_price()
            if not current_price_data:
                return None
                
            current_price = float(current_price_data['closing_price'])
            print(f"현재가: {current_price:,.0f} KRW")
            
            # 캔들스틱 데이터 수집 및 변동률 계산
            analysis_results = {}
            
            # 분봉 데이터 수집 (1분~60분)
            for unit in [1, 3, 5, 10, 15, 30, 60]:
                try:
                    data = self.get_minute_candles(self.symbol, unit, count=200)
                    
                    if data and len(data) > 0:
                        data = sorted(data, key=lambda x: x['timestamp'], reverse=True)
                        
                        now_price = float(data[0]['trade_price'])
                        comparison_index = min(unit, len(data) - 1)
                        prev_price = float(data[comparison_index]['opening_price'])
                        
                        change_rate = ((now_price - prev_price) / prev_price) * 100
                        
                        if len(data) >= 200:
                            prices_list = [float(candle['trade_price']) for candle in data[:200]]
                            highs_list = [float(candle['high_price']) for candle in data[:200]]
                            lows_list = [float(candle['low_price']) for candle in data[:200]]
                            volumes_list = [float(candle['candle_acc_trade_volume']) for candle in data[:200]]
                            
                            prices = np.array(prices_list)
                            highs = np.array(highs_list)
                            lows = np.array(lows_list)
                            volumes = np.array(volumes_list)
                            
                            analysis_results[f'{unit}m'] = {
                                'moving_averages': self.analyzer.indicators.calculate_moving_averages(prices, [5, 10, 20, 50, 200]),
                                'ema': {
                                    '12': self.analyzer.indicators.calculate_ema(prices, 12),
                                    '26': self.analyzer.indicators.calculate_ema(prices, 26)
                                },
                                'wma': {
                                    '20': self.analyzer.indicators.calculate_wma(prices, 20)
                                },
                                'rsi': self.analyzer.indicators.calculate_rsi(prices),
                                'stochastic': self.analyzer.indicators.calculate_stochastic(highs, lows, prices),
                                'bollinger_bands': self.analyzer.indicators.calculate_bollinger_bands(prices),
                                'dmi': self.analyzer.indicators.calculate_dmi(highs, lows, prices),
                                'atr': self.analyzer.indicators.calculate_atr(highs, lows, prices),
                                'obv': self.analyzer.indicators.calculate_obv(prices, volumes),
                                'vwap': self.analyzer.indicators.calculate_vwap(highs, lows, prices, volumes),
                                'mfi': self.analyzer.indicators.calculate_mfi(highs, lows, prices, volumes),
                                'williams_r': self.analyzer.indicators.calculate_williams_r(highs, lows, prices),
                                'cci': self.analyzer.indicators.calculate_cci(highs, lows, prices),
                                'change_rate': change_rate
                            }
                        else:
                            analysis_results[f'{unit}m'] = {
                                'change_rate': change_rate
                            }
                        
                except Exception as e:
                    print(f"{unit}분봉 처리 중 오류 발생: {e}")
                    analysis_results[f'{unit}m'] = {
                        'change_rate': 0.0
                    }
            
            # 24시간 데이터 추가
            analysis_results['24h'] = {
                'change_rate': float(current_price_data['fluctate_rate_24H'])
            }
            
            # 최종 데이터 구조화
            market_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'market': f"{self.symbol}_KRW",
                'current_price': current_price,
                'analysis': analysis_results
            }
            
            return market_data
            
        except Exception as e:
            print(f"시장 데이터 수집 중 오류 발생: {e}")
            return None

if __name__ == "__main__":
    trader = BithumbTrader()
    trader.run_trading_bot(interval=60)