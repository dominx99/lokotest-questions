"""Apply verification fixes to Ir-1 questions JSON.

Reads Ir-1-pytania.json, deletes broken questions, fixes fixable ones,
writes updated Ir-1-pytania.json.
"""

import json
import re
from pathlib import Path

PYTANIA_PATH = Path("instructions/Ir-1/Ir-1-pytania.json")

# Questions to DELETE (1-indexed Q numbers)
# These are fundamentally broken: wrong instruction, wrong section, unsupported by text
DELETE_QNUMS = {
    # Wrong instruction (Ie-1, Ie-8, Ir-9)
    5, 69, 89, 90, 104, 109, 115, 205, 210,
    # Wrong section (content doesn't exist in referenced §)
    98, 130, 148, 159, 213,  # assigned to § 9 but wrong topic
    23, 37, 169, 183,  # ANP not in § 41
    121, 123, 127,  # § 17 ust. 7 doesn't exist (only 4 ust.)
    # Unsupported by text / unfixable
    6, 93,  # no speed limit in § 12 ust. 6 for this scenario
    126,  # Ir-3 not in § 28
    128, 129, 131, 147, 185,  # wrong topics in § 28
    135,  # wrong ust in § 7, unverifiable
    137,  # answer misinterprets regulation
    138,  # wrong topic in § 15 ust. 5
    143,  # answer lists 2 of 4 factors, debatable
    150,  # 3 errors in one question
    153,  # flawed premise about signals
    164,  # no basis in § 3 ust. 5
    166,  # answer mentions dyspozytor not in text
    172,  # not supported by § 66 text
    175, 182,  # not in provided text
    180,  # can't verify type 'S' from § 58
    189,  # not supported by § 10 ust. 2
    195,  # cross-references § 41 from § 11
    204,  # Pc6 not in § 32
    208,  # IRJ concept not in § 10
    215,  # can't verify from § 70-71
}


def fix_questions(questions: list[dict]) -> list[dict]:
    """Apply fixes to individual questions (by 1-indexed position)."""
    fixes_applied = []

    for i, q in enumerate(questions):
        qnum = i + 1  # 1-indexed

        # Q10: Fix broken distractor A ("co" -> proper answer)
        if qnum == 10:
            if q["answers"]["A"] == "co":
                q["answers"]["A"] = "Od warunków atmosferycznych i pory roku"
                fixes_applied.append(f"Q{qnum}: fixed broken distractor A")

        # Q59: "minimalna" -> "maksymalna" in question
        elif qnum == 59:
            q["question"] = q["question"].replace("minimalna", "maksymalna").replace("Minimalna", "Maksymalna")
            fixes_applied.append(f"Q{qnum}: fixed minimalna -> maksymalna")

        # Q68: "jazda manewrowa" -> "pociąg roboczy"
        elif qnum == 68:
            q["question"] = q["question"].replace(
                "jazdy manewrowej", "pociągu roboczego"
            ).replace(
                "jazda manewrowa", "pociąg roboczy"
            )
            fixes_applied.append(f"Q{qnum}: fixed jazda manewrowa -> pociąg roboczy")

        # Q110: explanation ust. 12 -> ust. 10
        elif qnum == 110:
            q["explanation"] = q["explanation"].replace("ust. 12", "ust. 10")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 12 -> ust. 10")

        # Q118: explanation ust. 3 -> ust. 1
        elif qnum == 118:
            q["explanation"] = q["explanation"].replace("ust. 3", "ust. 1")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 3 -> ust. 1")

        # Q134: correct answer A -> C (semafor wjazdowy, not wyjazdowy)
        elif qnum == 134:
            q["correct"] = "C"
            fixes_applied.append(f"Q{qnum}: fixed correct A -> C (semafor wjazdowy)")

        # Q139: explanation ust. 11 -> ust. 27
        elif qnum == 139:
            q["explanation"] = q["explanation"].replace("ust. 11", "ust. 27")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 11 -> ust. 27")

        # Q140: explanation ust. 4 -> ust. 3 pkt 1
        elif qnum == 140:
            q["explanation"] = q["explanation"].replace("ust. 4", "ust. 3 pkt 1")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 4 -> ust. 3 pkt 1")

        # Q141: explanation ust. 1 -> ust. 6
        elif qnum == 141:
            q["explanation"] = q["explanation"].replace("ust. 1", "ust. 6")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 1 -> ust. 6")

        # Q144: fix terminology and explanation
        elif qnum == 144:
            q["question"] = q["question"].replace("pełną", "szczegółową").replace("pełnej", "szczegółowej").replace("pełna", "szczegółowa")
            q["explanation"] = q["explanation"].replace("ust. 2", "ust. 1")
            fixes_applied.append(f"Q{qnum}: fixed próba pełna -> szczegółowa, ust. 2 -> ust. 1")

        # Q149: fix question and explanation
        elif qnum == 149:
            q["question"] = q["question"].replace(
                "drużyny trakcyjnej", "kabiny sterowniczej"
            ).replace(
                "drużynę trakcyjną", "kabinę sterowniczą"
            )
            q["explanation"] = q["explanation"].replace("ust. 5", "ust. 3 pkt 2")
            fixes_applied.append(f"Q{qnum}: fixed drużyny trakcyjnej -> kabiny sterowniczej, ust. 5 -> ust. 3 pkt 2")

        # Q165: explanation ust. 1 -> ust. 2
        elif qnum == 165:
            q["explanation"] = q["explanation"].replace("ust. 1", "ust. 2")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 1 -> ust. 2")

        # Q173: explanation ust. 3 pkt 2 -> ust. 3 pkt 1
        elif qnum == 173:
            q["explanation"] = q["explanation"].replace("pkt 2", "pkt 1")
            fixes_applied.append(f"Q{qnum}: fixed explanation pkt 2 -> pkt 1")

        # Q179: explanation ust. 1 -> ust. 7
        elif qnum == 179:
            q["explanation"] = q["explanation"].replace("ust. 1", "ust. 7")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 1 -> ust. 7")

        # Q187: explanation ust. 2 -> ust. 4
        elif qnum == 187:
            q["explanation"] = q["explanation"].replace("ust. 2", "ust. 4")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 2 -> ust. 4")

        # Q193: explanation ust. 2 -> ust. 6
        elif qnum == 193:
            q["explanation"] = q["explanation"].replace("ust. 2", "ust. 6")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 2 -> ust. 6")

        # Q194: explanation ust. 2 -> ust. 4
        elif qnum == 194:
            q["explanation"] = q["explanation"].replace("ust. 2", "ust. 4")
            fixes_applied.append(f"Q{qnum}: fixed explanation ust. 2 -> ust. 4")

    return fixes_applied


def recalculate_section_ref(q: dict) -> None:
    """Recalculate section_ref from explanation."""
    m = re.search(r"§\s*(\d+\w?)", q["explanation"])
    q["section_ref"] = f"§ {m.group(1)}" if m else None


def main() -> None:
    with open(PYTANIA_PATH) as f:
        data = json.load(f)

    questions = data["questions"]
    original_count = len(questions)
    print(f"Loaded {original_count} questions")

    # Apply fixes first (before deletion changes indices)
    fixes = fix_questions(questions)
    for fix in fixes:
        print(f"  FIX: {fix}")

    # Delete broken questions (by 1-indexed Q number)
    kept = []
    deleted_uuids = []
    for i, q in enumerate(questions):
        qnum = i + 1
        if qnum in DELETE_QNUMS:
            deleted_uuids.append(q["uuid"])
        else:
            kept.append(q)

    # Recalculate section_ref for all kept questions
    for q in kept:
        recalculate_section_ref(q)

    data["questions"] = kept

    # Write result
    PYTANIA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nDeleted: {len(deleted_uuids)} questions")
    print(f"Fixed: {len(fixes)} questions")
    print(f"Remaining: {len(kept)} questions")


if __name__ == "__main__":
    main()
