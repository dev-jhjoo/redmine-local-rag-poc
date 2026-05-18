# scripts/sync_redmine_csv.py

import csv
import json
import os
from datetime import datetime
from pathlib import Path


CSV_PATH = Path(os.getenv("REDMINE_CSV_PATH", "data/issues.csv"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/redmine_issues.json"))


def normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("#", "id")


def get_value(row: dict, *keys: str) -> str:
    normalized = {normalize_key(k): v for k, v in row.items()}

    for key in keys:
        value = normalized.get(normalize_key(key))
        if value:
            return value.strip()

    return ""


def convert_csv_to_json():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    issues = []

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            issue_id = get_value(row, "#", "id", "issue id", "번호")
            subject = get_value(row, "Subject", "제목")
            description = get_value(row, "Description", "설명")
            project = get_value(row, "Project", "프로젝트")
            tracker = get_value(row, "Tracker", "유형", "트래커")
            status = get_value(row, "Status", "상태")
            priority = get_value(row, "Priority", "우선순위")
            author = get_value(row, "Author", "저자")
            assigned_to = get_value(row, "Assigned to", "담당자")
            created_on = get_value(row, "Created", "Created on", "등록")
            updated_on = get_value(row, "Updated", "Updated on", "변경")

            issues.append({
                "id": issue_id,
                "subject": subject,
                "description": description,
                "project": project,
                "project_id": None,
                "tracker": tracker,
                "status": status,
                "priority": priority,
                "author": author,
                "assigned_to": assigned_to,
                "created_on": created_on,
                "updated_on": updated_on,
                "closed_on": get_value(row, "Closed", "Closed on", "완료일"),
                "journals": [],
                "attachments": [],
                "url": "",
                "raw": row,
            })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "source": "redmine_csv",
        "csv_path": str(CSV_PATH),
        "count": len(issues),
        "issues": issues,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Converted {len(issues)} issues")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    convert_csv_to_json()