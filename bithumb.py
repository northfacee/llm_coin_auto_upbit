import requests
import time
from datetime import datetime
import json
from dotenv import load_dotenv
from pprint import pprint
from database_manager import DatabaseManager

class BithumbTrader:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://api.bithumb.com/public"
        self.headers = {"accept": "application/json"}
        self.db_manager = DatabaseManager()
        
    def get_current_price(self, market="BTC_KRW"):
        """현재가 정보 조회"""
        try:
            url = f"{self.base_url}/ticker/{market}"
            response = requests.get(url, headers=self.headers)
            return response.json()
        except Exception as e:
            print(f"현재가 조회 실패: {e}")
            return None

    def collect_market_data(self, market="BTC_KRW"):
        """모든 시장 데이터 수집"""
        try:
            current_price_data = self.get_current_price(market)
            if not current_price_data or 'data' not in current_price_data:
                raise Exception("현재가 데이터 없음")

            ticker_data = current_price_data['data']
            
            market_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'market': market,
                'current_price': float(ticker_data['closing_price']),
                'opening_price': float(ticker_data['opening_price']),
                'high_price': float(ticker_data['max_price']),
                'low_price': float(ticker_data['min_price']),
                'prev_closing_price': float(ticker_data['prev_closing_price']),
                'acc_trade_volume_24h': float(ticker_data['units_traded_24H']),
                'acc_trade_price_24h': float(ticker_data['acc_trade_value_24H']),
                'signed_change_rate': float(ticker_data['fluctate_rate_24H']),
                'signed_change_price': float(ticker_data['fluctate_24H'])
            }

            # 데이터베이스에 저장
            self.db_manager.save_market_data(market_data)
            return market_data

        except Exception as e:
            print(f"시장 데이터 수집 중 오류 발생: {e}")
            return None

    def run_trading_bot(self, market="BTC_KRW", interval=10):
        """자동매매 봇 실행"""
        print(f"트레이딩 봇 시작 - {market}")
        print(f"데이터 수집 간격: {interval}초")
        
        while True:
            try:
                market_data = self.collect_market_data(market)
                if not market_data:
                    print("시장 데이터 수집 실패 - 10초 후 재시도")
                    time.sleep(10)
                    continue
                
                print("\n수집된 시장 데이터:")
                print(json.dumps(market_data, indent=2, ensure_ascii=False))
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"봇 실행 중 오류 발생: {e}")
                print("10초 후 재시도")
                time.sleep(10)

if __name__ == "__main__":
    trader = BithumbTrader()
    trader.run_trading_bot(market="BTC_KRW", interval=10)