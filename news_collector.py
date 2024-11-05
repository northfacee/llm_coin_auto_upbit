# news_collector.py
import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv
from database_manager import DatabaseManager
import sqlite3

class NaverNewsCollector:
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('NAVER_CLIENT_ID')
        self.client_secret = os.getenv('NAVER_CLIENT_SECRET')
        self.db_manager = DatabaseManager()
        self.search_keywords = ["비트코인", "이더리움", "나스닥", "미국대선","일론머스크"]
        
        if not self.client_id or not self.client_secret:
            raise ValueError("네이버 API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    
    def collect_news(self, query: str, display: int = 10, start: int = 1) -> Dict:
        """네이버 뉴스 API를 통해 뉴스 수집"""
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": "date"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"뉴스 수집 중 오류 발생: {e}")
            return None

    def is_duplicate_news(self, title: str, pub_date: datetime) -> bool:
        """중복된 뉴스인지 확인"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM news 
                    WHERE title = ? AND pub_date = ?
                """, (title, pub_date))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            print(f"중복 확인 중 오류 발생: {e}")
            return False  # 에러 발생 시 중복이 아닌 것으로 처리
    
    def process_news_data(self, news_items: List[Dict]) -> List[Dict]:
        """뉴스 데이터 처리 및 포맷팅"""
        processed_news = []
        for item in news_items:
            title = item['title'].replace('<b>', '').replace('</b>', '')
            description = item['description'].replace('<b>', '').replace('</b>', '')
            pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900')
            
            if not self.is_duplicate_news(title, pub_date):
                processed_news.append({
                    'title': title,
                    'description': description,
                    'pub_date': pub_date
                })
            
        return processed_news
    
    def save_news(self, news_data: List[Dict]) -> bool:
        """뉴스 데이터를 데이터베이스에 저장"""
        try:
            for news_item in news_data:
                self.db_manager.save_news(
                    title=news_item['title'],
                    description=news_item['description'],
                    pub_date=news_item['pub_date']
                )
            return True
        except Exception as e:
            print(f"뉴스 저장 중 오류 발생: {e}")
            return False

def collect_and_save_news():
    """뉴스 수집 및 저장 실행"""
    try:
        collector = NaverNewsCollector()
        total_saved = 0
        
        for keyword in collector.search_keywords:
            print(f"\n{keyword} 관련 뉴스 수집 중...")
            news_response = collector.collect_news(keyword, display=10)
            
            if not news_response:
                print(f"{keyword} 뉴스 데이터를 가져오지 못했습니다.")
                continue
            
            news_items = collector.process_news_data(news_response['items'])
            if collector.save_news(news_items):
                print(f"{keyword}: {len(news_items)}개의 새로운 뉴스 기사 저장")
                total_saved += len(news_items)
                
                log_entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "keyword": keyword,
                    "news_count": len(news_items),
                    "news_data": [
                        {
                            "title": item['title'],
                            "description": item['description'],
                            "pub_date": item['pub_date'].strftime("%Y-%m-%d %H:%M:%S")
                        }
                        for item in news_items
                    ]
                }
                
                with open("news_collection_log.jsonl", 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        print(f"\n총 {total_saved}개의 새로운 뉴스 기사가 저장되었습니다.")
            
    except Exception as e:
        print(f"뉴스 수집 중 오류 발생: {e}")

if __name__ == "__main__":
    collect_and_save_news()