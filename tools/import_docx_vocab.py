#!/usr/bin/env python3
"""Build the built-in vocabulary list from Jo's docx files."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


SECTION_RE = re.compile(r"^[A-Z]$")
UNIT_RE = re.compile(r"Unit\s+(\d+)", re.I)
BRACKET_RE = re.compile(r"\s*\[[^\]]+\]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--html", default=Path("index.html"), type=Path)
    parser.add_argument("--model", default="translategemma:4b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--batch-size", default=12, type=int)
    args = parser.parse_args()

    raw_items = extract_items(args.source)
    print(f"extracted {len(raw_items)} study items", flush=True)

    translations = translate_all(
        [item["text"] for item in raw_items],
        model=args.model,
        url=args.ollama_url,
        batch_size=args.batch_size,
    )

    used_ids: set[str] = set()
    items = []
    for index, (item, cn) in enumerate(zip(raw_items, translations), start=1):
        item_id = make_id(item["unit"], index, item["text"], used_ids)
        items.append(
            {
                "id": item_id,
                "unit": item["unit"],
                "type": "phrase" if re.search(r"\s", item["text"]) else "word",
                "text": item["text"],
                "cn": cn.strip() or item["text"],
            }
        )

    replace_builtins(args.html, items)
    print(f"updated {args.html} with {len(items)} built-in items", flush=True)
    return 0


def extract_items(source: Path) -> list[dict[str, str]]:
    files = sorted(
        source.glob("8B Unit *.docx"),
        key=lambda path: int(UNIT_RE.search(path.name).group(1)) if UNIT_RE.search(path.name) else 999,
    )
    if not files:
        raise SystemExit(f"no docx files found in {source}")

    items: list[dict[str, str]] = []
    for path in files:
        text = subprocess.check_output(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            text=True,
        )
        lines = text.splitlines()
        unit = lines[0].strip() if lines else path.stem
        section = ""
        for raw in lines[1:]:
            line = raw.strip()
            if not line:
                continue
            if SECTION_RE.fullmatch(line):
                section = line
                continue
            if not line.startswith("•"):
                continue
            phrase = clean_english(line[1:].strip())
            if phrase:
                items.append({"unit": unit, "section": section, "text": phrase})
    return items


def clean_english(value: str) -> str:
    value = BRACKET_RE.sub("", value)
    value = value.replace("\u00a0", " ")
    value = value.replace("’", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"\s+", " ", value).strip()
    return value


def translate_all(
    texts: list[str],
    *,
    model: str,
    url: str,
    batch_size: int,
) -> list[str]:
    translations: list[str] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        translated = translate_batch(batch, model=model, url=url)
        if len(translated) != len(batch):
            translated = [translate_one(text, model=model, url=url) for text in batch]
        translations.extend(translated)
        print(f"translated {len(translations)}/{len(texts)}", flush=True)
    return translations


def translate_batch(texts: list[str], *, model: str, url: str) -> list[str]:
    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(texts, start=1))
    prompt = (
        "Translate each numbered English study item into concise Simplified Chinese.\n"
        "Output exactly the same number of lines. Keep the line number at the start.\n"
        "Translate sb. as 某人 and sth. as 某物. Do not add explanations.\n"
        f"{numbered}"
    )
    response = ollama_generate(prompt, model=model, url=url)
    parsed = parse_numbered(response)
    return parsed[: len(texts)]


def translate_one(text: str, *, model: str, url: str) -> str:
    prompt = (
        "Translate into concise Simplified Chinese only. "
        "Translate sb. as 某人 and sth. as 某物. "
        f"English: {text}"
    )
    return clean_translation(ollama_generate(prompt, model=model, url=url))


def ollama_generate(prompt: str, *, model: str, url: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
                return str(data.get("response", "")).strip()
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise RuntimeError(f"ollama request failed: {exc}") from exc
            time.sleep(2)
    return ""


def parse_numbered(response: str) -> list[str]:
    values: list[str] = []
    for raw in response.splitlines():
        line = raw.strip()
        match = re.match(r"^\s*\d+\s*[.)、]\s*(.+)$", line)
        if match:
            values.append(clean_translation(match.group(1)))
    return values


def clean_translation(value: str) -> str:
    value = re.sub(r"^\s*[-*]\s*", "", value.strip())
    value = re.sub(r"^中文[:：]\s*", "", value)
    value = value.strip(" \t\r\n\"'`")
    return re.sub(r"\s+", " ", value)


def make_id(unit: str, index: int, text: str, used_ids: set[str]) -> str:
    unit_match = UNIT_RE.search(unit)
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
        raise SystemExit("could not replace builtInItems block")
    html_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
