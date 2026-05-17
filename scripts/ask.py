import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "redmine_issues")


def embed(text: str) -> list[float]:
    res = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    res.raise_for_status()
    return res.json()["embedding"]


def search(question: str, top_k: int = 5) -> list[Any]:
    client = QdrantClient(url=QDRANT_URL)
    vector = embed(question)
    return client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        limit=top_k,
        with_payload=True,
    )


def generate(question: str, contexts: list[Any]) -> str:
    context_text = "\n\n".join(
        f"[Issue #{hit.payload.get('issue_id')} / {hit.payload.get('subject')} / score={hit.score:.4f}]\n{hit.payload.get('text')}"
        for hit in contexts
    )

    prompt = f"""
너는 회사 Redmine PMS 데이터를 기반으로 답변하는 사내 기술 어시스턴트다.
아래 검색 결과 안에 있는 내용만 근거로 답변해라.
근거가 부족하면 '검색 결과만으로는 확실하지 않습니다'라고 말해라.
답변 마지막에는 참고한 Issue 번호를 목록으로 정리해라.

[검색 결과]
{context_text}

[질문]
{question}

[답변]
""".strip()

    res = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": 4096,
            },
        },
        timeout=300,
    )
    res.raise_for_status()
    return res.json()["response"]


def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        question = input("질문을 입력하세요: ").strip()

    results = search(question)
    answer = generate(question, results)
    print(answer)


if __name__ == "__main__":
    main()
