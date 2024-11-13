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

class BithumbTradeExecutor:
    def __init__(self):
        """빗썸 API 거래 실행기 초기화"""
        load_dotenv()
        self.api_url = "https://api.bithumb.com"
        self.api_key = os.getenv('BITHUMB_API_KEY')
        self.api_secret = os.getenv('BITHUMB_API_SECRET').encode('utf-8')
        self.symbol = "BTC"
        self.db_path = "crypto_analysis.db"

        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in environment variables")
        
        self.min_trade_amounts = {
            'BTC': Decimal('0.0001'),
            'ETH': Decimal('0.001'),
            'XRP': Decimal('1'),
        }

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
            return {
                'krw_available': Decimal(str(data.get('available_krw', '0'))),
                'btc_available': Decimal(str(data.get('available_btc', '0'))),
                'krw_total': Decimal(str(data.get('total_krw', '0'))),
                'btc_total': Decimal(str(data.get('total_btc', '0')))
            }
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {str(e)}")
            return {
                'krw_available': Decimal('0'),
                'btc_available': Decimal('0'),
                'krw_total': Decimal('0'),
                'btc_total': Decimal('0')
            }

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
            
            # print(f"Request URL: {url}")
            # print(f"Request Headers: {headers}")
            # print(f"Request Params: {params}")
            
            response = requests.post(url, headers=headers, data=params)
            # print(f"Response Status: {response.status_code}")
            # print(f"Response Content: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API 요청 실패: {str(e)}")

    def execute_trade(self, decision: Dict[str, Any], max_investment: float, current_price: float) -> Dict:
        """거래 결정 실행"""
        try:
            # 1. 결정 텍스트 파싱
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

            # 3. 잔고 확인
            balance = self.get_balance()
            available_krw = Decimal(str(balance['krw_available']))
            available_btc = Decimal(str(balance['btc_available']))

            # 4. 투자 비중 계산 및 로깅
            investment_ratio = self._parse_investment_ratio(decision_text)
            max_investment_decimal = Decimal(str(max_investment))
            investment_amount = max_investment_decimal * Decimal(str(investment_ratio))
            
            print(f"\n=== 투자 계산 상세 ===")
            print(f"최대 투자금액: {float(max_investment_decimal):,.0f}원")
            print(f"투자 비중: {float(investment_ratio)*100:.1f}%")
            print(f"계산된 투자금액: {float(investment_amount):,.0f}원")
            print(f"사용 가능한 KRW: {float(available_krw):,.0f}원")

            # 5. 매수/매도 결정 및 실행
            if trade_type == 'BUY':
                # 매수 가능 금액 확인
                if available_krw < Decimal('10000'):  # 최소 주문 금액
                    return {
                        'status': 'ERROR',
                        'type': 'BUY_FAIL',
                        'message': f'잔액 부족 (현재 잔액: {float(available_krw):,.0f}원)',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                # 실제 매수 금액 조정
                actual_investment = min(investment_amount, available_krw)
                print(f"실제 투자금액: {float(actual_investment):,.0f}원")
                return self._place_buy_order(actual_investment, Decimal(str(current_price)))

            elif trade_type == 'SELL':
                # 매도 가능 수량 확인
                if available_btc < self.min_trade_amounts['BTC']:
                    return {
                        'status': 'ERROR',
                        'type': 'SELL_FAIL',
                        'message': f'BTC 잔액 부족 (현재 보유량: {float(available_btc):.8f} BTC)',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                # 매도 수량 계산 (전체 보유량의 investment_ratio 만큼)
                sell_quantity = available_btc * Decimal(str(investment_ratio))
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

    def _parse_decision(self, decision_text: str) -> str:
        """거래 결정 텍스트 파싱"""
        try:
            # 결정 텍스트를 줄 단위로 분리하고 소문자로 변환
            lines = decision_text.lower().split('\n')
            for line in lines:
                # "투자결정" 또는 "결정" 키워드가 있는 줄 찾기
                if '투자결정' in line or '결정' in line:
                    # 매수/매도/관망 결정 파싱
                    if '매수' in line:
                        return 'BUY'
                    elif '매도' in line or '매각' in line:  # '매각'도 포함
                        return 'SELL'
                    elif '관망' in line:
                        return 'HOLD'
                    
                    # 디버깅을 위한 출력
                    print(f"파싱된 결정 라인: {line}")
            
            # 디버깅을 위한 전체 텍스트 출력
            print(f"전체 결정 텍스트:\n{decision_text}")
            
            # 결정을 찾지 못한 경우
            return 'HOLD'
        except Exception as e:
            print(f"결정 파싱 중 오류: {str(e)}")
            return 'HOLD'

    def _parse_investment_ratio(self, decision_text: str) -> float:
        """투자 비중 파싱"""
        try:
            # 투자 비중/비율 관련 키워드 찾기
            keywords = ['투자 비중', '투자비중']
            for keyword in keywords:
                if keyword in decision_text:
                    # 해당 라인 추출
                    lines = decision_text.split('\n')
                    ratio_line = next((line for line in lines if keyword in line), None)
                    
                    if ratio_line:
                        # 숫자 추출 (백분율)
                        import re
                        matches = re.findall(r'(\d+)%', ratio_line)
                        if matches:
                            ratio = float(matches[0]) / 100
                            return min(max(ratio, 0.0), 1.0)
            
            # 기본값 반환
            return 0.5
            
        except Exception as e:
            print(f"투자 비중 파싱 중 오류: {str(e)}")
            return 0.5

    def _place_buy_order(self, investment_amount: Decimal, price: Decimal) -> Dict:
        """매수 주문 실행"""
        try:
            # 1. 수량 계산 - 투자금액을 현재가로 나누어 구매 가능한 수량 계산
            quantity = (investment_amount / price).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            
            print(f"투자 계산 정보:")
            print(f"- 투자금액: {float(investment_amount):,.0f}원")
            print(f"- 현재가: {float(price):,.0f}원")
            print(f"- 계산된 수량: {float(quantity):.8f} BTC")
            
            # 2. 최소 거래량 확인
            if quantity < self.min_trade_amounts['BTC']:
                return {
                    'status': 'ERROR',
                    'type': 'BUY_FAIL',
                    'message': f'주문 수량({float(quantity):.8f})이 최소 거래량({self.min_trade_amounts["BTC"]})보다 작습니다',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

            # 3. 주문 파라미터 설정
            params = {
                'order_currency': self.symbol,
                'payment_currency': 'KRW',
                'units': str(quantity),
                'price': str(price),
                'type': 'bid'
            }

            # 4. API 요청 실행
            response = self._send_request("/trade/place", params)
            
            # 5. 응답 처리
            if response['status'] != '0000':
                raise Exception(f"매수 주문 실패: {response.get('message')}")

            # 6. 성공 결과 반환
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
        """매도 주문 실행"""
        try:
            # 1. 최소 거래량 확인
            if quantity < self.min_trade_amounts['BTC']:
                return {
                    'status': 'ERROR',
                    'type': 'SELL_FAIL',
                    'message': f'주문 수량이 최소 거래량({self.min_trade_amounts["BTC"]})보다 작습니다',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

            # 2. 주문 파라미터 설정
            params = {
                'order_currency': self.symbol,
                'payment_currency': 'KRW',
                'units': str(quantity),
                'price': str(price),
                'type': 'ask'
            }

            # 3. API 요청 실행
            response = self._send_request("/trade/place", params)
            
            # 4. 응답 처리
            if response['status'] != '0000':
                raise Exception(f"매도 주문 실패: {response.get('message')}")

            # 5. 성공 결과 반환
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
        
    def get_current_position(self) -> Dict[str, Any]:
        """현재 매수 포지션의 평균 매수가와 수량을 조회하고 잔고와 비교"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 모든 BUY 거래 조회
                query = """
                SELECT quantity, price, total_amount
                FROM trade_executions
                WHERE trade_type = 'BUY'
                ORDER BY timestamp DESC
                """
                
                cursor.execute(query)
                trades = cursor.fetchall()
                
                if not trades:
                    return {
                        'avg_price': 0,
                        'total_quantity': 0,
                        'total_investment': 0,
                        'investment_ratio': 0
                    }
                
                # 평균 매수가 및 총 수량 계산
                total_quantity = sum(Decimal(str(trade[0])) for trade in trades)
                total_investment = sum(Decimal(str(trade[2])) for trade in trades)
                
                if total_quantity > 0:
                    avg_price = total_investment / total_quantity
                else:
                    avg_price = Decimal('0')
                
                # 현재 잔고 조회
                balance = self.get_balance()
                krw_total = Decimal(str(balance['krw_total']))
                
                # 투자 비율 계산 (총 투자금액 / 총 자산)
                total_assets = krw_total + total_investment
                investment_ratio = (total_investment / total_assets * 100) if total_assets > 0 else Decimal('0')
                
                return {
                    'avg_price': float(avg_price),
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

    def _get_current_price(self) -> float:
        """현재 BTC 가격 조회"""
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