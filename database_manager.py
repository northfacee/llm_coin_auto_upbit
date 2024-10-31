from datetime import datetime
import pandas as pd
import sqlite3

class DatabaseManager:
    def __init__(self, db_name='crypto_data.db'):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """데이터베이스 및 테이블 초기화"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # 시장 데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp DATETIME PRIMARY KEY,
                market TEXT,
                current_price REAL,
                opening_price REAL,
                high_price REAL,
                low_price REAL,
                prev_closing_price REAL,
                acc_trade_volume_24h REAL,
                acc_trade_price_24h REAL,
                signed_change_rate REAL,
                signed_change_price REAL
            )
        ''')
        
        # 거래 분석 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_analysis (
                timestamp DATETIME PRIMARY KEY,
                current_price REAL,
                decision TEXT,
                investment_ratio INTEGER,
                reason TEXT,
                stop_loss REAL,
                target_price REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_market_data(self, market_data):
        """시장 데이터를 데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO market_data (
                    timestamp, market, current_price, opening_price, high_price,
                    low_price, prev_closing_price, acc_trade_volume_24h,
                    acc_trade_price_24h, signed_change_rate, signed_change_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market_data['timestamp'],
                market_data['market'],
                market_data['current_price'],
                market_data['opening_price'],
                market_data['high_price'],
                market_data['low_price'],
                market_data['prev_closing_price'],
                market_data['acc_trade_volume_24h'],
                market_data['acc_trade_price_24h'],
                market_data['signed_change_rate'],
                market_data['signed_change_price']
            ))
            conn.commit()
        except sqlite3.Error as e:
            print(f"데이터 저장 중 오류 발생: {e}")
        finally:
            conn.close()
    
    def save_analysis_result(self, timestamp, current_price, analysis_text):
        """분석 결과를 데이터베이스에 저장"""
        try:
            # GPT 분석 결과 파싱
            lines = analysis_text.split('\n')
            decision = ""
            investment_ratio = 0
            reason = ""
            stop_loss = 0
            target_price = 0
            
            for line in lines:
                if "투자 결정:" in line:
                    decision_part = line.split(":")[1].strip()
                    decision = decision_part.split("(")[0].strip()
                    if "(" in decision_part:
                        investment_ratio = int(decision_part.split("(")[1].split("%")[0])
                elif "결정 이유:" in line:
                    reason = line.split(":")[1].strip()
                elif "손절가 제안:" in line:
                    stop_loss = float(line.split(":")[1].split("원")[0].strip().replace(",", ""))
                elif "목표가 제안:" in line:
                    target_price = float(line.split(":")[1].split("원")[0].strip().replace(",", ""))

            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trading_analysis 
                (timestamp, current_price, decision, investment_ratio, reason, stop_loss, target_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                current_price,
                decision,
                investment_ratio,
                reason,
                stop_loss,
                target_price
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"분석 결과 저장 중 오류 발생: {e}")
    
    def get_market_data(self, hours=24):
        """시장 데이터 조회"""
        conn = sqlite3.connect(self.db_name)
        
        query = f'''
            SELECT * FROM market_data 
            WHERE timestamp >= datetime('now', '-{hours} hours')
            ORDER BY timestamp ASC
        '''
        
        df = pd.read_sql_query(query, conn, parse_dates=['timestamp'])
        conn.close()
        return df
    
    def get_analysis_data(self, hours=24):
        """거래 분석 데이터 조회"""
        conn = sqlite3.connect(self.db_name)
        
        query = f'''
            SELECT * FROM trading_analysis
            WHERE timestamp >= datetime('now', '-{hours} hours')
            ORDER BY timestamp ASC
        '''
        
        df = pd.read_sql_query(query, conn, parse_dates=['timestamp'])
        conn.close()
        return df
    
    def get_latest_price(self):
        """최신 가격 데이터 조회"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, current_price, signed_change_rate
            FROM market_data
            ORDER BY timestamp DESC
            LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'timestamp': result[0],
                'price': result[1],
                'change_rate': result[2]
            }
        return None
    
    def get_latest_analysis(self):
        """최신 거래 분석 조회"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, current_price, decision, investment_ratio, reason
            FROM trading_analysis
            ORDER BY timestamp DESC
            LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'timestamp': result[0],
                'price': result[1],
                'decision': result[2],
                'investment_ratio': result[3],
                'reason': result[4]
            }
        return None