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

# 환경 변수 및 LangSmith 설정
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = "crypto-trading-analysis"

# 상태 타입 정의
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next_step: str
    results: dict

# 데이터베이스 매니저 초기화
db_manager = DatabaseManager()
langsmith_client = Client()

@tool
def get_recent_news(dummy: str = "") -> str:
    """최근 24시간 동안의 비트코인 관련 뉴스를 가져옵니다."""
    with langsmith.trace(
        name="get_recent_news",
        project_name="crypto-trading-analysis",
        tags=["news", "data-collection"]
    ):
        news_df = db_manager.get_recent_news(hours=24)
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

@tool
def get_market_data(dummy: str = "") -> str:
    """최근 24시간 동안의 비트코인 가격 데이터를 가져옵니다."""
    with langsmith.trace(
        name="get_market_data",
        project_name="crypto-trading-analysis",
        tags=["market", "data-collection"]
    ):
        market_df = db_manager.get_market_data(hours=24)
        if market_df.empty:
            return "가격 데이터가 없습니다."
        
        price_history = [
            {
                'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                'current_price': float(row['current_price'])
            }
            for _, row in market_df[['timestamp', 'current_price']].iterrows()
        ]
        
        market_data = {
            'current_price': float(market_df.iloc[-1]['current_price']),
            'opening_price': float(market_df.iloc[-1]['opening_price']),
            'high_price': float(market_df.iloc[-1]['high_price']),
            'low_price': float(market_df.iloc[-1]['low_price']),
            'signed_change_rate': float(market_df.iloc[-1]['signed_change_rate']),
            'price_history': price_history
        }
        return json.dumps(market_data, ensure_ascii=False)

def news_analysis_agent(state: AgentState) -> AgentState:
    """뉴스를 분석하여 투자 제안을 하는 에이전트"""
    with langsmith.trace(
        name="news_analysis_agent",
        project_name="crypto-trading-analysis",
        tags=["news", "analysis"]
    ) as tracer:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        news_data = get_recent_news.invoke("")
        #current_price = json.loads(get_market_data.invoke(""))['current_price']
        
        prompt = f"""당신은 암호화폐 뉴스 분석 전문가입니다. 
        최근 24시간 동안의 비트코인 관련 뉴스를 분석하여 투자 결정을 내려주세요.
        
        뉴스 데이터:
        {news_data}
        
        다음 형식으로 분석 결과를 제공해주세요:
        1. 투자 결정: (매수/매도/관망)
        2. 투자 비중: (0-100%)
        3. 결정 이유: (뉴스 기반 분석)
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
            #current_price=current_price,
            analysis_text=response.content
        )
        
        return state

def price_analysis_agent(state: AgentState) -> AgentState:
    """가격 데이터를 분석하여 투자 제안을 하는 에이전트"""
    with langsmith.trace(
        name="price_analysis_agent",
        project_name="crypto-trading-analysis",
        tags=["price", "analysis"]
    ) as tracer:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        market_data = get_market_data.invoke("")
        current_price = json.loads(market_data)['current_price']
        
        prompt = f"""당신은 암호화폐 기술적 분석 전문가입니다. 
        최근 24시간 동안의 비트코인 가격 데이터를 분석하여 투자 결정을 내려주세요.
        
        시장 데이터:
        {market_data}
        
        다음 형식으로 분석 결과를 제공해주세요:
        1. 투자 결정: (매수/매도/관망)
        2. 투자 비중: (0-100%)
        3. 결정 이유: (가격 동향 기반 분석)
        4. 목표가: (매수/매도 시)
        5. 손절가: (매수/매도 시)
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
        
        return state

def final_decision_agent(state: AgentState) -> AgentState:
    """뉴스 분석과 가격 분석을 종합하여 최종 투자 결정을 내리는 에이전트"""
    with langsmith.trace(
        name="final_decision_agent",
        project_name="crypto-trading-analysis",
        tags=["final", "decision"]
    ) as tracer:
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        prompt = f"""당신은 암호화폐 투자 최고 결정권자입니다.
        뉴스 분석과 가격 분석 결과를 종합하여 최종 투자 결정을 내려주세요.
        
        뉴스 분석 결과:
        {state['results']['news_analysis']['analysis']}
        
        가격 분석 결과:
        {state['results']['price_analysis']['analysis']}
        
        다음 형식으로 최종 결정을 제공해주세요:
        1. 최종 투자 결정: (매수/매도/관망)
        2. 최종 투자 비중: (0-100%)
        3. 결정 이유: (종합적인 분석)
        4. 위험도: (상/중/하)
        5. 투자 전략: (단기/중기/장기)
        """
        
        response = llm.invoke(prompt)
        timestamp = datetime.now()
        current_price = json.loads(get_market_data.invoke(""))['current_price']
        
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

def create_trading_workflow() -> Graph:
    workflow = StateGraph(AgentState)
    workflow.add_node("news_analysis", news_analysis_agent)
    workflow.add_node("price_analysis", price_analysis_agent)
    workflow.add_node("final_decision", final_decision_agent)
    workflow.add_edge("news_analysis", "price_analysis")
    workflow.add_edge("price_analysis", "final_decision")
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
            "results": {}
        }
        
        with langsmith.trace(
            name="complete_trading_analysis",
            project_name="crypto-trading-analysis",
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
            else:
                print("분석 결과가 없습니다.")
        
    except Exception as e:
        print(f"분석 실행 중 오류 발생: {e}")
        raise e

if __name__ == "__main__":
    run_trading_analysis()