"""Merge generated questions into verification JSON with NEW status.

Reads question JSON files from /tmp/add-questions-{instruction}/*.json,
creates verification entries with status NEW, and merges into
{instruction}-verification.json.

Usage:
    uv run python scripts/add_new_questions.py Ir-1
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def recalculate_summary(results: list[dict]) -> dict:
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "OK")
    fix = sum(1 for r in results if r["status"] == "FIX")
    delete = sum(1 for r in results if r["status"] == "DELETE")
    new = sum(1 for r in results if r["status"] == "NEW")
    return {"total": total, "ok": ok, "fix": fix, "delete": delete, "new": new}


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <instruction>")
        sys.exit(1)

    instruction = sys.argv[1]
    tmp_dir = Path(f"/tmp/add-questions-{instruction}")

    if not tmp_dir.exists():
        print(f"No temp directory found: {tmp_dir}")
        sys.exit(1)

    json_files = sorted(tmp_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {tmp_dir}")
        sys.exit(1)

    # Collect all new questions from agent outputs
    new_questions = []
    for f in json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                new_questions.extend(data)
            else:
                print(f"Warning: {f.name} is not a list, skipping")
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: failed to read {f.name}: {e}")

    if not new_questions:
        print("No new questions found in temp files")
        sys.exit(0)

    # Create verification entries with NEW status
    new_results = []
    for q in new_questions:
        uuid = q.get("uuid")
        if not uuid:
            print(f"Warning: question without uuid, skipping")
            continue

        new_results.append({
            "uuid": uuid,
            "status": "NEW",
            "problems": [],
            "changes": {
                "question": q.get("question", ""),
                "answers": q.get("answers", {}),
                "correct": q.get("correct", ""),
                "explanation": q.get("explanation", ""),
                "section_ref": q.get("section_ref", ""),
            },
        })

    # Load or create verification file
    base = INSTRUCTIONS_DIR / instruction
    v_path = base / f"{instruction}-verification.json"

    if v_path.exists():
        v_data = load_json(v_path)
    else:
        v_data = {
            "instruction": instruction,
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "results": [],
        }

    # Check for duplicate UUIDs
    existing_uuids = {r["uuid"] for r in v_data["results"]}
    added = 0
    for result in new_results:
        if result["uuid"] in existing_uuids:
            print(f"Warning: UUID {result['uuid']} already in verification, skipping")
            continue
        v_data["results"].append(result)
        existing_uuids.add(result["uuid"])
        added += 1

    v_data["summary"] = recalculate_summary(v_data["results"])
    save_json(v_path, v_data)

    print(f"Added {added} new questions to {v_path.name}")
    print(f"Summary: {v_data['summary']}")


if __name__ == "__main__":
    main()
