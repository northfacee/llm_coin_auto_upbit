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

class BithumbTradeExecutor:
    def __init__(self):
        """빗썸 API 거래 실행기 초기화"""
        load_dotenv()
        self.api_url = "https://api.bithumb.com"
        self.api_key = os.getenv('BITHUMB_API_KEY')
        self.api_secret = os.getenv('BITHUMB_API_SECRET').encode('utf-8')
        self.symbol = "BTC"
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in environment variables")
        
        self.min_trade_amounts = {
            'BTC': Decimal('0.0001'),
            'ETH': Decimal('0.001'),
            'XRP': Decimal('1'),
        }

    def _create_signature(self, endpoint: str, params: dict) -> dict:
        """API 요청 서명 및 헤더 생성"""
        nonce = str(int(time.time() * 1000))
        params['nonce'] = nonce
        
        # 정렬된 파라미터 문자열 생성
        query_string = urllib.parse.urlencode(params) if params else ''
        
        # 서명 데이터 준비
        sign_data = endpoint + ";" + query_string + ";" + nonce
        
        # HMAC-SHA512 서명 생성
        signature = hmac.new(
            self.api_secret,
            sign_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        # Base64 인코딩
        encoded_signature = base64.b64encode(signature.encode('utf-8')).decode('utf-8')
        
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'api-client-type': '2',
            'Api-Key': self.api_key,
            'Api-Nonce': nonce,
            'Api-Sign': encoded_signature
        }
        
        return headers

    def _send_request(self, endpoint: str, params: dict) -> dict:
        """API 요청 전송"""
        try:
            headers = self._create_signature(endpoint, params)
            url = f"{self.api_url}{endpoint}"
            
            print(f"Request URL: {url}")
            print(f"Request Headers: {headers}")
            print(f"Request Params: {params}")
            
            response = requests.post(url, headers=headers, data=params)
            print(f"Response Status: {response.status_code}")
            print(f"Response Content: {response.text}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API 요청 실패: {str(e)}")

    def get_balance(self) -> dict:
        """BTC 잔고 조회"""
        endpoint = "/info/balance"
        params = {
            'currency': 'BTC'
        }
        
        try:
            response = self._send_request(endpoint, params)
            
            if response['status'] == '5100':
                raise Exception(f"인증 실패: {response.get('message')}")
            
            if response.get('status') != '0000':
                raise Exception(f"잔고 조회 실패: {response.get('message')}")
            
            return {
                'krw_available': Decimal(response['data']['available_krw']),
                'available': Decimal(response['data']['available_btc']),
                'current_price': Decimal(response['data']['xcoin_last_btc'])
            }
            
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {str(e)}")
            raise e

    def execute_trade(self, decision: Dict[str, Any], max_investment: float, current_price: float) -> Dict:
        """거래 결정 실행"""
        try:
            # 결정 파싱
            trade_type = self._parse_decision(decision['decision'])
            if not trade_type:
                return {'status': 'SKIP', 'message': '관망 결정으로 인한 거래 건너뛰기'}
            
            # 잔고 확인
            balance = self.get_balance()
            
            # 투자 금액 계산
            investment_ratio = self._parse_investment_ratio(decision['decision'])
            investment_amount = Decimal(str(min(max_investment * investment_ratio, float(balance['krw_available']))))
            
            if trade_type == 'BUY':
                return self._place_buy_order(investment_amount, Decimal(str(current_price)))
            else:  # SELL
                return self._place_sell_order(balance['available'], Decimal(str(current_price)))
                
        except Exception as e:
            print(f"거래 실행 중 오류 발생: {str(e)}")
            return {'status': 'ERROR', 'message': str(e)}

    def _parse_decision(self, decision_text: str) -> Optional[Literal['BUY', 'SELL']]:
        """결정 텍스트 파싱"""
        decision_text = decision_text.lower()
        if '매수' in decision_text:
            return 'BUY'
        elif '매도' in decision_text:
            return 'SELL'
        return None

    def _parse_investment_ratio(self, decision_text: str) -> float:
        """투자 비중 파싱"""
        try:
            import re
            match = re.search(r'투자 비중:\s*(\d+)%', decision_text)
            if match:
                return float(match.group(1)) / 100
            return 0.5  # 기본값
        except:
            return 0.5

    def _calculate_quantity(self, price: Decimal, investment_amount: Decimal) -> Decimal:
        """주문 수량 계산"""
        quantity = investment_amount / price
        min_amount = self.min_trade_amounts.get(self.symbol, Decimal('0.0001'))
        return quantity.quantize(min_amount, rounding=ROUND_DOWN)

    def _place_buy_order(self, investment_amount: Decimal, price: Decimal) -> Dict:
        """매수 주문 실행"""
        quantity = self._calculate_quantity(price, investment_amount)
        
        endpoint = "/trade/place"
        params = {
            'order_currency': self.symbol,
            'payment_currency': 'KRW',
            'units': str(quantity),
            'price': str(price),
            'type': 'bid'
        }
        
        response = self._send_request(endpoint, params)
        if response['status'] != '0000':
            raise Exception(f"매수 주문 실패: {response.get('message')}")
        
        return {
            'status': 'SUCCESS',
            'type': 'BUY',
            'order_id': response['order_id'],
            'quantity': float(quantity),
            'price': float(price),
            'total_amount': float(quantity * price)
        }

    def _place_sell_order(self, quantity: Decimal, price: Decimal) -> Dict:
        """매도 주문 실행"""
        endpoint = "/trade/place"
        params = {
            'order_currency': self.symbol,
            'payment_currency': 'KRW',
            'units': str(quantity),
            'price': str(price),
            'type': 'ask'
        }
        
        response = self._send_request(endpoint, params)
        if response['status'] != '0000':
            raise Exception(f"매도 주문 실패: {response.get('message')}")
        
        return {
            'status': 'SUCCESS',
            'type': 'SELL',
            'order_id': response['order_id'],
            'quantity': float(quantity),
            'price': float(price),
            'total_amount': float(quantity * price)
        }