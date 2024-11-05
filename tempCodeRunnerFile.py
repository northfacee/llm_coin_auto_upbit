    def get_transaction_history(self, symbol: str) -> Optional[List[Dict]]:
        """최근 체결 내역 조회"""
        try:
            url = f"{self.base_url}/public/transaction_history/{symbol}_KRW"
            print(f"요청 URL: {url}")
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != '0000':
                print(f"API 에러: {data.get('message', '알 수 없는 에러')}")
                return None
            
            return data['data']
            
        except Exception as e:
            print(f"체결 내역 조회 실패: {e}")
            return None