"""Merge verification agent results into verification JSON.

Reads raw verification results from .tmp/verify-{name}/*.json,
validates and normalizes them, then writes {name}-verification.json.

Supports two modes:
- normal: creates/overwrites verification.json with all results
- rescued: merges results into existing verification.json,
  replacing only RESCUED entries with new FIX/OK/DELETE results

Usage:
    uv run python scripts/merge_verification.py Ir-1
    uv run python scripts/merge_verification.py Ir-1 --rescued
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


def normalize_result(r: dict) -> dict:
    """Normalize field names from agent output."""
    # Map non-standard field names
    if "issues" in r and "problems" not in r:
        r["problems"] = r.pop("issues")
    if "reason" in r and "problems" not in r:
        reason = r.pop("reason")
        r["problems"] = [reason] if isinstance(reason, str) else reason
    if "reasons" in r and "problems" not in r:
        r["problems"] = r.pop("reasons")
    for alt in ("fix", "corrections", "suggested_changes"):
        if alt in r and "changes" not in r:
            r["changes"] = r.pop(alt)

    # Ensure problems is a list
    if "problems" not in r:
        r["problems"] = []
    if isinstance(r["problems"], str):
        r["problems"] = [r["problems"]]

    return r


def validate_result(r: dict) -> list[str]:
    """Validate a single result, return list of warnings."""
    warnings = []
    if "uuid" not in r:
        warnings.append("missing uuid")
    if "status" not in r:
        warnings.append("missing status")
    elif r["status"] not in ("OK", "FIX", "DELETE"):
        warnings.append(f"invalid status: {r['status']}")

    if r.get("status") in ("FIX", "DELETE"):
        problems = r.get("problems", [])
        if not problems or problems == [""] or problems == []:
            warnings.append(f"empty problems for {r.get('status')}")

    if r.get("status") == "FIX":
        changes = r.get("changes", {})
        if not changes:
            warnings.append("FIX without changes")

    return warnings


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


def collect_results(tmp_dir: Path) -> list[dict]:
    """Collect and normalize all results from agent output files."""
    result_files = sorted(tmp_dir.glob("*.json"))
    if not result_files:
        print(f"No result files in {tmp_dir}", file=sys.stderr)
        sys.exit(1)

    all_results: list[dict] = []
    for f in result_files:
        try:
            data = load_json(f)
            if isinstance(data, list):
                all_results.extend(data)
            elif isinstance(data, dict) and "uuid" in data:
                all_results.append(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Warning: skipping {f.name}: {e}", file=sys.stderr)

    # Normalize and validate
    warn_count = 0
    for r in all_results:
        normalize_result(r)
        warnings = validate_result(r)
        if warnings:
            warn_count += 1
            print(f"  Warning [{r.get('uuid', '?')}]: {', '.join(warnings)}", file=sys.stderr)

    if warn_count:
        print(f"  {warn_count} result(s) with warnings", file=sys.stderr)

    return all_results


def merge_normal(name: str, results: list[dict]) -> None:
    """Normal mode: create/overwrite verification.json."""
    v_path = INSTRUCTIONS_DIR / name / f"{name}-verification.json"

    v_data = {
        "instruction": name,
        "timestamp": datetime.now().isoformat(),
        "summary": recalculate_summary(results),
        "results": results,
    }

    save_json(v_path, v_data)

    s = v_data["summary"]
    rescued_info = f", {s['rescued']} rescued" if s.get('rescued', 0) > 0 else ""
    print(f"Weryfikacja {name}: {s['ok']} pytań OK, {s['fix']} do poprawy, {s['delete']} do usunięcia{rescued_info}")


def merge_rescued(name: str, new_results: list[dict]) -> None:
    """Rescued mode: replace RESCUED entries with new results, keep others."""
    v_path = INSTRUCTIONS_DIR / name / f"{name}-verification.json"

    if not v_path.exists():
        print(f"Error: {v_path} not found", file=sys.stderr)
        sys.exit(1)

    v_data = load_json(v_path)

    # Build lookup of new results by UUID
    new_by_uuid = {r["uuid"]: r for r in new_results}

    # Replace RESCUED entries with new results
    replaced = 0
    updated_results = []
    for entry in v_data["results"]:
        if entry["status"] == "RESCUED" and entry["uuid"] in new_by_uuid:
            updated_results.append(new_by_uuid[entry["uuid"]])
            replaced += 1
        else:
            updated_results.append(entry)

    v_data["results"] = updated_results
    v_data["summary"] = recalculate_summary(updated_results)
    v_data["timestamp"] = datetime.now().isoformat()

    save_json(v_path, v_data)

    s = v_data["summary"]
    rescued_info = f", {s['rescued']} RESCUED" if s.get('rescued', 0) > 0 else ""
    print(f"Weryfikacja RESCUED {name}: {replaced} zastąpionych — {s['ok']} OK, {s['fix']} FIX, {s['delete']} DELETE{rescued_info}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge verification agent results into verification JSON.",
    )
    parser.add_argument("name", help="Instruction name (e.g. Ir-1)")
    parser.add_argument(
        "--rescued",
        action="store_true",
        help="Rescued mode: merge into existing verification, replacing RESCUED entries",
    )
    args = parser.parse_args()

    tmp_dir = Path(f".tmp/verify-{args.name}")
    results = collect_results(tmp_dir)

    if not results:
        print("No valid results found", file=sys.stderr)
        sys.exit(1)

    if args.rescued:
        merge_rescued(args.name, results)
    else:
        merge_normal(args.name, results)


if __name__ == "__main__":
    main()
