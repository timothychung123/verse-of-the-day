#!/usr/bin/env python3
"""
generate_verse.py — Generate a single Verse of the Day and publish to GitHub Pages.

Usage:
  python scripts/generate_verse.py                  # generates for today
  python scripts/generate_verse.py --date 2026-07-04  # generates for a specific date
  python scripts/generate_verse.py --no-push         # generate files only, skip git push
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "YOUR_GITHUB_USERNAME")
REPO_NAME       = "verse-of-the-day"
BASE_URL        = f"https://{GITHUB_USERNAME}.github.io/{REPO_NAME}"
ROOT            = Path(__file__).parent.parent  # project root

SYSTEM_PROMPT = """You are a warm, thoughtful Bible teacher writing a daily devotional for a modern audience.

Guidelines:
- Select a verse from ACROSS the entire Bible — Old and New Testament, Psalms, Proverbs, Prophets, Epistles, Gospels, Wisdom literature. Rotate broadly; do not repeat recent books.
- Always connect the verse back to Christ and the gospel, even for Old Testament passages.
- Write in a warm, accessible, conversational tone — never cold, preachy, or overly religious. Write as if explaining to a thoughtful friend.
- Include grounded, practical life application for someone living in the modern world.
- Keep the total article between 400–600 words across all four sections.
- Avoid clichés and Christianese jargon. Prefer concrete imagery over abstract platitudes.
- The prayer should feel personal and authentic, not formulaic.

You MUST respond with valid JSON only. No markdown fences, no extra text — raw JSON."""

USER_PROMPT = """Generate a Verse of the Day devotional. Return a JSON object with exactly these keys:

{
  "reference": "Book Chapter:Verse",
  "book": "Book name only",
  "text": "The exact verse text (ESV translation preferred)",
  "context": "2–3 paragraphs on historical and biblical context",
  "application": "2–3 paragraphs on practical application for today",
  "gospel": "2 paragraphs connecting this verse to Christ and the gospel",
  "prayer": "1–2 paragraphs as a closing prayer in first person"
}

Each paragraph should be wrapped in <p> tags in the JSON string values."""


def call_claude(extra_instruction: str = "") -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = USER_PROMPT
    if extra_instruction:
        prompt += f"\n\nAdditional instruction: {extra_instruction}"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Claude returned invalid JSON:\n{raw}", file=sys.stderr)
        raise e


def estimate_reading_time(text: str) -> int:
    words = len(text.split())
    return max(1, round(words / 200))


def build_share_text(reference: str, verse_text: str, url: str) -> str:
    plain = verse_text.replace("<p>", "").replace("</p>", " ").strip()
    return f'"{plain}" — {reference}\n\nRead today\'s reflection: {url}'


def render_template(template_path: Path, replacements: dict) -> str:
    html = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


def build_archive_card(entry: dict) -> str:
    preview = (entry["text"]
               .replace("<p>", "").replace("</p>", " ")
               .strip()[:160])
    date_obj = datetime.strptime(entry["date"], "%Y-%m-%d").date()
    date_display = date_obj.strftime("%B %-d, %Y")
    return (
        f'<a class="archive-card" href="verses/{entry["date"]}.html">\n'
        f'  <div class="card-date">{date_display}</div>\n'
        f'  <div class="card-ref">{entry["reference"]}</div>\n'
        f'  <p class="card-preview">{preview}&hellip;</p>\n'
        f'</a>\n'
    )


def update_archive(entry: dict):
    data_path = ROOT / "data" / "verses.json"
    data_path.parent.mkdir(exist_ok=True)
    entries = []
    if data_path.exists():
        entries = json.loads(data_path.read_text(encoding="utf-8"))

    # Remove existing entry for this date (idempotent re-runs)
    entries = [e for e in entries if e.get("date") != entry["date"]]
    entries.insert(0, entry)  # newest first
    data_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    # Rebuild archive.html
    cards_html = "\n".join(build_archive_card(e) for e in entries)
    archive_template = ROOT / "archive.html"
    archive_html = archive_template.read_text(encoding="utf-8")

    # Replace the placeholder block between the grid tags
    import re
    archive_html = re.sub(
        r'(<div class="archive-grid" id="archive-grid">).*?(</div>)',
        rf'\1\n      {cards_html}\n    \2',
        archive_html,
        flags=re.DOTALL
    )
    archive_template.write_text(archive_html, encoding="utf-8")
    print(f"  [archive] {len(entries)} total entries written to archive.html")


def generate(target_date: date, no_push: bool = False, extra: str = ""):
    print(f"[generate] Generating verse for {target_date}...")

    data = call_claude(extra_instruction=extra)
    print(f"  [claude]  {data['reference']} — {data['text'][:60]}...")

    date_str     = target_date.strftime("%Y-%m-%d")
    date_display = target_date.strftime("%B %-d, %Y")
    verse_plain  = (data["text"]
                    .replace("<p>", "").replace("</p>", " ").strip())
    verse_url    = f"{BASE_URL}/verses/{date_str}.html"
    share_text   = build_share_text(data["reference"], data["text"], verse_url)

    replacements = {
        "VERSE_REFERENCE":    data["reference"],
        "VERSE_TEXT":         data["text"],
        "VERSE_TEXT_PLAIN":   verse_plain,
        "DATE_DISPLAY":       date_display,
        "DATE_SLUG":          date_str,
        "BOOK_NAME":          data["book"],
        "READING_TIME":       estimate_reading_time(
                                  data["context"] + data["application"] +
                                  data["gospel"] + data["prayer"]),
        "SECTION_CONTEXT":    data["context"],
        "SECTION_APPLICATION":data["application"],
        "SECTION_GOSPEL":     data["gospel"],
        "SECTION_PRAYER":     data["prayer"],
        "SHARE_TEXT_ENCODED": quote(share_text),
        "PAGE_URL":           verse_url,
        "PAGE_URL_ENCODED":   quote(verse_url),
        "GITHUB_USERNAME":    GITHUB_USERNAME,
    }

    # Write the individual verse page
    verse_dir = ROOT / "verses"
    verse_dir.mkdir(exist_ok=True)
    verse_html = render_template(verse_dir / "template.html", replacements)
    out_path = verse_dir / f"{date_str}.html"
    out_path.write_text(verse_html, encoding="utf-8")
    print(f"  [file]    verses/{date_str}.html written")

    # If this is today, also update index.html
    if target_date == date.today():
        index_replacements = {**replacements, "PAGE_URL": f"{BASE_URL}/"}
        index_html = render_template(ROOT / "index.html", index_replacements)
        (ROOT / "index.html").write_text(index_html, encoding="utf-8")
        print(f"  [file]    index.html updated")

    # Update archive
    archive_entry = {
        "date":      date_str,
        "reference": data["reference"],
        "book":      data["book"],
        "text":      data["text"],
    }
    update_archive(archive_entry)

    if not no_push:
        git_commit_and_push(date_str, data["reference"])

    print(f"[done] {data['reference']} published for {date_str}")
    return data


def git_commit_and_push(date_str: str, reference: str):
    print("  [git]     staging and committing...")
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    msg = f"verse({date_str}): {reference}"
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("  [git]     pushed to origin/main")


def main():
    parser = argparse.ArgumentParser(description="Generate a Verse of the Day")
    parser.add_argument("--date", default=None,
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-push", action="store_true",
                        help="Skip git commit and push")
    parser.add_argument("--extra", default="",
                        help="Extra instruction to pass to Claude")
    args = parser.parse_args()

    target = (datetime.strptime(args.date, "%Y-%m-%d").date()
              if args.date else date.today())
    generate(target, no_push=args.no_push, extra=args.extra)


if __name__ == "__main__":
    main()
