"""Apply verification fixes to questions JSON.

Reads {name}-verification.json, applies changes to {name}-pytania.json,
removes applied results from verification.

Usage:
    uv run python scripts/apply_verification.py Ir-1              # apply all
    uv run python scripts/apply_verification.py Ir-1 <uuid>       # apply one
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def recalculate_section_ref(q: dict) -> None:
    m = re.search(r"§\s*(\d+\w?)", q.get("explanation", ""))
    q["section_ref"] = f"§ {m.group(1)}" if m else None


def apply_one(
    questions: list[dict],
    result: dict,
) -> list[dict]:
    """Apply a single verification result. Returns updated questions list."""
    uuid = result["uuid"]
    status = result["status"]

    if status == "DELETE":
        questions = [q for q in questions if q["uuid"] != uuid]
    elif status == "NEW":
        changes = result.get("changes", {})
        if not changes:
            return questions
        new_q = {
            "uuid": uuid,
            "question": changes.get("question", ""),
            "answers": changes.get("answers", {}),
            "correct": changes.get("correct", ""),
            "explanation": changes.get("explanation", ""),
            "section_ref": changes.get("section_ref"),
        }
        recalculate_section_ref(new_q)
        questions.append(new_q)
    elif status == "FIX":
        changes = result.get("changes", {})
        if not changes:
            return questions
        for q in questions:
            if q["uuid"] != uuid:
                continue
            if "question" in changes:
                q["question"] = changes["question"]
            if "answers" in changes:
                q["answers"].update(changes["answers"])
            if "correct" in changes:
                q["correct"] = changes["correct"]
            if "explanation" in changes:
                q["explanation"] = changes["explanation"]
            recalculate_section_ref(q)
            break

    return questions


def recalculate_summary(results: list[dict]) -> dict:
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "OK")
    fix = sum(1 for r in results if r["status"] == "FIX")
    delete = sum(1 for r in results if r["status"] == "DELETE")
    new = sum(1 for r in results if r["status"] == "NEW")
    return {"total": total, "ok": ok, "fix": fix, "delete": delete, "new": new}


def apply_uuid(name: str, uuid: str) -> dict:
    """Apply a single UUID. Returns {"applied": status} or {"error": msg}."""
    base = INSTRUCTIONS_DIR / name
    v_path = base / f"{name}-verification.json"
    q_path = base / f"{name}-pytania.json"

    v_data = load_json(v_path)
    q_data = load_json(q_path)

    result = next((r for r in v_data["results"] if r["uuid"] == uuid), None)
    if result is None:
        return {"error": f"UUID {uuid} not found in verification"}

    if result["status"] not in ("FIX", "DELETE", "NEW"):
        return {"error": f"Cannot apply {result['status']} status"}

    q_data["questions"] = apply_one(q_data["questions"], result)

    v_data["results"] = [r for r in v_data["results"] if r["uuid"] != uuid]
    v_data["summary"] = recalculate_summary(v_data["results"])

    save_json(v_path, v_data)
    save_json(q_path, q_data)

    return {"applied": result["status"]}


def dismiss_uuid(name: str, uuid: str) -> dict:
    """Remove a UUID from verification without changing questions."""
    base = INSTRUCTIONS_DIR / name
    v_path = base / f"{name}-verification.json"

    v_data = load_json(v_path)

    result = next((r for r in v_data["results"] if r["uuid"] == uuid), None)
    if result is None:
        return {"error": f"UUID {uuid} not found in verification"}

    v_data["results"] = [r for r in v_data["results"] if r["uuid"] != uuid]
    v_data["summary"] = recalculate_summary(v_data["results"])

    save_json(v_path, v_data)

    return {"dismissed": result["status"]}


def apply_all(name: str) -> dict:
    """Apply all FIX/DELETE results. Returns summary of actions."""
    base = INSTRUCTIONS_DIR / name
    v_path = base / f"{name}-verification.json"
    q_path = base / f"{name}-pytania.json"

    v_data = load_json(v_path)
    q_data = load_json(q_path)

    to_apply = [r for r in v_data["results"] if r["status"] in ("FIX", "DELETE", "NEW")]

    fixed = 0
    deleted = 0
    added = 0
    for result in to_apply:
        q_data["questions"] = apply_one(q_data["questions"], result)
        if result["status"] == "FIX":
            fixed += 1
        elif result["status"] == "NEW":
            added += 1
        else:
            deleted += 1

    applied_uuids = {r["uuid"] for r in to_apply}
    v_data["results"] = [r for r in v_data["results"] if r["uuid"] not in applied_uuids]
    v_data["summary"] = recalculate_summary(v_data["results"])

    save_json(v_path, v_data)
    save_json(q_path, q_data)

    return {"fixed": fixed, "deleted": deleted, "added": added, "remaining": len(v_data["results"])}


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <name> [uuid]")
        sys.exit(1)

    name = sys.argv[1]
    if len(sys.argv) >= 3:
        uuid = sys.argv[2]
        result = apply_uuid(name, uuid)
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"Applied {result['applied']} for {uuid}")
    else:
        result = apply_all(name)
        print(f"Fixed: {result['fixed']}, Deleted: {result['deleted']}, Remaining: {result['remaining']}")


if __name__ == "__main__":
    main()
