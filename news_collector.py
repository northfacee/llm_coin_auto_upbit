import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database_manager import DatabaseManager

class NaverNewsCollector:
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('NAVER_CLIENT_ID')
        self.client_secret = os.getenv('NAVER_CLIENT_SECRET')
        self.db_manager = DatabaseManager()
        
        if not self.client_id or not self.client_secret:
            raise ValueError("네이버 API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    
    def collect_news(self, query="비트코인", display=100, start=1):
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
            "sort": "date"  # 최신순으로 정렬
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"뉴스 수집 중 오류 발생: {e}")
            return None
    
    def process_news_data(self, news_items):
        """뉴스 데이터 처리 및 포맷팅"""
        processed_news = []
        for item in news_items:
            # HTML 태그 제거
            title = item['title'].replace('<b>', '').replace('</b>', '')
            description = item['description'].replace('<b>', '').replace('</b>', '')
            
            # 날짜 포맷 변환
            pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900')
            
            processed_news.append({
                'title': title,
                'description': description,
                'pub_date': pub_date
            })
            
        return processed_news
    
    def save_news(self, news_data):
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
        
        # 뉴스 수집
        news_response = collector.collect_news()
        if not news_response:
            print("뉴스 데이터를 가져오지 못했습니다.")
            return
        
        # 뉴스 데이터 처리
        news_items = collector.process_news_data(news_response['items'])
        
        # 뉴스 저장
        if collector.save_news(news_items):
            print(f"총 {len(news_items)}개의 뉴스 기사가 저장되었습니다.")
            
            # 로그 파일에 저장 (백업용)
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            
        else:
            print("뉴스 저장에 실패했습니다.")
            
    except Exception as e:
        print(f"뉴스 수집 중 오류 발생: {e}")

if __name__ == "__main__":
    collect_and_save_news()