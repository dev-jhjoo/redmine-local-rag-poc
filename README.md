# Redmine Local RAG PoC

Redmine PMS의 Issues 데이터를 CSV로 수동 Export 한 뒤, 로컬 환경에서 RAG 검색/질의응답을 테스트하는 PoC 프로젝트입니다.

## 구성

```text
Redmine Issues CSV
  → JSON 변환
  → Embedding 생성
  → Qdrant 저장
  → Local LLM 질의응답
```

## 1. Docker Compose 실행

```bash
docker compose up -d
```

## 2. 최초 1회 모델 설치

LLM 모델:

```bash
docker exec -it redmine-rag-ollama ollama pull qwen2.5:3b
```

Embedding 모델:

```bash
docker exec -it redmine-rag-ollama ollama pull nomic-embed-text
```

## 3. Python 환경 구성

Python 3.11 이상 권장

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

패키지 설치:

```bash
pip install -r requirements.txt
```

## 4. Redmine Issues CSV Export

Redmine 화면에서 Issues 데이터를 CSV로 다운로드합니다.

```text
Redmine → Project → Issues → CSV Export
```

다운로드한 CSV 파일을 아래 경로에 저장합니다.

```bash
mkdir -p data
cp ~/Downloads/issues.csv data/redmine_issues.csv
```

## 5. CSV를 JSON으로 변환

```bash
python3.11 scripts/sync_redmine_csv.py
```

생성된 JSON을 인덱싱 경로로 이동합니다.

```bash
mkdir -p data/raw
mv data/redmine_issues.json data/raw/issues.json
```

## 6. Vector Index 생성

```bash
python3.11 scripts/build_index.py
```

## 7. 질의 실행

```bash
python3.11 scripts/ask.py "KShot 관련 최근 장애 이슈 요약해줘"
```

예시:

```bash
python3.11 scripts/ask.py "Kafka timeout 관련 이슈 찾아줘"
python3.11 scripts/ask.py "3010 collector 장애 원인 알려줘"
python3.11 scripts/ask.py "Redis timeout 관련 장애 정리해줘"
```

## 전체 실행 순서 요약

```bash
docker compose up -d

docker exec -it redmine-rag-ollama ollama pull qwen2.5:3b
docker exec -it redmine-rag-ollama ollama pull nomic-embed-text

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p data
cp ~/Downloads/issues.csv data/redmine_issues.csv

python3.11 scripts/sync_redmine_csv.py

mkdir -p data/raw
mv data/redmine_issues.json data/raw/issues.json

python3.11 scripts/build_index.py

python3.11 scripts/ask.py "KShot 관련 최근 장애 이슈 요약해줘"
```