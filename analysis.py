from bithumb import BithumbTrader
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from database_manager import DatabaseManager

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langsmith import Client
from langchain.smith import RunEvalConfig
import langsmith

def analyze_market():
    """실시간 시장 데이터 수집 및 분석"""
    try:
        # 환경 변수 로드
        load_dotenv()
        # LangSmith 설정
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
        os.environ["LANGCHAIN_PROJECT"] = "crypto-trading-analysis"
        
        # LangSmith 클라이언트 초기화
        langsmith_client = Client()
        
        # 빗썸 트레이더 초기화
        trader = BithumbTrader()
        
        # 데이터베이스 매니저 초기화
        db_manager = DatabaseManager()
        
        # LangChain 모델 초기화
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")

        # 프롬프트 템플릿 정의
        prompt = ChatPromptTemplate.from_template("""
현재 비트코인 시장 상황 분석 요청 (분석 시각: {timestamp})

가격 정보:
- 현재가: {current_price:,.0f}원
- 시가: {opening_price:,.0f}원
- 고가: {high_price:,.0f}원
- 저가: {low_price:,.0f}원
- 전일종가: {prev_closing_price:,.0f}원

거래량 정보:
- 24시간 거래량: {acc_trade_volume_24h:.4f}
- 24시간 거래대금: {acc_trade_price_24h:,.0f}원

가격 변동:
- 전일 대비 변동금액: {signed_change_price:,.0f}원
- 전일 대비 변동률: {signed_change_rate:.2f}%

위 데이터를 바탕으로 다음 형식에 맞춰 분석해주세요:

1. 투자 결정: [매수/매도/관망] 중 하나를 선택하고, 매수/매도 시 투자 비중(%)을 제시
2. 결정 이유: 2-3문장으로 설명
3. 리스크 관리:
   - 손절가 제안
   - 목표가 제안
""")

        # System 메시지를 포함한 프롬프트 체인 구성
        system_prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 암호화폐 트레이딩 전문가입니다. 주어진 시장 데이터를 분석하여 매수/매도/관망 결정을 내리고 그 이유를 설명해주세요. 그리고 당신은 매우 공격적으로 매수합니다. 위험리스크가 상당히 높은 것도 가능해요"),
            ("user", "{input}")
        ])

        # LangChain 체인 구성
        chain = (
            {"input": prompt} 
            | RunnablePassthrough()
            | system_prompt 
            | llm
            | StrOutputParser()
        )

        print("실시간 트레이딩 분석 시작")
        print("=" * 50)

        while True:
            try:
                # 시장 데이터 수집
                market_data = trader.collect_market_data(market="BTC_KRW")
                if not market_data:
                    print("데이터 수집 실패 - 1분 후 재시도")
                    time.sleep(60)
                    continue

                # 숫자 데이터 형변환
                formatted_data = {
                    "timestamp": market_data['timestamp'],
                    "current_price": float(market_data.get('current_price', 0)),
                    "opening_price": float(market_data.get('opening_price', 0)),
                    "high_price": float(market_data.get('high_price', 0)),
                    "low_price": float(market_data.get('low_price', 0)),
                    "prev_closing_price": float(market_data.get('prev_closing_price', 0)),
                    "acc_trade_volume_24h": float(market_data.get('acc_trade_volume_24h', 0)),
                    "acc_trade_price_24h": float(market_data.get('acc_trade_price_24h', 0)),
                    "signed_change_price": float(market_data.get('signed_change_price', 0)),
                    "signed_change_rate": float(market_data.get('signed_change_rate', 0))
                }

                # LangChain을 통한 분석 실행
                with langsmith.trace(
                    name="crypto_analysis",  # 추가된 name 파라미터
                    project_name="crypto-trading-analysis",
                    tags=["bitcoin", "market-analysis"]
                ) as tracer:
                    analysis = chain.invoke(formatted_data)

                # 시장 데이터 DB 저장
                db_manager.save_market_data(market_data)
                
                # 분석 결과 DB 저장
                db_manager.save_analysis_result(
                    timestamp=market_data['timestamp'],
                    current_price=formatted_data['current_price'],
                    analysis_text=analysis
                )

                # 분석 결과 출력
                print("\n" + "=" * 50)
                print(f"분석 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"현재 비트코인 가격: {formatted_data['current_price']:,.0f}원")
                print(f"24시간 변동률: {formatted_data['signed_change_rate']:.2f}%")
                print("-" * 50)
                print("LangChain 분석 결과:")
                print(analysis)
                print("=" * 50)

                # JSON 로그 파일 저장 (백업용)
                log_entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "market_data": market_data,
                    "analysis": analysis
                }
                
                with open("trading_analysis_log.jsonl", 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

                # 대기
                time.sleep(10)
            
            except Exception as e:
                print(f"분석 중 오류 발생: {e}")
                print("1분 후 재시도")
                time.sleep(10)
    
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 종료되었습니다.")
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    analyze_market()