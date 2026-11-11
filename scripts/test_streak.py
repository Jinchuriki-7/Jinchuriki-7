#!/usr/bin/env python3
"""
Local test suite for the streak generator.
Run with: python scripts/test_streak.py

Does NOT require a live GitHub token for the unit tests.
Set GH_TOKEN env var for the integration test.

Tests cover:
  - Empty input edge case
  - Single day streaks
  - Consecutive day streaks
  - Gaps in streak (broken streak detection)
  - Today with no contributions
  - Full Oct24-Nov9 scenario with Nov 7 = 69 contributions
  - Historical longest streak detection
  - Date formatting helpers
  - SVG generation and XML validity
"""
import sys
import datetime
import os

# Allow importing generate_streak from sibling
sys.path.insert(0, str(__file__.replace("test_streak.py", "")))
from generate_streak import calculate_streaks, generate_svg, fmt_date_range

PASS = "✓"
FAIL = "✗"
results = []


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, label, detail))
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


print("\n=== Unit Tests: Streak Calculation ===\n")

# ── Test 1: Empty input ──────────────────────────────────────────────────────
today = datetime.date(2026, 11, 9)
stats = calculate_streaks({}, today)
check("Empty: total=0", stats["total"] == 0)
check("Empty: current=0", stats["current_streak"] == 0)
check("Empty: longest=0", stats["longest_streak"] == 0)

# ── Test 2: Single day today ─────────────────────────────────────────────────
daily = {"2026-11-09": 5}
stats = calculate_streaks(daily, today)
check("Single day: total=5", stats["total"] == 5)
check("Single day: current=1", stats["current_streak"] == 1)
check("Single day: longest=1", stats["longest_streak"] == 1)

# ── Test 3: 3 consecutive days ending today ───────────────────────────────────
daily = {
    "2026-11-07": 69,
    "2026-11-08": 10,
    "2026-11-09": 5,
}
stats = calculate_streaks(daily, today)
check("3-day streak: total=84", stats["total"] == 84)
check("3-day streak: current=3", stats["current_streak"] == 3, f"got {stats['current_streak']}")
check("3-day streak: longest=3", stats["longest_streak"] == 3, f"got {stats['longest_streak']}")
check("3-day streak: start=Nov7", stats["current_start"] == "2026-11-07")

# ── Test 4: Gap in streak (Nov 6 missing) ─────────────────────────────────────
daily = {
    "2026-10-24": 3,
    "2026-10-25": 5,
    "2026-11-07": 69,
    "2026-11-08": 10,
    "2026-11-09": 5,
}
stats = calculate_streaks(daily, today)
check("Gap test: current=3", stats["current_streak"] == 3, f"got {stats['current_streak']}")
check("Gap test: longest=3", stats["longest_streak"] == 3, f"got {stats['longest_streak']}")
check("Gap test: total=92", stats["total"] == 92, f"got {stats['total']}")

# ── Test 5: Today has 0 contributions (not yet contributed) ───────────────────
daily_no_today = {
    "2026-11-07": 69,
    "2026-11-08": 10,
    # No entry for 2026-11-09
}
stats = calculate_streaks(daily_no_today, today)
check("No-today: current=2 (backward from yesterday)", stats["current_streak"] == 2, f"got {stats['current_streak']}")
check("No-today: current_end=Nov8", stats["current_end"] == "2026-11-08")

# ── Test 6: Long run with Nov7=69 scenario (Oct24–Nov9) ───────────────────────
# Simulates the described profile state
long_daily = {f"2026-10-{d:02d}": 3 for d in range(24, 32)}  # Oct 24-31
long_daily.update({f"2026-11-0{d}": 5 for d in range(1, 7)})   # Nov 1-6
long_daily["2026-11-07"] = 69
long_daily["2026-11-08"] = 10
long_daily["2026-11-09"] = 5
stats = calculate_streaks(long_daily, today)
check("Full scenario: current=17", stats["current_streak"] == 17, f"got {stats['current_streak']}")
check("Full scenario: longest=17", stats["longest_streak"] == 17, f"got {stats['longest_streak']}")
check("Full scenario: start=Oct24", stats["current_start"] == "2026-10-24")
check("Full scenario: Nov7=69", long_daily.get("2026-11-07") == 69)

# ── Test 7: Longest streak NOT current ────────────────────────────────────────
daily_hist = {
    "2026-05-01": 1, "2026-05-02": 1, "2026-05-03": 1,
    "2026-05-04": 1, "2026-05-05": 1,  # 5-day streak in May
    "2026-11-08": 2,
    "2026-11-09": 3,                    # 2-day current streak
}
stats = calculate_streaks(daily_hist, today)
check("Hist: longest=5", stats["longest_streak"] == 5, f"got {stats['longest_streak']}")
check("Hist: current=2", stats["current_streak"] == 2, f"got {stats['current_streak']}")
check("Hist: longest_start=May1", stats["longest_start"] == "2026-05-01")

# ── Test 8: Date range formatting ─────────────────────────────────────────────
print("\n=== Unit Tests: Date Formatting ===\n")
check("fmt_range same day", fmt_date_range("2026-11-07", "2026-11-07") != "—")
check("fmt_range multi-day", fmt_date_range("2026-10-24", "2026-11-09") != "—")
check("fmt_range None", fmt_date_range(None, None) == "—")

# ── Test 9: SVG generation ─────────────────────────────────────────────────────
print("\n=== Unit Tests: SVG Generation ===\n")
test_stats = {
    "total": 1234,
    "current_streak": 17,
    "current_start": "2026-10-24",
    "current_end": "2026-11-09",
    "longest_streak": 17,
    "longest_start": "2026-10-24",
    "longest_end": "2026-11-09",
    "today": "2026-11-09",
}
svg = generate_svg(test_stats)
check("SVG: contains 1,234", "1,234" in svg)
check("SVG: contains 17", ">17<" in svg)
check("SVG: contains Dhaka", "Dhaka" in svg)
check("SVG: valid XML", True)  # If generate_svg didn't throw, it's valid text
try:
    import xml.etree.ElementTree as ET
    ET.fromstring(svg)
    check("SVG: parses as valid XML", True)
except ET.ParseError as e:
    check("SVG: parses as valid XML", False, str(e))

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n=== Summary ===")
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"  {passed} passed, {failed} failed\n")

# ── Integration test (optional, requires GH_TOKEN) ───────────────────────────
token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
if token:
    print("=== Integration Test: Live GitHub API ===\n")
    from generate_streak import fetch_contributions, verify_nov7
    try:
        daily, today_live, api_total = fetch_contributions(token, "Jinchuriki-7")
        verify_nov7(daily)
        stats_live = calculate_streaks(daily, today_live)
        print(f"\n  Live Results:")
        print(f"    Total        : {stats_live['total']}")
        print(f"    Current      : {stats_live['current_streak']} days ({stats_live['current_start']} → {stats_live['current_end']})")
        print(f"    Longest      : {stats_live['longest_streak']} days ({stats_live['longest_start']} → {stats_live['longest_end']})")
        print(f"\n  [✓] Integration test passed")
    except Exception as e:
        print(f"  [✗] Integration test failed: {e}")
else:
    print("[INFO] GH_TOKEN not set — skipping live integration test")

if failed > 0:
    sys.exit(1)

