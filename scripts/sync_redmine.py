import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth


"""
Redmine 계정/비밀번호 기반 동기화 스크립트

필수 .env 예시:

REDMINE_URL=https://redmine.company.com
REDMINE_USERNAME=my_username
REDMINE_PASSWORD=my_password

선택 .env:

REDMINE_PROJECT_ID=my_project
REDMINE_ISSUE_LIMIT=100
REDMINE_STATUS_ID=*
REDMINE_INCLUDE=journals,attachments
OUTPUT_PATH=data/redmine_issues.json

사용 예:

python scripts/sync_redmine.py
"""


load_dotenv()


REDMINE_URL = os.getenv("REDMINE_URL", "").rstrip("/")
REDMINE_USERNAME = os.getenv("REDMINE_USERNAME", "")
REDMINE_PASSWORD = os.getenv("REDMINE_PASSWORD", "")

PROJECT_ID = os.getenv("REDMINE_PROJECT_ID")
ISSUE_LIMIT = int(os.getenv("REDMINE_ISSUE_LIMIT", "100"))
STATUS_ID = os.getenv("REDMINE_STATUS_ID", "*")
INCLUDE = os.getenv("REDMINE_INCLUDE", "journals,attachments")
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/redmine_issues.json"))


def validate_env() -> None:
    missing = []

    if not REDMINE_URL:
        missing.append("REDMINE_URL")

    if not REDMINE_USERNAME:
        missing.append("REDMINE_USERNAME")

    if not REDMINE_PASSWORD:
        missing.append("REDMINE_PASSWORD")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def build_auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(REDMINE_USERNAME, REDMINE_PASSWORD)


def fetch_issues(offset: int = 0, limit: int = 100) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "offset": offset,
        "limit": limit,
        "status_id": STATUS_ID,
        "include": INCLUDE,
        "sort": "updated_on:desc",
    }

    if PROJECT_ID:
        params["project_id"] = PROJECT_ID

    response = requests.get(
        f"{REDMINE_URL}/issues.json",
        params=params,
        auth=build_auth(),
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    journals = issue.get("journals", [])
    attachments = issue.get("attachments", [])

    journal_texts: List[str] = []

    for journal in journals:
        notes = journal.get("notes")
        if notes:
            journal_texts.append(
                f"[{journal.get('created_on', '')}] "
                f"{journal.get('user', {}).get('name', 'unknown')}: {notes}"
            )

    attachment_infos = [
        {
            "id": attachment.get("id"),
            "filename": attachment.get("filename"),
            "filesize": attachment.get("filesize"),
            "content_type": attachment.get("content_type"),
            "content_url": attachment.get("content_url"),
        }
        for attachment in attachments
    ]

    return {
        "id": issue.get("id"),
        "subject": issue.get("subject"),
        "description": issue.get("description"),
        "project": issue.get("project", {}).get("name"),
        "project_id": issue.get("project", {}).get("id"),
        "tracker": issue.get("tracker", {}).get("name"),
        "status": issue.get("status", {}).get("name"),
        "priority": issue.get("priority", {}).get("name"),
        "author": issue.get("author", {}).get("name"),
        "assigned_to": issue.get("assigned_to", {}).get("name"),
        "created_on": issue.get("created_on"),
        "updated_on": issue.get("updated_on"),
        "closed_on": issue.get("closed_on"),
        "journals": journal_texts,
        "attachments": attachment_infos,
        "url": f"{REDMINE_URL}/issues/{issue.get('id')}",
        "raw": issue,
    }


def sync_redmine() -> List[Dict[str, Any]]:
    validate_env()

    print("Redmine sync started")
    print(f"URL: {REDMINE_URL}")
    print(f"PROJECT_ID: {PROJECT_ID or '(all accessible projects)'}")
    print(f"ISSUE_LIMIT: {ISSUE_LIMIT}")
    print(f"STATUS_ID: {STATUS_ID}")
    print(f"INCLUDE: {INCLUDE}")

    issues: List[Dict[str, Any]] = []
    offset = 0
    page_size = min(100, ISSUE_LIMIT)

    while len(issues) < ISSUE_LIMIT:
        remaining = ISSUE_LIMIT - len(issues)
        current_limit = min(page_size, remaining)

        data = fetch_issues(offset=offset, limit=current_limit)
        fetched = data.get("issues", [])

        if not fetched:
            break

        normalized = [normalize_issue(issue) for issue in fetched]
        issues.extend(normalized)

        print(f"Fetched {len(issues)} / {ISSUE_LIMIT}")

        total_count = data.get("total_count", 0)
        offset += current_limit

        if offset >= total_count:
            break

    return issues


def save_issues(issues: List[Dict[str, Any]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "redmine_url": REDMINE_URL,
        "project_id": PROJECT_ID,
        "count": len(issues),
        "issues": issues,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved to {OUTPUT_PATH}")


def main() -> None:
    try:
        issues = sync_redmine()
        save_issues(issues)
        print("Redmine sync completed")
    except requests.HTTPError as error:
        status_code = error.response.status_code if error.response else "unknown"
        body = error.response.text[:500] if error.response is not None else ""

        print(f"HTTP error occurred. status={status_code}")
        print(body)
        raise
    except Exception as error:
        print(f"Sync failed: {error}")
        raise


if __name__ == "__main__":
    main()
