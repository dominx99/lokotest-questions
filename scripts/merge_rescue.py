"""Merge rescue agent results into verification JSON.

Reads raw rescue results from /tmp/rescue-{name}/*.json,
updates {name}-verification.json: DELETE→RESCUED with changes,
or confirms DELETE.

Usage:
    uv run python scripts/merge_rescue.py Ir-1
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def load_json(path: Path) -> dict | list:
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
    rescued = sum(1 for r in results if r["status"] == "RESCUED")
    summary = {"total": total, "ok": ok, "fix": fix, "delete": delete}
    if rescued > 0:
        summary["rescued"] = rescued
    return summary


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <name>")
        sys.exit(1)

    name = sys.argv[1]
    tmp_dir = Path(f"/tmp/rescue-{name}")
    v_path = INSTRUCTIONS_DIR / name / f"{name}-verification.json"

    if not v_path.exists():
        print(f"Error: {v_path} not found")
        sys.exit(1)

    # Collect all rescue result files
    result_files = sorted(tmp_dir.glob("*.json"))
    if not result_files:
        print(f"No rescue results in {tmp_dir}")
        sys.exit(1)

    # Parse and flatten all results
    rescue_results: list[dict] = []
    for f in result_files:
        try:
            data = load_json(f)
            if isinstance(data, list):
                rescue_results.extend(data)
            elif isinstance(data, dict) and "uuid" in data:
                rescue_results.append(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Warning: skipping {f.name}: {e}", file=sys.stderr)

    if not rescue_results:
        print("No valid rescue results found")
        sys.exit(1)

    # Build lookup by UUID
    rescue_by_uuid = {}
    for r in rescue_results:
        uuid = r.get("uuid")
        if uuid:
            # Normalize field names
            if "issues" in r and "problems" not in r:
                r["problems"] = r.pop("issues")
            if "reason" in r and "problems" not in r:
                reason = r.pop("reason")
                r["problems"] = [reason] if isinstance(reason, str) else reason
            rescue_by_uuid[uuid] = r

    # Load and update verification
    v_data = load_json(v_path)

    rescued_count = 0
    confirmed_delete = 0

    for entry in v_data["results"]:
        if entry["status"] != "DELETE":
            continue
        uuid = entry["uuid"]
        rescue = rescue_by_uuid.get(uuid)
        if rescue is None:
            continue

        if rescue.get("status") == "RESCUED":
            entry["status"] = "RESCUED"
            entry["changes"] = rescue.get("changes", {})
            if rescue.get("problems"):
                entry["problems"] = rescue["problems"]
            rescued_count += 1
        else:
            # Confirmed DELETE — leave as is
            confirmed_delete += 1

    v_data["summary"] = recalculate_summary(v_data["results"])
    v_data["timestamp"] = datetime.now().isoformat()

    save_json(v_path, v_data)

    total_checked = rescued_count + confirmed_delete
    print(f"Rescue {name}: {rescued_count} uratowanych, {confirmed_delete} potwierdzonych DELETE (z {total_checked} sprawdzonych)")


if __name__ == "__main__":
    main()
