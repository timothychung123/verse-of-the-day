#!/usr/bin/env python3
"""
generate_weekly.py — Generate 5 verses scheduled for Mon–Fri of the current (or next) week.

Usage:
  python scripts/generate_weekly.py              # schedules Mon–Fri starting next Monday
  python scripts/generate_weekly.py --this-week  # schedules Mon–Fri of THIS week
  python scripts/generate_weekly.py --no-push    # generate files only, skip git push
  python scripts/generate_weekly.py --start 2026-07-07  # start from a specific Monday
"""

import argparse
import time
from datetime import date, timedelta, datetime

from generate_verse import generate


def next_monday(ref: date) -> date:
    days_ahead = (7 - ref.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # if today is Monday, start NEXT Monday
    return ref + timedelta(days=days_ahead)


def this_monday(ref: date) -> date:
    return ref - timedelta(days=ref.weekday())


def weekdays_from(start: date, count: int = 5) -> list[date]:
    days = []
    d = start
    while len(days) < count:
        if d.weekday() < 5:  # Monday=0 … Friday=4
            days.append(d)
        d += timedelta(days=1)
    return days


def main():
    parser = argparse.ArgumentParser(description="Generate a week of verses")
    parser.add_argument("--this-week", action="store_true",
                        help="Generate for Mon–Fri of the current week")
    parser.add_argument("--no-push", action="store_true",
                        help="Skip git commit/push after each verse")
    parser.add_argument("--start", default=None,
                        help="Start date YYYY-MM-DD (should be a Monday)")
    parser.add_argument("--delay", type=int, default=8,
                        help="Seconds to wait between API calls (default: 8)")
    args = parser.parse_args()

    today = date.today()
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    elif args.this_week:
        start = this_monday(today)
    else:
        start = next_monday(today)

    targets = weekdays_from(start, count=5)

    print(f"[weekly] Generating verses for the week of {start.strftime('%B %-d, %Y')}")
    print(f"         Dates: {', '.join(str(d) for d in targets)}")
    print()

    results = []
    for i, d in enumerate(targets, 1):
        print(f"── [{i}/5] {d} ─────────────────────────────────────────")
        try:
            data = generate(d, no_push=args.no_push)
            results.append((d, data["reference"], "✓"))
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append((d, "—", "✗"))
        if i < 5:
            print(f"  [wait]  sleeping {args.delay}s before next call...")
            time.sleep(args.delay)
        print()

    print("═" * 52)
    print("Weekly generation complete:")
    for d, ref, status in results:
        print(f"  {status}  {d}  {ref}")


if __name__ == "__main__":
    main()
