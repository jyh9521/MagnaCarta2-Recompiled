"""通用本地化记录检查；不假定游戏的实际文本编码或资源布局。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

TOKEN = re.compile(r"\{\d+\}|%(?:\d+\$)?[sdif]|\$n|\\n|<[^>]+>")
FIELDS = ("id", "resource", "context", "source_locale", "source", "translation", "status", "reviewer")


def validate(data):
    errors, seen = [], set()
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("entries"), list):
        return ["invalid catalog envelope"]
    for n, row in enumerate(data["entries"]):
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in FIELDS):
            errors.append(f"row {n}: missing or non-string field"); continue
        if not row["id"] or row["id"] in seen:
            errors.append(f"row {n}: empty or duplicate id")
        seen.add(row["id"])
        if not row["resource"] or not row["source_locale"]:
            errors.append(f"row {n}: missing provenance")
        if row["status"] not in ("untranslated", "draft", "reviewed"):
            errors.append(f"row {n}: invalid status")
        if row["status"] == "reviewed" and (not row["reviewer"].strip() or not row["translation"].strip()):
            errors.append(f"row {n}: reviewed requires translation and reviewer")
        if row["translation"] and Counter(TOKEN.findall(row["source"])) != Counter(TOKEN.findall(row["translation"])):
            errors.append(f"row {n}: protected token mismatch")
        if row["status"] == "untranslated" and row["translation"]:
            errors.append(f"row {n}: untranslated must be empty")
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("catalog", type=Path); args = p.parse_args()
    try:
        errors = validate(json.loads(args.catalog.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        p.exit(2, str(error) + "\n")
    for error in errors:
        print(error)
    if errors:
        p.exit(1)
    print("PASS catalog")


if __name__ == "__main__":
    main()
