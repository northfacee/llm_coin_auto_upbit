# price_collector.py
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import threading
from queue import Queue
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

class MarketDataAnalyzer:
    def __init__(self):
        self.data_queue = Queue()
    
    @staticmethod
    def calculate_moving_averages(prices: np.array, periods: List[int]) -> Dict[int, float]:
        """여러 기간의 이동평균 계산"""
        mas = {}
        for period in periods:
            if len(prices) >= period:
                mas[period] = np.mean(prices[-period:])
        return mas

    @staticmethod
    def calculate_rsi(prices: np.array, period: int = 14) -> float:
        """RSI 계산"""
        deltas = np.diff(prices)
        gain = np.where(deltas > 0, deltas, 0)
        loss = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_stochastic(high: np.array, low: np.array, close: np.array, 
                           k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Stochastic Oscillator 계산"""
        lowest_low = np.min(low[-k_period:])
        highest_high = np.max(high[-k_period:])
        
        if highest_high - lowest_low == 0:
            return 50, 50
        
        k = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low)
        d = np.mean([k])  # 실제로는 이전 값들도 필요
        return k, d

    @staticmethod
    def calculate_macd(prices: np.array, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """MACD 계산"""
        ema_fast = np.mean(prices[-fast:])  # 간단화를 위해 SMA 사용
        ema_slow = np.mean(prices[-slow:])
        macd_line = ema_fast - ema_slow
        signal_line = np.mean([macd_line])  # 실제로는 이전 값들도 필요
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(prices: np.array, period: int = 20, num_std: float = 2) -> Tuple[float, float, float]:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            return None, None, None
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        return upper_band, sma, lower_band

class BithumbTrader:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://api.bithumb.com"
        self.headers = {"accept": "application/json"}
        self.analyzer = MarketDataAnalyzer()

    def get_transaction_history(self, symbol: str) -> Optional[List[Dict]]:
        """최근 체결 내역 조회"""
        try:
            url = f"{self.base_url}/public/transaction_history/{symbol}_KRW"
            print(f"요청 URL: {url}")
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != '0000':
                print(f"API 에러: {data.get('message', '알 수 없는 에러')}")
                return None
            
            return data['data']
            
        except Exception as e:
            print(f"체결 내역 조회 실패: {e}")
            return None

    def get_orderbook(self, symbol: str) -> Optional[Dict]:
        """호가 정보 조회"""
        try:
            url = f"{self.base_url}/public/orderbook/{symbol}_KRW"
            print(f"요청 URL: {url}")
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != '0000':
                print(f"API 에러: {data.get('message', '알 수 없는 에러')}")
                return None
            
            return data['data']
            
        except Exception as e:
            print(f"호가 데이터 조회 실패: {e}")
            return None

    def get_current_price(self, symbol: str = "BTC") -> Optional[Dict]:
        """현재가 정보 조회"""
        try:
            url = f"{self.base_url}/public/ticker/{symbol}_KRW"
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
        
    def get_candlestick_data(self, symbol: str, interval: str) -> Optional[List[Dict]]:
        """캔들스틱 데이터 조회"""
        try:
            # 시간 간격에 따른 엔드포인트 선택 (1h 제거)
            if interval == '30m':
                url = f"{self.base_url}/public/candlestick/{symbol}_KRW/30m"
            elif interval == '24h':
                url = f"{self.base_url}/public/candlestick/{symbol}_KRW/24h"
            else:
                raise ValueError(f"지원하지 않는 시간 간격: {interval}")
            
            print(f"요청 URL: {url}")
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != '0000':
                print(f"API 에러: {data.get('message', '알 수 없는 에러')}")
                return None
            
            return data['data']
            
        except Exception as e:
            print(f"캔들스틱 데이터 조회 실패: {e}")
            return None

    def collect_market_data(self, market: str = "BTC_KRW") -> Dict:
        """시장 데이터 수집 및 분석"""
        try:
            symbol = market.split('_')[0]
            
            # 현재가 정보 조회
            current_price_data = self.get_current_price(symbol)
            if current_price_data:
                print(f"현재가: {current_price_data['closing_price']} KRW")
            
            # 캔들스틱 데이터 수집 (30m, 24h만)
            candle_data = {}
            for interval in ['30m', '24h']:
                data = self.get_candlestick_data(symbol, interval)
                if data:
                    print(f"{interval} 캔들스틱 데이터 수집 완료")
                    candle_data[interval] = data
            
            # 호가 데이터 수집
            orderbook = self.get_orderbook(symbol)
            if orderbook:
                print("호가 데이터 수집 완료")
            
            # 최근 체결 내역 수집
            transactions = self.get_transaction_history(symbol)
            if transactions:
                print("체결 내역 수집 완료")
            
            # 데이터 분석
            analysis_results = {}
            for interval, data in candle_data.items():
                try:
                    if data and len(data) > 0:
                        # 숫자 변환 시 쉼표 제거 및 예외 처리
                        def safe_float(value):
                            if isinstance(value, str):
                                return float(value.replace(',', ''))
                            return float(value)

                        prices = np.array([safe_float(candle[2]) for candle in data])  # 종가
                        highs = np.array([safe_float(candle[3]) for candle in data])   # 고가
                        lows = np.array([safe_float(candle[4]) for candle in data])    # 저가
                        
                        analysis_results[interval] = {
                            'moving_averages': self.analyzer.calculate_moving_averages(prices, [5, 10, 20, 50, 200]),
                            'rsi': self.analyzer.calculate_rsi(prices),
                            'stochastic': self.analyzer.calculate_stochastic(highs, lows, prices),
                            'macd': self.analyzer.calculate_macd(prices),
                            'bollinger_bands': self.analyzer.calculate_bollinger_bands(prices),
                            'ohlcv': data[-1]
                        }
                        print(f"{interval} 기술적 분석 완료")
                except Exception as e:
                    print(f"{interval} 데이터 분석 중 오류 발생: {e}")
                    print(f"데이터 샘플: {data[0] if data else 'No data'}")
            
            # 최종 데이터 구조화
            market_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'market': market,
                'current_price': current_price_data,
                'analysis': analysis_results,
                'orderbook': orderbook,
                'transactions': transactions
            }
            
            # 분석용 큐에 데이터 추가
            self.analyzer.data_queue.put(market_data)
            return market_data
            
        except Exception as e:
            print(f"시장 데이터 수집 중 오류 발생: {e}")
            print(f"상세 에러: {str(e)}")
            return None

    def run_trading_bot(self, market: str = "BTC_KRW", interval: int = 60):
        """데이터 수집 봇 실행"""
        print(f"데이터 수집 봇 시작 - {market}")
        print(f"수집 간격: {interval}초")
        
        while True:
            try:
                market_data = self.collect_market_data(market)
                if market_data and 'current_price' in market_data:
                    print(f"\n{market_data['timestamp']} - 데이터 수집 및 분석 완료")
                    print(f"현재가: {float(market_data['current_price']['closing_price']):,.0f} KRW")
                    print(f"24시간 변동률: {market_data['current_price']['fluctate_rate_24H']}%")
                    
                    # 기술적 지표 출력 (24시간 기준)
                    if '24h' in market_data['analysis']:
                        analysis = market_data['analysis']['24h']
                        print(f"RSI(14): {analysis['rsi']:.2f}")
                        print(f"MACD: {analysis['macd'][0]:.2f} / Signal: {analysis['macd'][1]:.2f}")
                        bb = analysis['bollinger_bands']
                        if all(x is not None for x in bb):
                            print(f"볼린저 밴드: {bb[0]:,.0f} / {bb[1]:,.0f} / {bb[2]:,.0f}")
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"봇 실행 중 오류 발생: {e}")
                print("1분 후 재시도")
                time.sleep(60)

if __name__ == "__main__":
    trader = BithumbTrader()
    trader.run_trading_bot(market="BTC_KRW", interval=30)