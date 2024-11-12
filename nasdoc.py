import yfinance as yf
import pandas as pd
from datetime import datetime
import time

def get_nasdaq_realtime():
    """
    나스닥 실시간 1분 데이터를 가져오는 함수
    """
    try:
        # 나스닥 지수 데이터 가져오기
        nasdaq = yf.Ticker('^IXIC')
        df = nasdaq.history(period='1d', interval='1m')
        
        if df.empty:
            print("데이터를 가져올 수 없습니다.")
            return None
        
        # 최신 데이터
        current_time = datetime.now().strftime("%H:%M:%S")
        last_price = float(df['Close'].iloc[-1])
        previous_close = float(nasdaq.info.get('regularMarketPreviousClose', 0))
        
        # 변동폭 계산
        change = last_price - previous_close
        change_percent = (change / previous_close) * 100
        
        # 당일 정보
        day_high = float(df['High'].max())
        day_low = float(df['Low'].min())
        day_volume = int(df['Volume'].sum())
        
        # 화면 지우기 출력
        print("\033[H\033[J")  # 터미널 화면 지우기
        
        # 현재 정보 출력
        print(f"\n========== 나스닥 실시간 정보 ({current_time}) ==========")
        print(f"현재 지수: {last_price:,.2f}")
        print(f"전일 종가: {previous_close:,.2f}")
        print(f"변동폭: {change:+,.2f} ({change_percent:+,.2f}%)")
        
        print("\n========== 당일 거래 정보 ==========")
        print(f"당일 최고: {day_high:,.2f}")
        print(f"당일 최저: {day_low:,.2f}")
        print(f"거래량: {day_volume:,}")
        
        # 최근 5분 추이
        print("\n========== 최근 5분 추이 ==========")
        recent_5min = df.tail(5)
        for idx, row in recent_5min.iterrows():
            time_str = idx.strftime("%H:%M")
            close_price = float(row['Close'])
            minute_change = close_price - float(df['Close'].shift(1).loc[idx])
            minute_change_percent = (minute_change / float(df['Close'].shift(1).loc[idx])) * 100
            print(f"{time_str} | {close_price:,.2f} | {minute_change:+,.2f} ({minute_change_percent:+,.2f}%)")
        
        return df
        
    except Exception as e:
        print(f"에러 발생: {str(e)}")
        return None

def monitor_nasdaq(refresh_interval=60):
    """
    나스닥 지수를 실시간으로 모니터링하는 함수
    
    Parameters:
    refresh_interval (int): 갱신 주기 (초 단위, 기본값 60초)
    """
    print("나스닥 실시간 모니터링을 시작합니다...")
    print("종료하려면 Ctrl+C를 누르세요.")
    
    try:
        while True:
            df = get_nasdaq_realtime()
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\n모니터링을 종료합니다.")
    except Exception as e:
        print(f"모니터링 중 오류 발생: {str(e)}")

# 사용 예시ㅎ
if __name__ == "__main__":
    # 60초마다 갱신하여 모니터링
    monitor_nasdaq(refresh_interval=60)