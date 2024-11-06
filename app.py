import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pandas as pd
import requests
import time
from database_manager import DatabaseManager
from trading import BithumbTradeExecutor  # BithumbTradeExecutor 추가
import os
from dotenv import load_dotenv

load_dotenv()

try:
    INVESTMENT = float(os.getenv('INVESTMENT'))
except TypeError:
    raise ValueError("INVESTMENT 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

def get_account_balance():
    """계좌 잔고 및 수익률 정보 조회"""
    try:
        trader = BithumbTradeExecutor()
        balance = trader.get_balance()
        
        # 현재 총 자산가치 계산
        total_value = float(balance['available'] * balance['current_price'] + balance['krw_available'])
        
        # 수익률 계산 (전역 변수 INVESTMENT 사용)
        profit = total_value - INVESTMENT
        profit_rate = ((total_value - INVESTMENT) / INVESTMENT) * 100
        
        return {
            'total_value': total_value,
            'profit': profit,
            'profit_rate': profit_rate,
            'krw_available': float(balance['krw_available'])
        }
    except Exception as e:
        print(f"잔고 조회 중 오류 발생: {e}")
        return None

def display_metrics():
    """메트릭 정보를 표시하는 함수"""
    balance_info = get_account_balance()
    
    if balance_info:
        # CSS 스타일 정의
        st.markdown("""
        <style>
        .metric-container {
            text-align: center;
            padding: 10px;
        }
        .metric-label {
            font-size: 1rem;
            color: rgb(153, 153, 153);
            font-weight: 600;
            text-transform: uppercase;
        }
        .metric-value {
            font-size: 2rem !important;
            font-weight: 600;
            color: rgb(255, 255, 255);
        }
        .profit-positive {
            color: #3D9970 !important;
            font-size: 2rem !important;
        }
        .profit-negative {
            color: #FF4136 !important;
            font-size: 2rem !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        cols = st.columns(4)
        
        # 총 자산
        with cols[0]:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-label">총 자산</div>
                <div class="metric-value">₩{balance_info['total_value']:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 현재 수익
        with cols[1]:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-label">현재 수익</div>
                <div class="metric-value">₩{balance_info['profit']:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 수익률
        with cols[2]:
            profit_rate = balance_info['profit_rate']
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-label">수익률</div>
                <div class="{'profit-positive' if profit_rate >= 0 else 'profit-negative'}">
                    {profit_rate:+.2f}%
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # KRW 잔액
        with cols[3]:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-label">KRW 잔액</div>
                <div class="metric-value">₩{balance_info['krw_available']:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

def get_bithumb_candle_data(interval='1m', count=100):
    """빗썸 API에서 실시간 캔들 데이터 조회"""
    try:
        url = f"https://api.bithumb.com/public/candlestick/BTC_KRW/{interval}"
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == '0000':
            # 데이터 변환
            df = pd.DataFrame(data['data'], columns=[
                'timestamp', 'opening_price', 'closing_price',
                'high_price', 'low_price', 'acc_trade_volume'
            ])
            
            # 타임스탬프를 datetime으로 변환 (밀리초를 초로 변환) 및 KST로 변환
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
            df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=9)  # UTC to KST
            
            # 데이터 타입 변환
            numeric_columns = ['opening_price', 'closing_price', 'high_price', 
                             'low_price', 'acc_trade_volume']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            # 최근 count개만큼 데이터 반환
            return df.tail(count)
    except Exception as e:
        print(f"빗썸 API 호출 중 오류 발생: {e}")
        return pd.DataFrame()

def create_trading_chart(market_df, trade_df):
    """거래 내역이 포함된 BTC 가격 차트 생성"""    
    # 가격 범위 계산
    min_price = market_df['low_price'].min()
    max_price = market_df['high_price'].max()
    price_margin = (max_price - min_price) * 0.1

    # 서브플롯 생성 (캔들스틱 + 거래량)
    fig = make_subplots(rows=2, cols=1, 
                       shared_xaxes=True,
                       vertical_spacing=0.03,
                       row_heights=[0.7, 0.3])

    # 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=market_df['timestamp'],
            open=market_df['opening_price'],
            high=market_df['high_price'],
            low=market_df['low_price'],
            close=market_df['closing_price'],
            name='OHLC',
            increasing_line_width=4,
            decreasing_line_width=4,
            increasing_fillcolor='#3D9970',
            decreasing_fillcolor='#FF4136'
        ),
        row=1, col=1
    )

    # 거래 내역 표시
    if not trade_df.empty:
        # 차트에 표시된 기간에 맞추기
        min_time = market_df['timestamp'].min()
        max_time = market_df['timestamp'].max()
        
        # timestamp 비교를 위해 timezone 정보 제거
        trade_df['timestamp'] = trade_df['timestamp'].dt.tz_localize(None)
        market_df['timestamp'] = market_df['timestamp'].dt.tz_localize(None)
        
        # 거래 데이터 필터링
        filtered_trade_df = trade_df[
            (trade_df['timestamp'] >= min_time) & 
            (trade_df['timestamp'] <= max_time)
        ]

        # 색상 매핑 설정
        color_map = {
            'BUY': "rgba(255, 0, 0, 0.9)",          # 선명한 빨간색
            'HOLD': "rgba(255, 255, 0, 0.9)",       # 선명한 노란색
            'SELL': "rgba(0, 255, 255, 0.9)",       # 선명한 시안색
            'CANT_BUY': "rgba(255, 0, 255, 0.9)"    # 선명한 마젠타(형광 보라)
        }

        # 매수/매도/홀드 시그널 추가
        for idx, row in filtered_trade_df.iterrows():
            line_color = color_map.get(row['trade_type'], "rgba(128, 128, 128, 0.7)")  # 기본값은 회색
            
            # 가격 차트에 수직선 추가
            fig.add_shape(
                type="line",
                x0=row['timestamp'],
                x1=row['timestamp'],
                y0=min_price - price_margin,
                y1=max_price + price_margin,
                line=dict(
                    color=line_color,
                    width=3,
                    dash="dash",
                ),
                row=1, col=1
            )
            
            # # 거래량 차트에 수직선 추가
            # fig.add_shape(
            #     type="line",
            #     x0=row['timestamp'],
            #     x1=row['timestamp'],
            #     y0=0,
            #     y1=market_df['acc_trade_volume'].max() * 1.1,
            #     line=dict(
            #         color=line_color,
            #         width=2,
            #         dash="dash",
            #     ),
            #     row=2, col=1
            # )

        # 범례 추가
        for trade_type, color in color_map.items():
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode='lines',
                    name=f'{trade_type.capitalize()} Signal',
                    line=dict(color=color, width=2, dash="dash"),
                    showlegend=True
                ),
                row=1, col=1
            )

    # 거래량 차트
    fig.add_trace(
        go.Bar(
            x=market_df['timestamp'],
            y=market_df['acc_trade_volume'],
            name='Volume',
            marker_color='#7FDBFF'
        ),
        row=2, col=1
    )

    # 차트 스타일 설정
    current_price = market_df['closing_price'].iloc[-1]
    fig.update_layout(
        title=f'Bitcoin Price Chart (Current: ₩{current_price:,.0f})',
        yaxis=dict(
            title='Price (KRW)',
            range=[min_price - price_margin, max_price + price_margin],
            tickformat=','
        ),
        yaxis2=dict(
            title='Volume',
            range=[0, market_df['acc_trade_volume'].max() * 1.1]
        ),
        xaxis_rangeslider_visible=False,
        height=800,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        bargap=0.3
    )

    fig.update_xaxes(gridcolor='#333333', showgrid=True)
    fig.update_yaxes(gridcolor='#333333', showgrid=True)

    return fig

def display_trade_history(trade_df):
    """거래 내역을 표시하는 함수"""
    st.header("Trading History")
    
    if trade_df.empty:
        st.info("No trading history in the selected time period.")
        return
    
    # 거래 내역 데이터프레임 포맷팅
    display_df = trade_df.copy()
    display_df['timestamp'] = pd.to_datetime(display_df['timestamp'])
    # UTC to KST 변환 제거
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df['price'] = display_df['price'].apply(lambda x: f"₩{x:,.0f}")
    display_df['total_amount'] = display_df['total_amount'].apply(lambda x: f"₩{x:,.0f}")
    display_df['trade_type'] = display_df['trade_type'].str.upper()
    
    st.dataframe(
        display_df,
        column_config={
            "timestamp": "Time",
            "trade_type": "Type",
            "quantity": "Quantity (BTC)",
            "price": "Price",
            "total_amount": "Total Amount",
            "order_id": "Order ID"
        },
        hide_index=True
    )

def get_trade_executions(db, hours=24):
    """거래 실행 내역을 가져오는 함수"""
    with db.get_connection() as conn:
        query = """
        SELECT 
            timestamp,
            trade_type,
            quantity,
            price,
            total_amount,
            order_id
        FROM trade_executions
        WHERE timestamp >= datetime('now', ?)
        ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn, params=(f'-{hours} hours',))
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # UTC to KST 변환 제거
        return df

def display_analysis_results(latest_analysis, all_analysis):
    """분석 결과를 표시하는 함수"""
    st.header("Latest Analysis Results")
    
    # 탭 생성
    analysis_tabs = st.tabs(["Final Decision", "Price Analysis", "News Analysis"])
    
    if not all_analysis.empty:
        # 각 분석 유형별 최신 데이터 가져오기
        final_analysis = all_analysis[all_analysis['analysis_type'] == 'final'].iloc[0] if len(all_analysis[all_analysis['analysis_type'] == 'final']) > 0 else None
        price_analysis = all_analysis[all_analysis['analysis_type'] == 'price'].iloc[0] if len(all_analysis[all_analysis['analysis_type'] == 'price']) > 0 else None
        news_analysis = all_analysis[all_analysis['analysis_type'] == 'news'].iloc[0] if len(all_analysis[all_analysis['analysis_type'] == 'news']) > 0 else None
        
        # Final Decision 탭
        with analysis_tabs[0]:
            if final_analysis is not None:
                st.markdown("### Final Trading Decision")
                st.markdown(f"**Timestamp:** {final_analysis['timestamp']}")
                if pd.notnull(final_analysis['current_price']):
                    st.markdown(f"**Current Price:** ₩{final_analysis['current_price']:,}")
                st.text_area("Analysis", final_analysis['analysis_text'], height=300, key="final_decision")
            else:
                st.info("No final decision analysis available.")
        
        # Price Analysis 탭
        with analysis_tabs[1]:
            if price_analysis is not None:
                st.markdown("### Technical Analysis")
                st.markdown(f"**Timestamp:** {price_analysis['timestamp']}")
                st.text_area("Analysis", price_analysis['analysis_text'], height=300, key="price_analysis")
            else:
                st.info("No price analysis available.")
        
        # News Analysis 탭
        with analysis_tabs[2]:
            if news_analysis is not None:
                st.markdown("### News Analysis")
                st.markdown(f"**Timestamp:** {news_analysis['timestamp']}")
                st.text_area("Analysis", news_analysis['analysis_text'], height=300, key="news_analysis")
            else:
                st.info("No news analysis available.")
    
    # Analysis History 표시
    st.header("Analysis History")
    for _, row in all_analysis.iterrows():
        with st.expander(f"{row['analysis_type']} Analysis - {row['timestamp']}"):
            if pd.notnull(row['current_price']):
                st.markdown(f"**Current Price:** ₩{row['current_price']:,}")
            st.text_area("Analysis", row['analysis_text'], height=200, key=f"{row['timestamp']}_{row['analysis_type']}")

def main():
    st.set_page_config(page_title='Bithumb Trading Monitor', 
                      layout='wide',
                      initial_sidebar_state='expanded')
    
    # 세션 상태 초기화
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 30
    if 'candle_interval' not in st.session_state:
        st.session_state.candle_interval = '5m'
    if 'candle_count' not in st.session_state:
        st.session_state.candle_count = 100

    # 스타일 설정 (이전과 동일)
    st.markdown("""
        <style>
        .stApp {
            background-color: #1e1e1e;
            color: white;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #2d2d2d;
            border-radius: 4px;
            padding: 10px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #0e84b5;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        </style>
        """, unsafe_allow_html=True)
    
    st.title('Bithumb Bitcoin Trading Monitor')

    # 데이터베이스 매니저 초기화
    db = DatabaseManager()

    display_metrics()

    # 사이드바 설정
    st.sidebar.header('Settings')
    
    # 새로고침 간격 설정
    st.session_state.refresh_interval = st.sidebar.slider(
        'Refresh Interval (seconds)', 
        min_value=1, 
        max_value=60, 
        value=st.session_state.refresh_interval
    )

    # 캔들 간격 설정
    st.session_state.candle_interval = st.sidebar.selectbox(
        'Candle Interval',
        ['1m', '3m', '5m', '10m', '30m', '1h', '6h', '12h', '24h'],
        index=['1m', '3m', '5m', '10m', '30m', '1h', '6h', '12h', '24h'].index(st.session_state.candle_interval)
    )

    # 캔들 개수 설정
    st.session_state.candle_count = st.sidebar.slider(
        'Number of Candles', 
        min_value=20, 
        max_value=200, 
        value=st.session_state.candle_count
    )

    # 탭 생성
    tabs = st.tabs(["Trading Chart", "Trade History", "Analysis Results"])

    # Trading Chart 탭
    with tabs[0]:
        # 실시간 데이터 로드
        market_df = get_bithumb_candle_data(st.session_state.candle_interval, st.session_state.candle_count)
        trade_df = get_trade_executions(db, hours=24)

        if not market_df.empty:
            chart_container = st.empty()
            fig = create_trading_chart(market_df, trade_df)
            chart_container.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Failed to load market data from Bithumb API.")

    # Trade History 탭
    with tabs[1]:
        display_trade_history(trade_df)

    # Analysis Results 탭
    with tabs[2]:
        latest_analysis = db.get_latest_full_analysis()
        all_analysis = db.get_all_analysis_results(hours=24)
        #print(all_analysis)
        display_analysis_results(latest_analysis, all_analysis)

    # 자동 새로고침 적용
    st.markdown(f"""
        <meta http-equiv="refresh" content="{st.session_state.refresh_interval}">
        <script>
            setTimeout(function(){{ window.location.reload(); }}, {st.session_state.refresh_interval * 1000});
        </script>
    """, unsafe_allow_html=True)

    # 현재 시간 표시
    st.sidebar.markdown("---")
    st.sidebar.write("Last update:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # main() 함수 내 trade_df 로드 후
    if not trade_df.empty:
        st.sidebar.write("거래 데이터 확인:")
        st.sidebar.write(f"총 거래 건수: {len(trade_df)}")
        st.sidebar.write(f"매수 건수: {len(trade_df[trade_df['trade_type'] == 'buy'])}")
        st.sidebar.write(f"매도 건수: {len(trade_df[trade_df['trade_type'] == 'sell'])}")
        st.sidebar.write("시간 범위:", trade_df['timestamp'].min(), "~", trade_df['timestamp'].max())

if __name__ == "__main__":
    main()