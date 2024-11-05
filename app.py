import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from database_manager import DatabaseManager
import pandas as pd

def create_price_chart(market_df, analysis_df):
    """가격 차트 생성 (매수/매도 포인트 포함)"""
    # 최근 20개 데이터만 사용
    market_df = market_df.tail(20)
    
    min_price = market_df['low_price'].min()
    max_price = market_df['high_price'].max()
    price_margin = (max_price - min_price) * 0.1

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.03, 
                       row_heights=[0.7, 0.3])

    # 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=market_df['timestamp'],
            open=market_df['opening_price'],
            high=market_df['high_price'],
            low=market_df['low_price'],
            close=market_df['current_price'],
            name='OHLC',
            increasing_line_width=4,  # 증가 캔들 두께
            decreasing_line_width=4,  # 감소 캔들 두께
            increasing_fillcolor='#3D9970',  # 증가 캔들 색상
            decreasing_fillcolor='#FF4136'   # 감소 캔들 색상
        ),
        row=1, col=1
    )

    # 매수/매도 포인트 추가
    if not analysis_df.empty and hasattr(analysis_df, 'decision'):
        # 분석 데이터도 차트에 표시된 기간에 맞추기
        min_time = market_df['timestamp'].min()
        max_time = market_df['timestamp'].max()
        analysis_df = analysis_df[
            (analysis_df['timestamp'] >= min_time) & 
            (analysis_df['timestamp'] <= max_time)
        ]
        
        # 매수 포인트 (빨간색)
        buy_points = analysis_df[analysis_df['decision'].str.contains('매수', na=False)]
        if not buy_points.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_points['timestamp'],
                    y=buy_points['current_price'],
                    mode='markers',
                    name='Buy',
                    marker=dict(
                        symbol='triangle-up',
                        size=20,
                        color='#FF4136',
                        line=dict(color='white', width=2)
                    ),
                    hovertemplate='매수 시점<br>가격: %{y:,.0f}원<br>투자비중: %{text}%',
                    text=buy_points['investment_ratio']
                ),
                row=1, col=1
            )

        # 매도 포인트 (파란색)
        sell_points = analysis_df[analysis_df['decision'].str.contains('매도', na=False)]
        if not sell_points.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_points['timestamp'],
                    y=sell_points['current_price'],
                    mode='markers',
                    name='Sell',
                    marker=dict(
                        symbol='triangle-down',
                        size=20,
                        color='#0074D9',
                        line=dict(color='white', width=2)
                    ),
                    hovertemplate='매도 시점<br>가격: %{y:,.0f}원<br>투자비중: %{text}%',
                    text=sell_points['investment_ratio']
                ),
                row=1, col=1
            )

    # 거래량 차트
    fig.add_trace(
        go.Bar(
            x=market_df['timestamp'],
            y=market_df['acc_trade_volume_24h'],
            name='Volume',
            marker_color='#7FDBFF'
        ),
        row=2, col=1
    )

    # 차트 스타일 설정
    fig.update_layout(
        title='Bitcoin Price Chart with Trading Signals',
        yaxis=dict(
            title='Price (KRW)',
            range=[min_price - price_margin, max_price + price_margin],
            tickformat=','
        ),
        yaxis2=dict(
            title='Volume',
            range=[0, market_df['acc_trade_volume_24h'].max() * 1.1]
        ),
        xaxis_rangeslider_visible=False,
        height=800,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        bargap=0.3  # 바 차트 간격 조정
    )

    fig.update_xaxes(gridcolor='#333333', showgrid=True)
    fig.update_yaxes(gridcolor='#333333', showgrid=True)

    return fig

def display_analysis_results(latest_analysis, all_analysis):
    """분석 결과를 표시하는 함수"""
    # 최신 전체 분석 결과 표시
    if latest_analysis:
        st.header("Latest Analysis Results")
        
        # 탭 생성
        tabs = st.tabs(["Final Decision", "Price Analysis", "News Analysis"])
        
        # Final Decision 탭
        with tabs[0]:
            st.markdown("### Final Trading Decision")
            st.markdown(f"**Timestamp:** {latest_analysis['final_timestamp']}")
            st.markdown(f"**Current Price:** ₩{latest_analysis['current_price']:,}")
            st.text_area("Analysis", latest_analysis['final_decision'], 
                        height=300, key="final_decision")
        
        # Price Analysis 탭
        with tabs[1]:
            st.markdown("### Technical Analysis")
            st.markdown(f"**Timestamp:** {latest_analysis['price_timestamp']}")
            st.text_area("Analysis", latest_analysis['price_analysis'], 
                        height=300, key="price_analysis")
        
        # News Analysis 탭
        with tabs[2]:
            st.markdown("### News Analysis")
            st.markdown(f"**Timestamp:** {latest_analysis['news_timestamp']}")
            st.text_area("Analysis", latest_analysis['news_analysis'], 
                        height=300, key="news_analysis")
    
    # 전체 분석 이력 표시
    st.header("Analysis History")
    for _, row in all_analysis.iterrows():
        with st.expander(
            f"{row['analysis_type'].upper()} Analysis - {row['timestamp']}"
        ):
            if row['current_price']:
                st.markdown(f"**Current Price:** ₩{row['current_price']:,}")
            st.text_area("Analysis", row['analysis_text'], 
                        height=200, key=f"{row['timestamp']}_{row['analysis_type']}")

def main():
    st.set_page_config(page_title='Bithumb Trading Monitor', 
                      layout='wide',
                      initial_sidebar_state='expanded')
    
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
        </style>
        """, unsafe_allow_html=True)
    
    st.title('Bithumb Bitcoin Trading Monitor')

    # 데이터베이스 매니저 초기화
    db = DatabaseManager()

    # 사이드바 설정
    st.sidebar.header('Settings')
    hours = st.sidebar.slider('Data Range (hours)', 1, 72, 24)
    refresh_interval = st.sidebar.slider('Refresh Interval (seconds)', 5, 60, 10)

    # 데이터 로드
    latest_analysis = db.get_latest_full_analysis()
    all_analysis = db.get_all_analysis_results(hours=hours)
    market_df = db.get_market_data(hours=hours)
    analysis_df = db.get_analysis_data(hours=hours)

    # 차트 표시
    if not market_df.empty:
        fig = create_price_chart(market_df, analysis_df)
        st.plotly_chart(fig, use_container_width=True)

    # 분석 결과 표시
    display_analysis_results(latest_analysis, all_analysis)

    # 자동 새로고침
    st.markdown(f"""
        <meta http-equiv="refresh" content="{refresh_interval}">
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()