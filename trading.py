import os
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN
import pyupbit
from dotenv import load_dotenv
import time
from datetime import datetime
import json

class UpbitTradeExecutor:
    def __init__(self):
        """업비트 API 거래 실행기 초기화"""
        load_dotenv()
        self.access_key = os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = os.getenv('UPBIT_SECRET_KEY')
        self.symbol = os.getenv('COIN', 'BTC')
        self.market = f"KRW-{self.symbol}"
        self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)

        if not self.access_key or not self.secret_key:
            raise ValueError("API credentials not found in environment variables")
        
        self.min_trade_amounts = {
            'BTC': Decimal('0.0001'),
            'XRP': Decimal('1'),
            'DOGE': Decimal('1'),
        }
        self.default_min_trade_amount = Decimal('1')
    
    def get_min_trade_amount(self) -> Decimal:
        """현재 설정된 코인의 최소 거래량 반환"""
        return self.min_trade_amounts.get(self.symbol, self.default_min_trade_amount)

    def get_balance(self) -> dict:
        """계좌 잔고 조회"""
        try:
            krw_balance = self.upbit.get_balance("KRW")
            coin_balance = self.upbit.get_balance(self.market)
            
            symbol = self.symbol.lower()
            result = {
                'krw_available': Decimal(str(krw_balance)),
                f'{symbol}_available': Decimal(str(coin_balance)),
                'krw_total': Decimal(str(krw_balance)),
                f'{symbol}_total': Decimal(str(coin_balance))
            }
            return result
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {str(e)}")
            return {
                'krw_available': Decimal('0'),
                f'{self.symbol.lower()}_available': Decimal('0'),
                'krw_total': Decimal('0'),
                f'{self.symbol.lower()}_total': Decimal('0')
            }

    def get_current_position(self) -> Dict[str, Any]:
        """현재 포지션 정보 조회"""
        try:
            krw_balance = self.upbit.get_balance("KRW")
            coin_balance = self.upbit.get_balance(self.market)
            avg_buy_price = self.upbit.get_avg_buy_price(self.market)
            
            total_investment = float(coin_balance * avg_buy_price)
            total_assets = float(krw_balance + total_investment)
            investment_ratio = (total_investment / total_assets * 100) if total_assets > 0 else 0
            
            return {
                'avg_price': float(avg_buy_price),
                'total_quantity': float(coin_balance),
                'total_investment': total_investment,
                'investment_ratio': investment_ratio
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
            if isinstance(decision, dict):
                print("\n=== 받은 결정 데이터 ===")
                print(json.dumps(decision, indent=2, ensure_ascii=False))
                
                actual_decision = decision.get('decision', {}) if isinstance(decision.get('decision'), dict) else decision
                
                decision_text = actual_decision.get('decision', 'HOLD')
                trade_type = decision_text.upper()
                
                # 타임스탬프 생성
                timestamp = datetime.now()
                
                # HOLD 또는 잘못된 거래 타입 처리
                if trade_type not in ['BUY', 'SELL', 'HOLD']:
                    return {
                        'status': 'ERROR',
                        'type': 'INVALID_TYPE',
                        'message': '잘못된 거래 타입',
                        'quantity': 0,
                        'price': current_price,
                        'total_amount': 0,
                        'order_id': f"ERROR_{timestamp.strftime('%Y%m%d%H%M%S')}",
                        'timestamp': timestamp.isoformat()
                    }
                    
                if trade_type == 'HOLD':
                    return {
                        'status': 'SUCCESS',
                        'type': 'HOLD',
                        'message': '관망 결정으로 인한 거래 건너뛰기',
                        'quantity': 0,
                        'price': current_price,
                        'total_amount': 0,
                        'order_id': f"HOLD_{timestamp.strftime('%Y%m%d%H%M%S')}",
                        'timestamp': timestamp.isoformat()
                    }

                balance = self.get_balance()
                symbol = self.symbol.lower()
                available_krw = Decimal(str(balance['krw_available']))
                available_coin = Decimal(str(balance[f'{symbol}_available']))

                investment_ratio = Decimal(str(actual_decision.get('percentage', 0))) / Decimal('100')
                max_investment_decimal = Decimal(str(max_investment))
                investment_amount = max_investment_decimal * investment_ratio

                print(f"\n=== 투자 계산 상세 ===")
                print(f"최대 투자금액: {float(max_investment_decimal):,.0f}원")
                print(f"투자 비중: {float(investment_ratio)*100:.1f}%")
                print(f"계산된 투자금액: {float(investment_amount):,.0f}원")
                print(f"사용 가능한 KRW: {float(available_krw):,.0f}원")

                if trade_type == 'BUY':
                    if available_krw < Decimal('5000'):
                        return {
                            'status': 'ERROR',
                            'type': 'BUY_FAIL',
                            'message': f'잔액 부족 (현재 잔액: {float(available_krw):,.0f}원)',
                            'quantity': 0,
                            'price': current_price,
                            'total_amount': 0,
                            'order_id': f"BUY_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                            'timestamp': timestamp.isoformat()
                        }
                    
                    actual_investment = min(investment_amount, available_krw)
                    return self._place_buy_order(actual_investment)

                elif trade_type == 'SELL':
                    if available_coin < self.get_min_trade_amount():
                        return {
                            'status': 'ERROR',
                            'type': 'SELL_FAIL',
                            'message': f'{self.symbol} 잔액 부족 (현재 보유량: {float(available_coin):.8f} {self.symbol})',
                            'quantity': 0,
                            'price': current_price,
                            'total_amount': 0,
                            'order_id': f"SELL_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                            'timestamp': timestamp.isoformat()
                        }
                    
                    if current_price <= 0:
                        return {
                            'status': 'ERROR',
                            'type': 'SELL_FAIL',
                            'message': '현재가가 유효하지 않습니다',
                            'quantity': 0,
                            'price': current_price,
                            'total_amount': 0,
                            'order_id': f"SELL_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                            'timestamp': timestamp.isoformat()
                        }
                    
                    target_sell_amount = investment_amount
                    sell_quantity = target_sell_amount / Decimal(str(current_price))
                    sell_quantity = min(sell_quantity, available_coin)
                    
                    if sell_quantity < self.get_min_trade_amount():
                        if available_coin >= self.get_min_trade_amount():
                            sell_quantity = self.get_min_trade_amount()
                        else:
                            return {
                                'status': 'ERROR',
                                'type': 'SELL_FAIL',
                                'message': f'최소 거래량 미달 (계산된 수량: {float(sell_quantity):.8f} {self.symbol})',
                                'quantity': 0,
                                'price': current_price,
                                'total_amount': 0,
                                'order_id': f"SELL_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                                'timestamp': timestamp.isoformat()
                            }
                    
                    print(f"매도 주문 실행: {float(sell_quantity):.8f} {self.symbol}")
                    return self._place_sell_order(sell_quantity)

        except Exception as e:
            timestamp = datetime.now()
            return {
                'status': 'ERROR',
                'type': 'EXECUTION_ERROR',
                'message': str(e),
                'quantity': 0,
                'price': current_price if current_price > 0 else 0,
                'total_amount': 0,
                'order_id': f"ERROR_{timestamp.strftime('%Y%m%d%H%M%S')}",
                'timestamp': timestamp.isoformat()
            }
        
    def _parse_decision(self, decision_data: dict) -> str:
        """거래 결정 파싱"""
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
        """투자 비율 파싱"""
        try:
            if isinstance(decision_data, dict):
                percentage = float(decision_data.get('percentage', 0))  # 기본값을 0으로 변경
                return min(max(percentage / 100, 0.0), 1.0)  # 0~1 사이로 정규화
            return 0.0  # 잘못된 입력시 0% 반환
        except Exception as e:
            print(f"투자 비중 파싱 중 오류: {str(e)}")
            return 0.0  # 오류 발생시 0% 반환

    def _place_buy_order(self, investment_amount: Decimal) -> Dict:
        """매수 주문 실행"""
        timestamp = datetime.now()
        try:
            print(f"매수 주문 실행: {float(investment_amount):,.0f}원")
            result = self.upbit.buy_market_order(self.market, investment_amount)
            
            if result is None or 'error' in result:
                error_message = result.get('error', {}).get('message', '알 수 없는 오류') if result else '주문 실패'
                return {
                    'status': 'ERROR',
                    'type': 'BUY_FAIL',
                    'message': error_message,
                    'quantity': 0,
                    'price': 0,
                    'total_amount': 0,
                    'order_id': f"BUY_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                    'timestamp': timestamp.isoformat()
                }
            
            price = float(result.get('price', 0))
            quantity = float(result.get('volume', 0))
            total_amount = price * quantity
            
            return {
                'status': 'SUCCESS',
                'type': 'BUY',
                'order_id': result['uuid'],
                'quantity': quantity,
                'price': price,
                'total_amount': total_amount,
                'timestamp': timestamp.isoformat()
            }

        except Exception as e:
            return {
                'status': 'ERROR',
                'type': 'BUY_FAIL',
                'message': str(e),
                'quantity': 0,
                'price': 0,
                'total_amount': 0,
                'order_id': f"BUY_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                'timestamp': timestamp.isoformat()
            }

    def _place_sell_order(self, quantity: Decimal) -> Dict:
        """매도 주문 실행"""
        timestamp = datetime.now()
        try:
            print(f"매도 주문 실행: {float(quantity):.8f} {self.symbol}")
            result = self.upbit.sell_market_order(self.market, quantity)
            
            if result is None or 'error' in result:
                error_message = result.get('error', {}).get('message', '알 수 없는 오류') if result else '주문 실패'
                return {
                    'status': 'ERROR',
                    'type': 'SELL_FAIL',
                    'message': error_message,
                    'quantity': 0,
                    'price': 0,
                    'total_amount': 0,
                    'order_id': f"SELL_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                    'timestamp': timestamp.isoformat()
                }
            
            price = float(result.get('price', 0))
            executed_quantity = float(result.get('volume', 0))
            total_amount = price * executed_quantity
            
            return {
                'status': 'SUCCESS',
                'type': 'SELL',
                'order_id': result['uuid'],
                'quantity': executed_quantity,
                'price': price,
                'total_amount': total_amount,
                'timestamp': timestamp.isoformat()
            }

        except Exception as e:
            return {
                'status': 'ERROR',
                'type': 'SELL_FAIL',
                'message': str(e),
                'quantity': 0,
                'price': 0,
                'total_amount': 0,
                'order_id': f"SELL_FAIL_{timestamp.strftime('%Y%m%d%H%M%S')}",
                'timestamp': timestamp.isoformat()
            }

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
            orders = self.upbit.get_order(query_market, state=state)
            return orders or []
            
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
                    created_at = order['created_at']
                    if 'T' in created_at:
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
    
    def cancel_order(self, uuid_str: str, market: Optional[str] = None) -> dict:
        """주문 취소"""
        try:
            result = self.upbit.cancel_order(uuid_str)
            
            if result is None:
                return {
                    'status': 'ERROR',
                    'type': 'CANCEL_FAIL', 
                    'message': '주문 취소 실패',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
            return {
                'status': 'SUCCESS',
                'type': 'CANCEL',
                'order_id': uuid_str,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            error_message = str(e)
            print(f"주문 취소 중 오류 발생: {error_message}")
            return {
                'status': 'ERROR',
                'type': 'CANCEL_FAIL', 
                'message': error_message,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }