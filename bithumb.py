import requests
import time
from datetime import datetime
from dotenv import load_dotenv
import json
from typing import Optional, Dict, Any
from database_manager import DatabaseManager

class BithumbTrader:
    def __init__(self):
        """빗썸 트레이딩 봇 초기화"""
        load_dotenv()
        self.base_url = "https://api.bithumb.com/public"
        self.headers = {"accept": "application/json"}
        self.db_manager = DatabaseManager()
    
    def get_current_price(self, market: str = "BTC_KRW") -> Optional[Dict[str, Any]]:
        """현재가 정보 조회"""
        try:
            url = f"{self.base_url}/ticker/{market}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"현재가 조회 실패: {e}")
            return None

    def collect_market_data(self, market: str = "BTC_KRW") -> Optional[Dict[str, Any]]:
        """모든 시장 데이터 수집 및 저장"""
        try:
            current_price_data = self.get_current_price(market)
            if not current_price_data or 'data' not in current_price_data:
                raise Exception("현재가 데이터 없음")
            
            ticker_data = current_price_data['data']
            timestamp = datetime.now()
            
            # 필요한 데이터 추출
            current_price = float(ticker_data['closing_price'])
            opening_price = float(ticker_data['opening_price'])
            high_price = float(ticker_data['max_price'])
            low_price = float(ticker_data['min_price'])
            signed_change_rate = float(ticker_data['fluctate_rate_24H'])
            
            # DatabaseManager의 save_market_data 메서드에 맞게 데이터 저장
            self.db_manager.save_market_data(
                timestamp=timestamp,
                current_price=current_price,
                opening_price=opening_price,
                high_price=high_price,
                low_price=low_price,
                signed_change_rate=signed_change_rate
            )
            
            # 로깅 및 분석용 전체 데이터 구조
            market_data = {
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'market': market,
                'current_price': current_price,
                'opening_price': opening_price,
                'high_price': high_price,
                'low_price': low_price,
                'signed_change_rate': signed_change_rate,
                'acc_trade_volume_24h': float(ticker_data['units_traded_24H']),
                'acc_trade_price_24h': float(ticker_data['acc_trade_value_24H'])
            }
            
            print(f"데이터베이스 저장 완료: {timestamp}")
            return market_data
            
        except Exception as e:
            print(f"시장 데이터 수집 중 오류 발생: {e}")
            return None

    def run_trading_bot(self, market: str = "BTC_KRW", interval: int = 60):
        """자동매매 봇 실행"""
        print(f"트레이딩 봇 시작 - {market}")
        print(f"데이터 수집 간격: {interval}초")
        
        while True:
            try:
                # 시장 데이터 수집
                market_data = self.collect_market_data(market)
                if not market_data:
                    print("시장 데이터 수집 실패 - 1분 후 재시도")
                    time.sleep(60)
                    continue
                
                # 데이터 출력
                print("\n" + "="*50)
                print(f"수집 시각: {market_data['timestamp']}")
                print(f"현재가: {market_data['current_price']:,} KRW")
                print(f"변동률: {market_data['signed_change_rate']}%")
                print(f"거래량(24H): {market_data['acc_trade_volume_24h']:,.2f}")
                print("="*50 + "\n")
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"봇 실행 중 오류 발생: {e}")
                print("1분 후 재시도")
                time.sleep(60)

if __name__ == "__main__":
    trader = BithumbTrader()
    trader.run_trading_bot(market="BTC_KRW", interval=10)