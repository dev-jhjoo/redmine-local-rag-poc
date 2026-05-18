import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from tqdm import tqdm

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "redmine_issues")
RAW_FILE = Path("data/redmine_issues.json")


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def get_name(value) -> str:
    if isinstance(value, dict):
        return str(value.get("name", ""))
    if value is None:
        return ""
    return str(value)

# def issue_to_text(issue: dict[str, Any]) -> str:
#     lines = [
#         f"Issue ID: {issue.get('id')}",
#         f"Project: {issue.get('project', {}).get('name', '')}",
#         f"Tracker: {issue.get('tracker', {}).get('name', '')}",
#         f"Status: {issue.get('status', {}).get('name', '')}",
#         f"Priority: {issue.get('priority', {}).get('name', '')}",
#         f"Author: {issue.get('author', {}).get('name', '')}",
#         f"Assigned To: {issue.get('assigned_to', {}).get('name', '')}",
#         f"Subject: {issue.get('subject', '')}",
#         f"Description: {clean_text(issue.get('description'))}",
#     ]

#     for journal in issue.get("journals", []):
#         notes = clean_text(journal.get("notes"))
#         if notes:
#             lines.append(
#                 f"Comment by {journal.get('user', {}).get('name', '')} at {journal.get('created_on', '')}: {notes}"
#             )

#     attachments = issue.get("attachments", [])
#     if attachments:
#         filenames = ", ".join(a.get("filename", "") for a in attachments)
#         lines.append(f"Attachments: {filenames}")

#     return "\n".join(lines)

def issue_to_text(issue: dict) -> str:
    journals = issue.get("journals", [])

    if isinstance(journals, list):
        journal_text = "\n".join(str(journal) for journal in journals)
    else:
        journal_text = str(journals or "")

    parts = [
        f"Issue ID: {issue.get('id', '')}",
        f"Project: {get_name(issue.get('project'))}",
        f"Tracker: {get_name(issue.get('tracker'))}",
        f"Status: {get_name(issue.get('status'))}",
        f"Priority: {get_name(issue.get('priority'))}",
        f"Author: {get_name(issue.get('author'))}",
        f"Assigned To: {get_name(issue.get('assigned_to'))}",
        f"Subject: {issue.get('subject', '')}",
        f"Description: {issue.get('description', '')}",
        f"Journals: {journal_text}",
        f"URL: {issue.get('url', '')}",
    ]

    return "\n".join(parts)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def embed(text: str) -> list[float]:
    res = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    res.raise_for_status()
    return res.json()["embedding"]


def stable_id(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def main() -> None:
    if not RAW_FILE.exists():
        raise RuntimeError("data/raw/issues.json not found. Run scripts/sync_redmine.py first.")

    # issues = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    raw_data = json.loads(RAW_FILE.read_text(encoding="utf-8"))

    if isinstance(raw_data, dict):
        issues = raw_data.get("issues", [])
    elif isinstance(raw_data, list):
        issues = raw_data
    else:
        raise RuntimeError("Invalid issues.json format")
    
    client = QdrantClient(url=QDRANT_URL)

    sample_vector = embed("dimension check")
    vector_size = len(sample_vector)

    # if client.collection_exists(QDRANT_COLLECTION):
    client.delete_collection(QDRANT_COLLECTION)

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    points: list[PointStruct] = []
    for issue in tqdm(issues, desc="Embedding issues"):
        full_text = issue_to_text(issue)
        for idx, chunk in enumerate(chunk_text(full_text)):
            vector = embed(chunk)
            issue_id = issue.get("id")
            point_id = stable_id(f"issue:{issue_id}:chunk:{idx}")
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "issue_id": issue_id,
                        "chunk_index": idx,
                        "subject": issue.get("subject", ""),
                        "project": get_name(issue.get("project")),
                        "tracker": get_name(issue.get("tracker")),
                        "status": get_name(issue.get("status")),
                        "updated_on": issue.get("updated_on", ""),
                        "text": chunk,
                    },
                )
            )

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    print(f"Indexed {len(points)} chunks into Qdrant collection '{QDRANT_COLLECTION}'")


if __name__ == "__main__":
    main()
