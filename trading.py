from typing import Literal, Optional, Dict, Any
import base64
import hmac
import hashlib
import urllib.parse
import requests
import time
from decimal import Decimal, ROUND_DOWN
import os
from dotenv import load_dotenv
import json
import traceback
import sqlite3
from datetime import datetime, timedelta
import jwt
import uuid

class BithumbTradeExecutor:
    def __init__(self):
        """빗썸 API 거래 실행기 초기화"""
        load_dotenv()
        self.api_url = "https://api.bithumb.com"
        self.api_key = os.getenv('BITHUMB_API_KEY')
        self.api_secret = os.getenv('BITHUMB_API_SECRET').encode('utf-8')
        self.api_key_v2 = os.getenv('BITHUMB_API_KEY_V2')
        self.api_secret_v2 = os.getenv('BITHUMB_API_SECRET_V2')
        
        self.symbol = os.getenv('COIN', 'BTC')
        self.db_path = "crypto_analysis.db"

        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in environment variables")
        
        self.min_trade_amounts = {
            'BTC': Decimal('0.0001'),
            'XRP': Decimal('5'),
            'DOGE': Decimal('9'),
        }
        
        self.default_min_trade_amount = Decimal('1')
    
    def get_min_trade_amount(self) -> Decimal:
        """현재 설정된 코인의 최소 거래량 반환"""
        return self.min_trade_amounts.get(self.symbol, self.default_min_trade_amount)

    def _create_signature(self, endpoint: str, params: dict) -> dict:
        """API 요청 서명 및 헤더 생성"""
        nonce = str(int(time.time() * 1000))
        params['nonce'] = nonce
        
        query_string = urllib.parse.urlencode(params)
        sign_data = endpoint + ";" + query_string + ";" + nonce
        
        signature = hmac.new(
            self.api_secret,
            sign_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        encoded_signature = base64.b64encode(signature.encode('utf-8')).decode('utf-8')
        
        return {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'api-client-type': '2',
            'Api-Key': self.api_key,
            'Api-Nonce': nonce,
            'Api-Sign': encoded_signature
        }

    def _send_request(self, endpoint: str, params: dict) -> dict:
        """API 요청 전송"""
        try:
            headers = self._create_signature(endpoint, params)
            url = f"{self.api_url}{endpoint}"
            
            response = requests.post(url, headers=headers, data=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API 요청 실패: {str(e)}")

    def get_account_info(self) -> list:
        """전체 계좌 정보 조회"""
        try:
            headers = {
                'Authorization': self._create_jwt_token()
            }
            
            response = requests.get(f"{self.api_url}/v1/accounts", headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"계좌 정보 조회 중 오류 발생: {str(e)}")
            return []

    def get_balance(self) -> dict:
        """계좌 잔고 조회"""
        try:
            params = {
                'currency': self.symbol
            }
            
            response = self._send_request("/info/balance", params)
            
            if response.get('status') != '0000':
                raise Exception(f"잔고 조회 실패: {response.get('message')}")
            
            data = response.get('data', {})
            symbol = self.symbol.lower()
            
            available_coin_key = f'available_{symbol}'
            total_coin_key = f'total_{symbol}'
            
            result = {
                'krw_available': Decimal(str(data.get('available_krw', '0'))),
                f'{symbol}_available': Decimal(str(data.get(available_coin_key, '0'))),
                'krw_total': Decimal(str(data.get('total_krw', '0'))),
                f'{symbol}_total': Decimal(str(data.get(total_coin_key, '0')))
            }
            
            return result
            
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {str(e)}")
            print("상세 오류:", traceback.format_exc())
            return {
                'krw_available': Decimal('0'),
                f'{self.symbol.lower()}_available': Decimal('0'),
                'krw_total': Decimal('0'),
                f'{self.symbol.lower()}_total': Decimal('0')
            }

    def get_current_position(self) -> Dict[str, Any]:
        """현재 포지션 정보 조회"""
        try:
            account_info = self.get_account_info()
            
            coin_data = next((item for item in account_info 
                        if item.get('currency') == self.symbol), None)
            
            if not coin_data:
                return {
                    'avg_price': 0,
                    'total_quantity': 0,
                    'total_investment': 0,
                    'investment_ratio': 0
                }
            
            balance = Decimal(str(coin_data.get('balance', '0')))
            locked = Decimal(str(coin_data.get('locked', '0')))
            avg_buy_price = Decimal(str(coin_data.get('avg_buy_price', '0')))
            
            total_quantity = balance + locked
            total_investment = total_quantity * avg_buy_price
            
            krw_data = next((item for item in account_info 
                        if item.get('currency') == 'KRW'), None)
            
            if krw_data:
                krw_balance = Decimal(str(krw_data.get('balance', '0')))
                total_assets = krw_balance + total_investment
                investment_ratio = (total_investment / total_assets * 100) if total_assets > 0 else Decimal('0')
            else:
                investment_ratio = Decimal('0')
            
            return {
                'avg_price': float(avg_buy_price),
                'total_quantity': float(total_quantity),
                'total_investment': float(total_investment),
                'investment_ratio': float(investment_ratio)
            }
                    
        except Exception as e:
            print(f"포지션 정보 조회 중 오류 발생: {str(e)}")
            return {
                'avg_price': 0,
                'total_quantity': 0,
                'total_investment': 0,
                'investment_ratio': 0
            }

    def execute_trade(self, decision: Dict[str, Any], max_investment: float, current_price: float) -> Dict:
        """거래 결정 실행"""
        try:
            if isinstance(decision, dict) and 'decision' in decision:
                decision_text = decision['decision']
                trade_type = self._parse_decision(decision_text)
            else:
                return {'status': 'ERROR', 'message': '잘못된 결정 형식'}

            if trade_type == 'HOLD':
                return {
                    'status': 'SUCCESS',
                    'type': 'HOLD',
                    'message': '관망 결정으로 인한 거래 건너뛰기',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

            balance = self.get_balance()
            symbol = self.symbol.lower()
            available_krw = Decimal(str(balance['krw_available']))
            available_coin = Decimal(str(balance[f'{symbol}_available']))

            investment_ratio = self._parse_investment_ratio(decision_text)
            max_investment_decimal = Decimal(str(max_investment))
            investment_amount = max_investment_decimal * Decimal(str(investment_ratio))
            
            print(f"\n=== 투자 계산 상세 ===")
            print(f"최대 투자금액: {float(max_investment_decimal):,.0f}원")
            print(f"투자 비중: {float(investment_ratio)*100:.1f}%")
            print(f"계산된 투자금액: {float(investment_amount):,.0f}원")
            print(f"사용 가능한 KRW: {float(available_krw):,.0f}원")

            if trade_type == 'BUY':
                if available_krw < Decimal('10000'):
                    return {
                        'status': 'ERROR',
                        'type': 'BUY_FAIL',
                        'message': f'잔액 부족 (현재 잔액: {float(available_krw):,.0f}원)',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                actual_investment = min(investment_amount, available_krw)
                print(f"실제 투자금액: {float(actual_investment):,.0f}원")
                return self._place_buy_order(actual_investment, Decimal(str(current_price)))

            elif trade_type == 'SELL':
                if available_coin < self.get_min_trade_amount():
                    return {
                        'status': 'ERROR',
                        'type': 'SELL_FAIL',
                        'message': f'{self.symbol} 잔액 부족 (현재 보유량: {float(available_coin):.8f} {self.symbol})',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                sell_quantity = available_coin * Decimal(str(investment_ratio))
                return self._place_sell_order(sell_quantity, Decimal(str(current_price)))

            return {
                'status': 'ERROR',
                'message': '거래 유형을 파싱할 수 없습니다',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            print(f"거래 실행 중 오류 발생: {str(e)}")
            print(traceback.format_exc())
            return {
                'status': 'ERROR',
                'message': str(e),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

    def _parse_decision(self, decision_data: dict) -> str:
        try:
            if isinstance(decision_data, dict):
                decision = decision_data.get('decision', '').upper()
                if decision in ['BUY', 'SELL', 'HOLD']:
                    return decision
            return 'HOLD'
        except Exception as e:
            print(f"결정 파싱 중 오류: {str(e)}")
            return 'HOLD'

    def _parse_investment_ratio(self, decision_data: dict) -> float:
        try:
            if isinstance(decision_data, dict):
                percentage = float(decision_data.get('percentage', 50))
                return min(max(percentage / 100, 0.0), 1.0)
            return 0.5
        except Exception as e:
            print(f"투자 비중 파싱 중 오류: {str(e)}")
            return 0.5

    def _place_buy_order(self, investment_amount: Decimal, price: Decimal) -> Dict:
        try:
            quantity = (investment_amount / price).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            
            print(f"투자 계산 정보:")
            print(f"- 투자금액: {float(investment_amount):,.0f}원")
            print(f"- 현재가: {float(price):,.0f}원")
            print(f"- 계산된 수량: {float(quantity):.8f} {self.symbol}")
            
            min_trade_amount = self.get_min_trade_amount()
            if quantity < min_trade_amount:
                return {
                    'status': 'ERROR',
                    'type': 'BUY_FAIL',
                    'message': f'주문 수량({float(quantity):.8f})이 최소 거래량({float(min_trade_amount)})보다 작습니다',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

            params = {
                'order_currency': self.symbol,
                'payment_currency': 'KRW',
                'units': str(quantity),
                'price': str(price),
                'type': 'bid'
            }

            response = self._send_request("/trade/place", params)
            
            if response['status'] != '0000':
                raise Exception(f"매수 주문 실패: {response.get('message')}")

            return {
                'status': 'SUCCESS',
                'type': 'BUY',
                'order_id': response['order_id'],
                'quantity': float(quantity),
                'price': float(price),
                'total_amount': float(quantity * price),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            print(f"매수 주문 실행 중 오류: {str(e)}")
            return {
                'status': 'ERROR',
                'type': 'BUY_FAIL',
                'message': str(e),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

    def _place_sell_order(self, quantity: Decimal, price: Decimal) -> Dict:
        try:
            min_trade_amount = self.get_min_trade_amount()
            if quantity < min_trade_amount:
                return {
                    'status': 'ERROR',
                    'type': 'SELL_FAIL',
                    'message': f'주문 수량({float(quantity):.8f})이 최소 거래량({float(min_trade_amount)})보다 작습니다',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

            params = {
                'order_currency': self.symbol,
                'payment_currency': 'KRW',
                'units': str(quantity),
                'price': str(price),
                'type': 'ask'
            }

            response = self._send_request("/trade/place", params)
            
            if response['status'] != '0000':
                raise Exception(f"매도 주문 실패: {response.get('message')}")

            return {
                'status': 'SUCCESS',
                'type': 'SELL',
                'order_id': response['order_id'],
                'quantity': float(quantity),
                'price': float(price),
                'total_amount': float(quantity * price),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            print(f"매도 주문 실행 중 오류: {str(e)}")
            return {
                'status': 'ERROR',
                'type': 'SELL_FAIL',
                'message': str(e),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

    def _get_current_price(self) -> float:
        try:
            url = f"{self.api_url}/public/ticker/{self.symbol}_KRW"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '0000':
                return float(data['data']['closing_price'])
            return 0
            
        except Exception as e:
            print(f"현재가 조회 중 오류 발생: {str(e)}")
            return 0

    def _convert_market_format(self, market: str, to_order: bool = False) -> str:
        """마켓 포맷 변환
        DOGE_KRW <-> KRW-DOGE
        """
        if to_order:
            if '-' in market:
                quote, base = market.split('-')
                return f"{base}_{quote}"
        else:
            if '_' in market:
                base, quote = market.split('_')
                return f"{quote}-{base}"
        return market

    def get_orders(self, market: str, state: str = 'wait', uuids: list = None) -> list:
        """미체결 주문 조회"""
        try:
            query_market = self._convert_market_format(market=market, to_order=False)
            params = {
                'market': query_market,
                'state': state,
                'limit': 100,
                'page': 1,
                'order_by': 'desc'
            }
            
            query = urllib.parse.urlencode(params)
            
            if uuids:
                uuid_query = '&'.join([f'uuids[]={uuid}' for uuid in uuids])
                query = f"{query}&{uuid_query}"
            
            hash = hashlib.sha512()
            hash.update(query.encode())
            query_hash = hash.hexdigest()
            
            payload = {
                'access_key': self.api_key_v2,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000),
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512'
            }
            
            jwt_token = jwt.encode(payload, self.api_secret_v2, algorithm='HS256')
            headers = {
                'Authorization': f'Bearer {jwt_token}'
            }
            
            response = requests.get(
                f"{self.api_url}/v1/orders?{query}",
                headers=headers
            )
            
            if response.status_code != 200:
                #print(f"API 응답: {response.text}")
                return []
                
            return response.json()
            
        except Exception as e:
            print(f"주문 조회 중 오류 발생: {str(e)}")
            return []

    def check_and_cancel_old_orders(self, market: Optional[str] = None) -> None:
        """10분 이상 경과된 미체결 주문 취소"""
        try:
            if market is None:
                market = f"{self.symbol}_KRW"
                
            orders = self.get_orders(market=market, state='wait')
            current_time = datetime.now()
            
            for order in orders:
                try:
                    # ISO 8601 형식의 시간을 파싱
                    created_at = order['created_at']
                    if 'T' in created_at:  # ISO 8601 형식 확인
                        # 타임존 제거 및 포맷 변환
                        order_time = datetime.fromisoformat(created_at.split('+')[0])
                    else:
                        order_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    
                    elapsed_time = current_time - order_time
                    
                    if elapsed_time.total_seconds() > 600:
                        print(f"10분 경과 미체결 주문 취소 - Order ID: {order['uuid']}")
                        cancel_result = self.cancel_order(order['uuid'])
                        
                        if cancel_result.get('status') == 'ERROR':
                            print(f"주문 취소 실패: {cancel_result.get('message')}")
                        else:
                            print("주문이 성공적으로 취소되었습니다.")
                            
                except Exception as e:
                    print(f"개별 주문 처리 중 오류: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"미체결 주문 확인/취소 중 오류: {str(e)}")

    def _create_jwt_token(self) -> str:
        """JWT 토큰 생성"""
        payload = {
            'access_key': self.api_key_v2,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000)
        }
        
        jwt_token = jwt.encode(payload, self.api_secret_v2, algorithm='HS256')
        return f'Bearer {jwt_token}'
    
    def cancel_order(self, uuid_str: str, market: Optional[str] = None) -> dict:
        """주문 취소"""
        try:
            market = f"{self.symbol}_KRW"
                
            params = {
                'uuid': uuid_str,
                'market': self._convert_market_format(market=market, to_order=True)
            }
            query = urllib.parse.urlencode(params).encode()
            
            hash = hashlib.sha512()
            hash.update(query)
            query_hash = hash.hexdigest()
            
            nonce = uuid.uuid4()  # uuid를 직접 생성
            
            payload = {
                'access_key': self.api_key_v2,
                'nonce': str(nonce),
                'timestamp': round(time.time() * 1000),
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512'
            }
            
            jwt_token = jwt.encode(payload, self.api_secret_v2)
            headers = {
                'Authorization': f'Bearer {jwt_token}'
            }
            
            response = requests.delete(
                f"{self.api_url}/v1/order",
                params=params,
                headers=headers
            )
            
            if response.status_code != 200:
                #print(f"API 응답: {response.text}")
                return {'status': 'ERROR', 'message': response.text}
                
            return response.json()
            
        except Exception as e:
            error_message = str(e)
            print(f"주문 취소 중 오류 발생: {error_message}")
            return {
                'status': 'ERROR',
                'type': 'CANCEL_FAIL', 
                'message': error_message,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }