# Crypto Trading Analysis Bot

실시간으로 암호화폐 시장을 분석하고 투자 결정을 제안하는 AI 기반 트레이딩 봇입니다.

## 기능

- 실시간 비트코인 시장 데이터 수집
- LangChain과 GPT-4를 활용한 시장 분석
- LangSmith를 통한 분석 결과 모니터링
- 데이터베이스 저장 및 로깅

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/your-username/crypto-trading-bot.git
cd crypto-trading-bot
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
`.env` 파일을 생성하고 다음 값들을 설정하세요:
```
OPENAI_API_KEY=your_openai_api_key
LANGSMITH_API_KEY=your_langsmith_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
```

## 실행 방법

```bash
python analyze_market.py
```

## 주의사항

- 이 봇은 교육 및 연구 목적으로 제작되었습니다.
- 실제 트레이딩에 사용할 경우 발생하는 손실에 대해 책임지지 않습니다.
- API 키와 같은 민감한 정보는 절대로 GitHub에 커밋하지 마세요.

## 라이선스

MIT License