from typing import TypedDict, Annotated, Sequence
from datetime import datetime, timedelta
import json
import os
from langchain_core.messages import BaseMessage, HumanMessage, FunctionMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt import ToolExecutor
from langchain_core.tools import tool
from langsmith import Client
import langsmith
from dotenv import load_dotenv
from database_manager import DatabaseManager
from price_collector import BithumbTrader
from news_collector import NaverNewsCollector
from trading import BithumbTradeExecutor
import time
import traceback  # traceback 모듈 추가
import requests

# 환경 변수 및 LangSmith 설정
load_dotenv()
try:
    INVESTMENT = float(os.getenv('INVESTMENT'))
except TypeError:
    raise ValueError("INVESTMENT 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

SYMBOL = os.getenv('COIN')
if not SYMBOL:
    raise ValueError("COIN 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = "bitcoin_agent"


# 상태 타입 정의
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next_step: str
    results: dict
    market_data: dict
    symbol: str

# 글로벌 인스턴스 초기화
db_manager = DatabaseManager()
trader = BithumbTrader()
trade_executor = BithumbTradeExecutor()
langsmith_client = Client()

def collect_latest_news():
    """최신 뉴스를 수집하고 저장"""
    try:
        local_news_collector = NaverNewsCollector()
        total_saved = 0
        
        for keyword in local_news_collector.search_keywords:
            news_response = local_news_collector.collect_news(keyword, display=10)
            if news_response:
                news_items = local_news_collector.process_news_data(news_response['items'])
                if local_news_collector.save_news(news_items):
                    total_saved += len(news_items)
        
        print(f"총 {total_saved}개의 새로운 뉴스 기사가 저장되었습니다.")
        
    except Exception as e:
        print(f"뉴스 수집 중 오류 발생: {e}")

def get_market_data_once(state: AgentState) -> dict:
    """시장 데이터를 안전하게 수집"""
    try:
        # 이미 market_data가 있다면 재사용
        if state.get('market_data') and isinstance(state['market_data'], dict):
            return state['market_data']
            
        if not trader.analyzer.data_queue.empty():
            market_data = trader.analyzer.data_queue.get()
        else:
            market_data = trader.collect_market_data()
        
        if not isinstance(market_data, dict):
            print("Warning: market_data is not a dictionary")
            market_data = {'error': 'Invalid data format'}
            
        if 'current_price' in market_data:
            if not isinstance(market_data['current_price'], dict):
                current_price_value = market_data['current_price']
                market_data['current_price'] = {
                    'closing_price': float(current_price_value),
                    'opening_price': float(current_price_value),
                    'max_price': float(current_price_value),
                    'min_price': float(current_price_value)
                }
        
        state['market_data'] = market_data
        return market_data
        
    except Exception as e:
        print(f"Error in get_market_data_once: {str(e)}")
        return {
            'timestamp': datetime.now().isoformat(),
            'market': f'{SYMBOL}_KRW',
            'current_price': {'closing_price': 0}
        }

@tool
def get_recent_news(dummy: str = "") -> str:
    """최근 24시간 동안의 암호화폐 관련 뉴스를 가져옵니다."""
    with langsmith.trace(
        name="get_recent_news",
        project_name="bitcoin_agent",
        tags=["news", "data-collection"]
    ):
        # 최신 뉴스 수집을 먼저 실행
        collect_latest_news()
        
        news_df = db_manager.get_recent_news_limit()
        #print(news_df)
        if news_df.empty:
            return "최근 뉴스가 없습니다."
        
        news_list = []
        for _, row in news_df.iterrows():
            news_list.append({
                'title': row['title'],
                'description': row['description'],
                'pub_date': row['pub_date'].isoformat() if hasattr(row['pub_date'], 'isoformat') else str(row['pub_date'])
            })
        return json.dumps(news_list, ensure_ascii=False)

def news_analysis_agent(state: AgentState) -> AgentState:
    """뉴스만을 분석하여 투자 제안을 하는 에이전트"""
    with langsmith.trace(
        name="news_analysis_agent",
        project_name="bitcoin_agent",
        tags=["news", "analysis"]
    ):
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        news_data = get_recent_news.invoke("")
        
        prompt = f"""You are a cryptocurrency market news analysis expert.
                    Focus on analyzing news that could have immediate impact on short-term price movements.

                    Analysis Priorities:
                    1. Regulation/Policy Related News (Impact Weight: 35%)
                    2. Institutional Investor Trends (Impact Weight: 25%)
                    3. Technical Development/Update News (Impact Weight: 20%)
                    4. Market Sentiment Related News (Impact Weight: 20%)

                    News Data:
                    {news_data}
                    
                    Please provide detailed analysis in the following format:
                    1. Investment Decision: (Buy/Sell/Hold)
                    2. Investment Weight: (0-100%)
                    3. Decision Rationale:
                    - Key Influential News (by impact ranking)
                    - Expected Market Response
                    - Impact Duration Prediction
                    4. Risk Factors:
                    - Short-term Risks
                    - Counter Scenario Possibilities
                    5. Overall News Impact Score: (Very Negative/-2 ~ Very Positive/+2)
                    """
        
        response = llm.invoke(prompt)
        timestamp = datetime.now()
        
        if 'results' not in state:
            state['results'] = {}
        
        state['results']['news_analysis'] = {
            'analysis': response.content,
            'timestamp': timestamp.isoformat()
        }
        
        db_manager.save_news_analysis(
            timestamp=timestamp,
            analysis_text=response.content
        )
        
        return state

def price_analysis_agent(state: AgentState) -> AgentState:
    """기술적 지표와 시장 데이터를 분석하여 투자 제안을 하는 에이전트"""
    with langsmith.trace(
        name="price_analysis_agent",
        project_name="bitcoin_agent",
        tags=["price", "analysis"]
    ):
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        market_data = get_market_data_once(state)
        
        def safe_get_nested(data, *keys, default='N/A'):
            try:
                result = data
                for key in keys:
                    if isinstance(result, dict):
                        result = result.get(key, default)
                    elif isinstance(result, (list, tuple)) and isinstance(key, int):
                        result = result[key] if 0 <= key < len(result) else default
                    else:
                        return default
                return result if result is not None else default
            except Exception as e:
                print(f"Error accessing {keys}: {str(e)}")
                return default

        def format_number(value, default='N/A'):
            if value == 'N/A':
                return value
            try:
                if isinstance(value, (int, float)):
                    return f"{value:,.2f}"
                return str(default)
            except:
                return str(default)
        
        try:
            # 모든 시간대의 분석 데이터 가져오기
            time_periods = ['1m', '3m', '5m', '10m', '15m', '30m']
            analysis_data = {}
            
            for period in time_periods:
                analysis_data[period] = safe_get_nested(market_data, 'analysis', period, default={})
                
            current_price = safe_get_nested(market_data, 'current_price', 'closing_price', default=0)
            
            # 각 시간대별 분석 데이터 구성
            analysis_by_period = {}
            for period in time_periods:
                period_data = analysis_data[period]
                
                # 이동평균선 데이터 처리
                moving_averages = period_data.get('moving_averages', {})
                
                analysis_by_period[period] = {
                    'MA': {
                        'MA5': format_number(safe_get_nested(moving_averages, 5)),
                        'MA10': format_number(safe_get_nested(moving_averages, 10)),
                        'MA20': format_number(safe_get_nested(moving_averages, 20)),
                        'MA50': format_number(safe_get_nested(moving_averages, 50)),
                        'MA200': format_number(safe_get_nested(moving_averages, 200))
                    },
                    'RSI': format_number(safe_get_nested(period_data, 'rsi')),
                    'Stochastic': {
                        'K': format_number(safe_get_nested(period_data, 'stochastic', 0)),
                        'D': format_number(safe_get_nested(period_data, 'stochastic', 1))
                    },
                    'BB': {
                        'Upper': format_number(safe_get_nested(period_data, 'bollinger_bands', 0)),
                        'Middle': format_number(safe_get_nested(period_data, 'bollinger_bands', 1)),
                        'Lower': format_number(safe_get_nested(period_data, 'bollinger_bands', 2))
                    },
                    'EMA': {
                        'EMA12': format_number(safe_get_nested(period_data, 'ema', '12')),
                        'EMA26': format_number(safe_get_nested(period_data, 'ema', '26'))
                    },
                    'DMI': {
                        '+DI': format_number(safe_get_nested(period_data, 'dmi', 0)),
                        '-DI': format_number(safe_get_nested(period_data, 'dmi', 1)),
                        'ADX': format_number(safe_get_nested(period_data, 'dmi', 2))
                    },
                    'ATR': format_number(safe_get_nested(period_data, 'atr')),
                    'OBV': format_number(safe_get_nested(period_data, 'obv')),
                    'VWAP': format_number(safe_get_nested(period_data, 'vwap')),
                    'MFI': format_number(safe_get_nested(period_data, 'mfi')),
                    'Williams_R': format_number(safe_get_nested(period_data, 'williams_r')),
                    'CCI': format_number(safe_get_nested(period_data, 'cci')),
                    'Change_Rate': format_number(safe_get_nested(period_data, 'change_rate'))
                }
            
            # 프롬프트 구성
            prompt = f"""You are a cryptocurrency technical analysis expert.
            Please make investment decisions based on the following data.
            
            Current Price: {format_number(current_price)} KRW
            
            === Price Change Rate by Timeframe ===
            1min: {analysis_by_period['1m']['Change_Rate']}%
            3min: {analysis_by_period['3m']['Change_Rate']}%
            5min: {analysis_by_period['5m']['Change_Rate']}%
            10min: {analysis_by_period['10m']['Change_Rate']}%
            15min: {analysis_by_period['15m']['Change_Rate']}%
            30min: {analysis_by_period['30m']['Change_Rate']}%
            """
            
            # 각 시간대별 데이터를 프롬프트에 추가
            for period in time_periods:
                
                data = analysis_by_period[period]
                prompt += f"""
                === {period} Indicators ===
                - RSI(14): {data['RSI']}
                - Stochastic K/D: {data['Stochastic']['K']}/{data['Stochastic']['D']}
                - Bollinger Bands:
                Upper: {data['BB']['Upper']}
                Middle: {data['BB']['Middle']}
                Lower: {data['BB']['Lower']}
                - Moving Averages:
                MA5: {data['MA']['MA5']}
                MA10: {data['MA']['MA10']}
                MA20: {data['MA']['MA20']}
                MA50: {data['MA']['MA50']}
                - EMA:
                EMA12: {data['EMA']['EMA12']}
                EMA26: {data['EMA']['EMA26']}
                - ATR: {data['ATR']}
                - VWAP: {data['VWAP']}
                - MFI: {data['MFI']}
                - Williams %R: {data['Williams_R']}
                - CCI: {data['CCI']}
                - Change Rate: {data['Change_Rate']}%
                """
            
            prompt += f"""

            [Market Analysis Criteria]
            1. Trend Strength Assessment
               - Moving Average Alignment
               - Trendline Support/Resistance
               - Trend Momentum Sustainability
            
            2. Short-term Reversal Signals
               - RSI, Stochastic Divergence
               - Bollinger Band Penetration
               - Volume Surge Areas
            
            3. Trade Entry Precision
               - Priority on 15min or Lower Timeframes
               - Multiple Indicator Confirmation Signals
               - Volume Profile Based Price Analysis
            
            4. Risk Management
               - Volatility-based Stop Loss
               - Expected Risk-Reward Ratio
               - Position Entry Timing
            
            Please provide analysis results in the following format:

            1. Investment Assessment
               - Decision: (Buy/Sell/Hold)
               - Investment Weight: (0-100%)
               - Target/Stop Loss Prices
               - Expected Position Hold Time
            
            2. Key Signal Analysis
               - Short-term (1-5min): Key Turning Points/Strength
               - Medium-term (10-30min): Trend Direction/Strength
               - Volume Anomalies
               - Notable Technical Patterns
            
            3. Risk Assessment
               - Reversal Probability
               - Volatility Level
               - Volume Risk
               - Recommended Leverage Multiple
            
            4. Overall Score: (-5 ~ +5)
               Negative: Downward Potential
               Positive: Upward Potential
               Absolute Value: Confidence Level
            """
            
            response = llm.invoke(prompt)
            timestamp = datetime.now()
            
            state['results']['price_analysis'] = {
                'analysis': response.content,
                'timestamp': timestamp.isoformat()
            }
            
            db_manager.save_price_analysis(
                timestamp=timestamp,
                current_price=current_price,
                analysis_text=response.content
            )
            
        except Exception as e:
            print(f"Error in price analysis: {str(e)}")
            state['results']['price_analysis'] = {
                'analysis': "기술적 분석 중 오류가 발생했습니다. 다음 분석을 기다려주세요.",
                'timestamp': datetime.now().isoformat()
            }
        
        return state
    
def final_decision_agent(state: AgentState) -> AgentState:
    with langsmith.trace(
        name="final_decision_agent",
        project_name="bitcoin_agent",
        tags=["final", "decision"]
    ):
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        market_data = get_market_data_once(state)
        current_price = 0
        
        try:
            if isinstance(market_data.get('current_price'), (int, float)):
                current_price = market_data['current_price']
            elif isinstance(market_data.get('current_price'), dict):
                current_price = market_data['current_price'].get('closing_price', 0)
            else:
                current_price = 0
                print("Warning: Unable to determine current price format")
        except Exception as e:
            print(f"Error extracting current price: {e}")

        try:
            position = trade_executor.get_current_position()
            avg_price = position.get('avg_price', 0)
            quantity = position.get('total_quantity', 0)
            investment = position.get('total_investment', 0)
            
            profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            position_text = f"""현재 보유 포지션:
            - 평균 매수가: {avg_price:,.0f}원
            - 현재 수익률: {profit_rate:.2f}%
            - 총 투자금액: {investment:,.0f}원
            - 보유 수량: {quantity:.8f} {SYMBOL}"""

        except Exception as e:
            print(f"포지션 정보 조회 실패: {e}")
            position_text = "현재 보유 중인 포지션이 없습니다."

        prompt = f"""
                You are a cryptocurrency investment expert and risk manager.
                Focus on capturing short-term profit opportunities from scalping and day trading perspectives.

                Key Investment Principles:
                - Immediate full position exit when profit exceeds +1% or loss exceeds -1%
                - Investment weight restricted to 0-30% range
                - Decision weight distribution: Price Analysis 85%, News Analysis 15%

                Market Status:
                Current Price: {current_price:,.0f} KRW

                Position Analysis:
                {position_text}

                Market Analysis:
                [News Analysis]
                {state['results']['news_analysis']['analysis']}

                [Technical Analysis]
                {state['results']['price_analysis']['analysis']}

                Please analyze the following items:

                1. Investment Decision
                - Decision: Choose one [Buy/Sell/Hold]
                - Investment Weight: Suggest within 0-30%

                2. Position Analysis
                - Current Profit/Loss Assessment
                - Risk Analysis
                - Position Adjustment Strategy

                3. Conclusion
                Brief description of market conditions and final investment decision"""

        response = llm.invoke(prompt)
        timestamp = datetime.now()
        
        state['results']['final_decision'] = {
            'decision': response.content,
            'timestamp': timestamp.isoformat()
        }
        
        db_manager.save_final_decision(
            timestamp=timestamp,
            current_price=current_price,
            analysis_text=response.content
        )
        
        return state
    
def execute_trading_decision(state: AgentState) -> None:
    """거래 결정을 실행하는 함수"""
    try:
        if 'final_decision' not in state['results']:
            print("최종 결정이 없어 거래를 실행할 수 없습니다.")
            return

        timestamp = datetime.now()
        
        try:
            final_decision = state['results']['final_decision']
            current_price = float(state['market_data']['current_price']['closing_price'])
            
            # 거래 실행
            result = trade_executor.execute_trade(
                decision=final_decision,
                max_investment=INVESTMENT,
                current_price=current_price
            )
            
            # 거래 결과 출력
            print("\n=== 거래 실행 결과 ===")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # HOLD 타입일 경우 별도 처리
            if result.get('type') == 'HOLD':
                db_manager.save_trade_execution(
                    timestamp=timestamp,
                    trade_type='HOLD',
                    quantity=0,
                    price=current_price,  # 현재가 사용
                    total_amount=0,
                    order_id=f"HOLD_{timestamp.strftime('%Y%m%d%H%M%S')}"
                )
            # 실제 거래 케이스 처리
            elif result['status'] == 'SUCCESS':
                db_manager.save_trade_execution(
                    timestamp=timestamp,
                    trade_type=result['type'],
                    quantity=result.get('quantity', 0),
                    price=result.get('price', current_price),
                    total_amount=result.get('total_amount', 0),
                    order_id=result.get('order_id', f"{result['type']}_{timestamp.strftime('%Y%m%d%H%M%S')}")
                )
            # 에러 케이스 처리
            else:
                db_manager.save_trade_execution(
                    timestamp=timestamp,
                    trade_type=result.get('type', 'ERROR'),
                    quantity=0,
                    price=current_price,  # 현재가 사용
                    total_amount=0,
                    order_id=f"ERROR_{timestamp.strftime('%Y%m%d%H%M%S')}"
                )
                
        except Exception as e:
            print(f"거래 실행 중 오류 발생: {str(e)}")
            print(traceback.format_exc())
            
            db_manager.save_trade_execution(
                timestamp=timestamp,
                trade_type='ERROR',
                quantity=0,
                price=current_price,  # 현재가 사용
                total_amount=0,
                order_id=f"ERROR_{timestamp.strftime('%Y%m%d%H%M%S')}"
            )
            
    except Exception as e:
        print(f"거래 실행 함수 전체 오류: {e}")
        print("오류 세부 정보:", traceback.format_exc())


def create_trading_workflow() -> Graph:
    """트레이딩 워크플로우 생성"""
    workflow = StateGraph(AgentState)

    initial_state = {
        "messages": [], 
        "next_step": "news_analysis",
        "results": {},
        "market_data": {},
        "symbol": SYMBOL
    }
    
    # 노드 추가
    workflow.add_node("news_analysis", news_analysis_agent)
    workflow.add_node("price_analysis", price_analysis_agent)
    workflow.add_node("final_decision", final_decision_agent)
    
    # 엣지 추가 (실행 순서 정의)
    workflow.add_edge("news_analysis", "price_analysis")
    workflow.add_edge("price_analysis", "final_decision")
    
    # 시작점과 종료점 설정
    workflow.set_entry_point("news_analysis")
    workflow.set_finish_point("final_decision")
    
    return workflow.compile()

def run_trading_analysis():
    """트레이딩 분석 실행"""
    try:
        print("트레이딩 분석 시작 (LangSmith 모니터링 활성화)")
        app = create_trading_workflow()
        config = {
            "messages": [], 
            "next_step": "news_analysis",
            "results": {},
            "market_data": {}
        }
        
        with langsmith.trace(
            name="complete_trading_analysis",
            project_name="bitcoin_agent",
            tags=["workflow", "complete"]
        ) as tracer:
            result = app.invoke(config)
            
            if 'results' in result:
                print("\n=== 분석 결과 ===")
                if 'news_analysis' in result['results']:
                    print("\n[뉴스 분석]")
                    print(result['results']['news_analysis']['analysis'])
                
                if 'price_analysis' in result['results']:
                    print("\n[가격 분석]")
                    print(result['results']['price_analysis']['analysis'])
                
                if 'final_decision' in result['results']:
                    print("\n[최종 결정]")
                    print(result['results']['final_decision']['decision'])
                    
                    # 거래 실행 추가
                    execute_trading_decision(result)
            else:
                print("분석 결과가 없습니다.")
        
    except Exception as e:
        print(f"분석 실행 중 오류 발생: {e}")
        raise e

def run_continuous_analysis():
    """30분마다 트레이딩 분석을 실행하는 연속 실행 함수"""
    WAIT_MINUTES = 2
    WAIT_SECONDS = WAIT_MINUTES * 60  # 30분을 초로 변환
    
    print("연속 트레이딩 분석 시작...")
    print(f"실행 간격: {WAIT_MINUTES}분")
    print("Ctrl+C를 눌러서 프로그램을 종료할 수 있습니다.")
    
    while True:
        try:
            # 현재 시간 출력
            current_time = datetime.now()
            print(f"\n{'='*50}")
            print(f"새로운 분석 시작 시간: {current_time}")
            print(f"{'='*50}\n")
            
            # 트레이딩 분석 실행
            run_trading_analysis()
            
            # 다음 실행까지 대기
            next_run_time = current_time + timedelta(minutes=WAIT_MINUTES)
            print(f"\n다음 분석 예정 시간: {next_run_time}")
            print(f"다음 분석까지 {WAIT_MINUTES}분 대기 중...")
            
            # 지정된 시간만큼 대기
            time.sleep(WAIT_SECONDS)
            
        except KeyboardInterrupt:
            print("\n프로그램이 사용자에 의해 종료되었습니다.")
            break
        except Exception as e:
            print(f"예기치 않은 오류 발생: {e}")
            print(f"{WAIT_MINUTES}분 후 다시 시도합니다...")
            time.sleep(WAIT_SECONDS)

if __name__ == "__main__":
    # 단일 실행 대신 연속 실행 함수를 호출
    run_continuous_analysis()