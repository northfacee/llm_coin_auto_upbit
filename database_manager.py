import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

class DatabaseManager:
    def __init__(self, db_path: str = "crypto_analysis.db"):
        """데이터베이스 매니저 초기화"""
        self.db_path = db_path
        self._create_tables()

    def get_connection(self):
        """데이터베이스 연결을 반환합니다."""
        return sqlite3.connect(self.db_path)
    
    def _create_tables(self):
        """필요한 테이블들을 생성합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 뉴스 데이터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    pub_date TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 시장 데이터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    current_price REAL NOT NULL,
                    opening_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    signed_change_rate REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 뉴스 분석 결과 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    analysis_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 가격 분석 결과 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    current_price REAL NOT NULL,
                    analysis_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 최종 결정 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS final_decision (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    current_price REAL NOT NULL,
                    analysis_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 거래 실행 결과 테이블 추가
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    trade_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    order_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def save_news(self, title: str, description: str, pub_date: datetime):
        """뉴스 데이터를 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO news (title, description, pub_date)
                VALUES (?, ?, ?)
            """, (title, description, pub_date))
            conn.commit()
    
    def save_market_data(self, timestamp: datetime, current_price: float, 
                        opening_price: float, high_price: float, 
                        low_price: float, signed_change_rate: float):
        """시장 데이터를 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO market_data (
                    timestamp, current_price, opening_price, 
                    high_price, low_price, signed_change_rate
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, current_price, opening_price, 
                 high_price, low_price, signed_change_rate))
            conn.commit()
    
    def save_news_analysis(self, timestamp: datetime, analysis_text: str):
        """뉴스 분석 결과를 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO news_analysis (timestamp, analysis_text)
                VALUES (?, ?)
            """, (timestamp, analysis_text))
            conn.commit()
    
    def save_price_analysis(self, timestamp: datetime, current_price: float, analysis_text: str):
        """가격 분석 결과를 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_analysis (timestamp, current_price, analysis_text)
                VALUES (?, ?, ?)
            """, (timestamp, current_price, analysis_text))
            conn.commit()
    
    def save_final_decision(self, timestamp: datetime, current_price: float, analysis_text: str):
        """최종 투자 결정을 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO final_decision (timestamp, current_price, analysis_text)
                VALUES (?, ?, ?)
            """, (timestamp, current_price, analysis_text))
            conn.commit()
    
    def get_recent_news(self, hours: int = 24) -> pd.DataFrame:
        """최근 뉴스를 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT title, description, pub_date
                FROM news
                WHERE pub_date >= datetime('now', ?)
                ORDER BY pub_date DESC
            """
            return pd.read_sql_query(query, conn, params=(f'-{hours} hours',))
        
    def get_recent_news_limit(self, limit: int = 50) -> pd.DataFrame:
        """최근 뉴스를 limit 개수만큼 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT title, description, pub_date
                FROM news
                ORDER BY pub_date DESC
                LIMIT ?
            """
            return pd.read_sql_query(query, conn, params=(limit,))
    
    def get_market_data(self, hours: int = 24) -> pd.DataFrame:
        """최근 시장 데이터를 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT timestamp, current_price, opening_price, 
                       high_price, low_price, signed_change_rate
                FROM market_data
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
            """
            return pd.read_sql_query(query, conn, params=(f'-{hours} hours',))
    
    def get_latest_analyses(self) -> dict:
        """가장 최근의 모든 분석 결과를 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 각 분석 유형별로 가장 최근 결과를 가져옴
            news_analysis = cursor.execute("""
                SELECT timestamp, current_price, analysis_text
                FROM news_analysis
                ORDER BY timestamp DESC
                LIMIT 1
            """).fetchone()
            
            price_analysis = cursor.execute("""
                SELECT timestamp, current_price, analysis_text
                FROM price_analysis
                ORDER BY timestamp DESC
                LIMIT 1
            """).fetchone()
            
            final_decision = cursor.execute("""
                SELECT timestamp, current_price, analysis_text
                FROM final_decision
                ORDER BY timestamp DESC
                LIMIT 1
            """).fetchone()
            
            return {
                'news_analysis': {
                    'timestamp': news_analysis[0] if news_analysis else None,
                    'current_price': news_analysis[1] if news_analysis else None,
                    'analysis': news_analysis[2] if news_analysis else None
                },
                'price_analysis': {
                    'timestamp': price_analysis[0] if price_analysis else None,
                    'current_price': price_analysis[1] if price_analysis else None,
                    'analysis': price_analysis[2] if price_analysis else None
                },
                'final_decision': {
                    'timestamp': final_decision[0] if final_decision else None,
                    'current_price': final_decision[1] if final_decision else None,
                    'analysis': final_decision[2] if final_decision else None
                }
            }
    def get_latest_full_analysis(self):
        """가장 최근의 전체 분석 결과를 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = """
            SELECT 
                n.timestamp as news_timestamp,
                n.analysis_text as news_analysis,
                p.timestamp as price_timestamp,
                p.analysis_text as price_analysis,
                p.current_price,
                f.timestamp as final_timestamp,
                f.analysis_text as final_decision
            FROM news_analysis n
            JOIN price_analysis p ON date(n.timestamp) = date(p.timestamp)
            JOIN final_decision f ON date(p.timestamp) = date(f.timestamp)
            WHERE n.timestamp >= datetime('now', '-24 hours')
            ORDER BY n.timestamp DESC
            LIMIT 1;
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                return {
                    'news_timestamp': result[0],
                    'news_analysis': result[1],
                    'price_timestamp': result[2],
                    'price_analysis': result[3],
                    'current_price': result[4],
                    'final_timestamp': result[5],
                    'final_decision': result[6]
                }
            return None

    def get_all_analysis_results(self, hours=24):
        """모든 분석 결과(뉴스, 가격, 최종 결정)를 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            query = f"""
            SELECT 
                'news' as analysis_type,
                timestamp,
                analysis_text,
                NULL as current_price
            FROM news_analysis 
            WHERE timestamp >= datetime('now', '-{hours} hours')
            UNION ALL
            SELECT 
                'price' as analysis_type,
                timestamp,
                analysis_text,
                current_price
            FROM price_analysis
            WHERE timestamp >= datetime('now', '-{hours} hours')
            UNION ALL
            SELECT 
                'final' as analysis_type,
                timestamp,
                analysis_text,
                current_price
            FROM final_decision
            WHERE timestamp >= datetime('now', '-{hours} hours')
            ORDER BY timestamp DESC;
            """
            
            return pd.read_sql_query(query, conn)
    def get_analysis_data(self, hours=24):
        """최근 분석 결과와 투자 결정을 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
            SELECT 
                timestamp,
                current_price,
                analysis_text as decision,
                NULL as investment_ratio
            FROM final_decision
            WHERE timestamp >= datetime('now', ?) 
            ORDER BY timestamp DESC
            """
            df = pd.read_sql_query(query, conn, params=(f'-{hours} hours',))
            
            # 분석 텍스트에서 투자 비중 추출 (예: "투자 비중: 50%")
            df['investment_ratio'] = df['decision'].str.extract(r'투자\s*비중[:\s]*(\d+)').astype(float)
            
            return df

    def save_trade_execution(self, timestamp, trade_type, quantity, price, total_amount, order_id):
        """거래 실행 결과를 데이터베이스에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    INSERT INTO trade_executions 
                    (timestamp, trade_type, quantity, price, total_amount, order_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                
                cursor.execute(query, (
                    timestamp,
                    trade_type,
                    quantity,
                    price,
                    total_amount,
                    order_id
                ))
                
                conn.commit()
                print("거래 실행 결과가 성공적으로 저장되었습니다.")
                
        except Exception as e:
            print(f"거래 실행 결과 저장 중 오류 발생: {e}")