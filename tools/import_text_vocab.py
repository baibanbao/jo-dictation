#!/usr/bin/env python3
"""Import built-in vocabulary from a plain text "English = Chinese" list."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


UNIT_RE = re.compile(r"^##\s*(8B\s+Unit\s+\d+)\s*[·\-]\s*(.+?)\s*$", re.I)
SECTION_RE = re.compile(r"^---\s*Section\s+([A-Z])\s*---$", re.I)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--html", nargs="+", default=[Path("index.html")], type=Path)
    args = parser.parse_args()

    items = parse_source(args.source)
    if not items:
        raise SystemExit(f"no vocabulary items found in {args.source}")

    for html_path in args.html:
        replace_builtins(html_path, items)
        print(f"updated {html_path} with {len(items)} built-in items")
    return 0


def parse_source(source: Path) -> list[dict[str, str]]:
    unit = ""
    section = ""
    raw_items: list[dict[str, str]] = []

    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or set(line) <= {"="}:
            continue

        unit_match = UNIT_RE.match(line)
        if unit_match:
            unit = clean_space(f"{unit_match.group(1)} {unit_match.group(2)}")
            section = ""
            continue

        if line.startswith("#"):
            continue

        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).upper()
            continue

        if " = " not in line:
            continue
        if not unit or not section:
            raise SystemExit(f"item before unit/section: {line}")

        text, cn = line.split(" = ", 1)
        text = clean_english(text)
        cn = clean_space(cn)
        if text:
            raw_items.append(
                {
                    "unit": unit,
                    "section": section,
                    "type": "phrase" if re.search(r"\s", text) else "word",
                    "text": text,
                    "cn": cn or text,
                }
            )

    used_ids: set[str] = set()
    items = []
    for index, item in enumerate(raw_items, start=1):
        items.append(
            {
                "id": make_id(item["unit"], index, item["text"], used_ids),
                "unit": item["unit"],
                "type": item["type"],
                "text": item["text"],
                "cn": item["cn"],
                "section": item["section"],
            }
        )
    return items


def clean_english(value: str) -> str:
    value = value.replace("\u00a0", " ")
    value = value.replace("’", "'").replace("“", '"').replace("”", '"')
    return clean_space(value)


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def make_id(unit: str, index: int, text: str, used_ids: set[str]) -> str:
    unit_match = re.search(r"Unit\s+(\d+)", unit, re.I)
    unit_part = f"u{unit_match.group(1)}" if unit_match else "u"
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "item"
    base = f"8b-{unit_part}-{index:03d}-{slug}"
    item_id = base
    suffix = 2
    while item_id in used_ids:
        item_id = f"{base}-{suffix}"
        suffix += 1
    used_ids.add(item_id)
    return item_id


def replace_builtins(html_path: Path, items: list[dict[str, str]]) -> None:
    html = html_path.read_text(encoding="utf-8")
    payload = json.dumps(items, ensure_ascii=False, indent=6)
    payload = "    const builtInItems = " + payload.replace("\n", "\n    ") + ";\n"
    pattern = re.compile(
        r"    const builtInItems = \[\n.*?\n    \];\n\n    let items = loadItems\(\);",
        re.S,
    )
    replacement = payload + "\n    let items = loadItems();"
    html, count = pattern.subn(replacement, html)
    if count != 1:
        raise SystemExit(f"could not replace builtInItems block in {html_path}")
    html_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
