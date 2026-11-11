#!/usr/bin/env python3
"""
Custom GitHub Contribution Streak Generator
Author: Generated for Jinchuriki-7 (Farhanul Haque)
Timezone: Asia/Dhaka (UTC+6)
Last updated: 2026-11-11

This script:
1. Fetches contribution data via GitHub GraphQL API
2. Calculates streaks using Bangladesh timezone (Asia/Dhaka)
3. Generates a premium dark-themed SVG card
4. Writes the SVG to streak-card.svg
5. Saves a JSON summary for CI verification
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import pytz
    DHAKA_TZ = pytz.timezone("Asia/Dhaka")
except ImportError:
    # Fallback: UTC+6 offset without pytz
    DHAKA_TZ = datetime.timezone(datetime.timedelta(hours=6))


# ─── Constants ──────────────────────────────────────────────────────────────

GITHUB_USERNAME = "Jinchuriki-7"
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
OUTPUT_SVG = Path(__file__).parent.parent / "streak-card.svg"


# ─── GraphQL Query ───────────────────────────────────────────────────────────

def build_query(username: str, from_date: str, to_date: str) -> str:
    """Build GraphQL query for contribution calendar."""
    return """
    query {
      user(login: "%s") {
        contributionsCollection(from: "%sT00:00:00Z", to: "%sT23:59:59Z") {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """ % (username, from_date, to_date)


def fetch_contributions(token: str, username: str) -> dict:
    """
    Fetch up to 1 year of contribution data via GitHub GraphQL.

    GitHub's contributionCalendar returns dates in the format YYYY-MM-DD
    anchored to the viewer's local day boundary on GitHub's servers (UTC).
    We retrieve the raw counts per date string and then compare those date
    strings against today in Asia/Dhaka timezone.

    Returns: dict of {date_str: count} e.g. {"2026-11-07": 69}
    """
    # Fetch last 12 months to cover all possible streak scenarios
    if hasattr(DHAKA_TZ, 'localize'):
        now_dhaka = datetime.datetime.now(DHAKA_TZ)
    else:
        now_dhaka = datetime.datetime.now(DHAKA_TZ)

    today_dhaka = now_dhaka.date()
    one_year_ago = today_dhaka - datetime.timedelta(days=365)

    from_str = one_year_ago.isoformat()
    to_str = today_dhaka.isoformat()

    query = build_query(username, from_str, to_str)
    payload = json.dumps({"query": query}).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "streak-generator/1.0",
        "Accept": "application/vnd.github.v4+json",
    }

    req = urllib.request.Request(GRAPHQL_ENDPOINT, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"[ERROR] Network error: {e.reason}", file=sys.stderr)
        raise

    data = json.loads(raw)

    # Surface GraphQL errors
    if "errors" in data:
        for err in data["errors"]:
            print(f"[ERROR] GraphQL: {err.get('message')}", file=sys.stderr)
        raise RuntimeError("GraphQL returned errors")

    # Flatten weeks → days
    weeks = (
        data["data"]["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["weeks"]
    )
    total_from_api = (
        data["data"]["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["totalContributions"]
    )

    daily: dict[str, int] = {}
    for week in weeks:
        for day in week["contributionDays"]:
            date_str = day["date"]   # Always "YYYY-MM-DD" from GitHub API
            count = day["contributionCount"]
            daily[date_str] = daily.get(date_str, 0) + count

    print(f"[INFO] Fetched {len(daily)} contribution days (API total: {total_from_api})")
    print(f"[INFO] Date range: {from_str} → {to_str}")
    print(f"[INFO] Today in Dhaka timezone: {today_dhaka}")

    # Debug: show last 20 days
    sorted_days = sorted(daily.keys())
    print("[DEBUG] Last 20 days with contributions:")
    for d in sorted_days[-20:]:
        marker = " ← TODAY" if d == str(today_dhaka) else ""
        print(f"  {d}: {daily[d]}{marker}")

    return daily, today_dhaka, total_from_api


# ─── Streak Calculation ───────────────────────────────────────────────────────

def calculate_streaks(daily: dict, today: datetime.date) -> dict:
    """
    Calculate contribution streaks using contiguous calendar days.

    Rules:
    - A day "counts" if its contribution count > 0.
    - Today (in Dhaka TZ) is included if it has contributions; if not yet
      contributed today, the current streak still counts backward from yesterday.
    - Streaks are computed on date strings (YYYY-MM-DD) so there's no TZ drift.
    """
    if not daily:
        return {
            "total": 0,
            "current_streak": 0,
            "current_start": None,
            "current_end": None,
            "longest_streak": 0,
            "longest_start": None,
            "longest_end": None,
            "today": str(today),
        }

    # Build a sorted list of all dates we have data for
    all_dates = sorted(daily.keys())

    # Compute total from daily data (sum of actual counts)
    total = sum(daily.values())

    # ── Current Streak ────────────────────────────────────────────────────
    # Walk backward from today; skip today if 0 contributions (not yet contributed)
    current_streak = 0
    current_start = None
    current_end = None

    check_date = today
    today_str = str(today)

    # If today has contributions, count it; otherwise start from yesterday
    if daily.get(today_str, 0) > 0:
        current_streak = 1
        current_start = today
        current_end = today
        check_date = today - datetime.timedelta(days=1)
    else:
        # Today not contributed yet — start from yesterday
        check_date = today - datetime.timedelta(days=1)

    # Walk backward
    while True:
        d_str = str(check_date)
        if d_str < all_dates[0]:
            break
        count = daily.get(d_str, 0)
        if count > 0:
            current_streak += 1
            current_start = check_date
            if current_end is None:
                current_end = check_date
            check_date -= datetime.timedelta(days=1)
        else:
            break

    # ── Longest Streak ─────────────────────────────────────────────────────
    longest_streak = 0
    longest_start = None
    longest_end = None

    run_length = 0
    run_start = None
    prev_date = None

    for d_str in all_dates:
        d = datetime.date.fromisoformat(d_str)
        count = daily[d_str]

        if count > 0:
            if prev_date is not None and (d - prev_date).days == 1:
                # Consecutive day
                run_length += 1
            else:
                # Start a new run
                run_length = 1
                run_start = d

            if run_length > longest_streak:
                longest_streak = run_length
                longest_start = run_start
                longest_end = d

            prev_date = d
        else:
            # Zero contributions — reset run
            prev_date = None
            run_length = 0
            run_start = None

    return {
        "total": total,
        "current_streak": current_streak,
        "current_start": str(current_start) if current_start else None,
        "current_end": str(current_end) if current_end else None,
        "longest_streak": longest_streak,
        "longest_start": str(longest_start) if longest_start else None,
        "longest_end": str(longest_end) if longest_end else None,
        "today": str(today),
    }


# ─── Date Formatting ─────────────────────────────────────────────────────────

def fmt_date(date_str: str | None) -> str:
    """Format YYYY-MM-DD to 'Nov 7' style."""
    if not date_str:
        return "—"
    d = datetime.date.fromisoformat(date_str)
    return d.strftime("%-d %b").lstrip("0") if sys.platform != "win32" else d.strftime("%d %b").lstrip("0")


def fmt_date_range(start: str | None, end: str | None) -> str:
    """Format a date range like 'Oct 24 – Nov 9'."""
    if not start or not end:
        return "—"
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    if s == e:
        return _fmt(s)
    if s.year == e.year and s.month == e.month:
        return f"{s.day}–{_fmt(e)}"
    return f"{_fmt(s)} – {_fmt(e)}"


def _fmt(d: datetime.date) -> str:
    return d.strftime("%b %-d") if sys.platform != "win32" else d.strftime("%b %d").replace(" 0", " ")


# ─── SVG Generation ──────────────────────────────────────────────────────────

SVG_TEMPLATE = """\
<svg width="800" height="195" viewBox="0 0 800 195"
     xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="GitHub Contribution Streak for {username}">

  <title>GitHub Contribution Streak – {username}</title>

  <!-- Background -->
  <rect width="800" height="195" rx="12" ry="12" fill="#0D1117"/>

  <!-- Outer border glow -->
  <rect x="1" y="1" width="798" height="193" rx="11" ry="11"
        fill="none" stroke="#00D9FF" stroke-width="1" stroke-opacity="0.35"/>

  <!-- Dividers -->
  <line x1="267" y1="30" x2="267" y2="165" stroke="#21262D" stroke-width="1"/>
  <line x1="533" y1="30" x2="533" y2="165" stroke="#21262D" stroke-width="1"/>

  <!-- ── Column 1: Total Contributions ── -->
  <text x="133" y="58"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="13" fill="#8B949E" letter-spacing="1">TOTAL CONTRIBUTIONS</text>

  <text x="133" y="118"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="52" font-weight="700" fill="#FFFFFF">{total}</text>

  <text x="133" y="148"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="12" fill="#8B949E">{total_range}</text>

  <!-- ── Column 2: Current Streak ── -->
  <!-- Fire icon -->
  <text x="400" y="52"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="22">🔥</text>

  <text x="400" y="75"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="13" fill="#00D9FF" letter-spacing="1">CURRENT STREAK</text>

  <text x="400" y="128"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="52" font-weight="700" fill="#FFFFFF">{current}</text>

  <text x="400" y="143"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="12" fill="#8B949E">days</text>

  <text x="400" y="162"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="12" fill="#8B949E">{current_range}</text>

  <!-- ── Column 3: Longest Streak ── -->
  <text x="667" y="58"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="13" fill="#8B949E" letter-spacing="1">LONGEST STREAK</text>

  <text x="667" y="118"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="52" font-weight="700" fill="#FFFFFF">{longest}</text>

  <text x="667" y="143"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="12" fill="#8B949E">days</text>

  <text x="667" y="162"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="12" fill="#8B949E">{longest_range}</text>

  <!-- Footer: timezone label -->
  <text x="400" y="184"
        text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif"
        font-size="10" fill="#484F58">🕐 Asia/Dhaka (UTC+6) · Updated {updated}</text>

</svg>
"""


def generate_svg(stats: dict) -> str:
    """Render the premium streak SVG from stats dict."""
    today = datetime.date.fromisoformat(stats["today"])

    # Total range: "Jan 1 – Today"
    total_range = f"All time"

    # Current streak date range
    cs = stats["current_streak"]
    current_range = ""
    if cs > 0:
        current_range = fmt_date_range(stats["current_start"], stats["current_end"])

    # Longest streak date range
    ls = stats["longest_streak"]
    longest_range = ""
    if ls > 0:
        longest_range = fmt_date_range(stats["longest_start"], stats["longest_end"])

    updated = today.strftime("%b %d, %Y")

    svg = SVG_TEMPLATE.format(
        username=GITHUB_USERNAME,
        total=f"{stats['total']:,}",
        total_range=total_range,
        current=str(cs),
        current_range=current_range,
        longest=str(ls),
        longest_range=longest_range,
        updated=updated,
    )
    return svg


# ─── Fallback SVG (when API fails) ───────────────────────────────────────────

def generate_error_svg(message: str) -> str:
    """Generate a minimal error state SVG without destroying the existing card."""
    return """\
<svg width="800" height="195" viewBox="0 0 800 195"
     xmlns="http://www.w3.org/2000/svg">
  <rect width="800" height="195" rx="12" fill="#0D1117"/>
  <rect x="1" y="1" width="798" height="193" rx="11"
        fill="none" stroke="#FF6B6B" stroke-width="1" stroke-opacity="0.5"/>
  <text x="400" y="90" text-anchor="middle"
        font-family="'Segoe UI',Arial,sans-serif" font-size="14" fill="#8B949E">
    ⚠️ Streak data temporarily unavailable
  </text>
  <text x="400" y="115" text-anchor="middle"
        font-family="'Segoe UI',Arial,sans-serif" font-size="11" fill="#484F58">
    %s
  </text>
  <text x="400" y="140" text-anchor="middle"
        font-family="'Segoe UI',Arial,sans-serif" font-size="10" fill="#484F58">
    Will retry on next scheduled run · Asia/Dhaka timezone
  </text>
</svg>""" % message[:80]


# ─── Verification Helper ─────────────────────────────────────────────────────

def verify_nov7(daily: dict) -> None:
    """
    Verification check for November 7, 2026 contributions.
    This checks the API data only — never invents data.
    """
    target = "2026-11-07"
    count = daily.get(target)
    if count is None:
        print(f"[VERIFY] {target}: NOT found in fetched window (may be outside 1-year range)")
    elif count == 0:
        print(f"[VERIFY] {target}: found but 0 contributions — API exclusion confirmed")
    else:
        print(f"[VERIFY] {target}: {count} contributions ✓")
        if count == 69:
            print(f"[VERIFY] ✓ Matches expected 69 contributions exactly")
        else:
            print(f"[VERIFY] ⚠ Expected 69, got {count} — API may aggregate differently")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[ERROR] No GitHub token found. Set GH_TOKEN or GITHUB_TOKEN environment variable.", file=sys.stderr)
        # Generate a placeholder SVG rather than crashing
        svg = generate_error_svg("Missing GitHub token (GH_TOKEN)")
        OUTPUT_SVG.write_text(svg, encoding="utf-8")
        print(f"[INFO] Wrote placeholder SVG to {OUTPUT_SVG}")
        sys.exit(1)

    print(f"[INFO] Starting streak generation for {GITHUB_USERNAME}")
    print(f"[INFO] Token prefix: {token[:8]}...")

    try:
        daily, today, api_total = fetch_contributions(token, GITHUB_USERNAME)
    except Exception as e:
        print(f"[ERROR] Failed to fetch contributions: {e}", file=sys.stderr)
        # Preserve existing SVG if present, otherwise write error SVG
        if not OUTPUT_SVG.exists():
            svg = generate_error_svg(str(e)[:80])
            OUTPUT_SVG.write_text(svg, encoding="utf-8")
        print("[INFO] Preserved existing SVG due to fetch error")
        sys.exit(1)

    # Verification checks
    verify_nov7(daily)

    # Compute streaks
    stats = calculate_streaks(daily, today)

    print(f"\n[RESULTS]")
    print(f"  Total contributions : {stats['total']}")
    print(f"  Current streak      : {stats['current_streak']} days")
    print(f"  Current start       : {stats['current_start']}")
    print(f"  Current end         : {stats['current_end']}")
    print(f"  Longest streak      : {stats['longest_streak']} days")
    print(f"  Longest start       : {stats['longest_start']}")
    print(f"  Longest end         : {stats['longest_end']}")
    print(f"  Today (Dhaka)       : {stats['today']}")

    # Generate and write SVG
    svg = generate_svg(stats)
    OUTPUT_SVG.write_text(svg, encoding="utf-8")
    print(f"\n[INFO] SVG written to {OUTPUT_SVG}")

    # Emit a machine-readable summary for CI
    summary = {
        "username": GITHUB_USERNAME,
        "generated_at": str(today),
        "timezone": "Asia/Dhaka",
        **stats,
    }
    summary_path = OUTPUT_SVG.parent / "streak-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[INFO] Summary written to {summary_path}")


if __name__ == "__main__":
    main()

