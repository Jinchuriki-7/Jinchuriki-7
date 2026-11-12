#!/usr/bin/env python3
"""
Inspect and verify public contributions data directly from GitHub profile.
"""

import urllib.request
import re

def main():
    url = 'https://github.com/users/Jinchuriki-7/contributions'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8')

        # Total contributions text
        m_total = re.search(r'([\d,]+)\s+contributions\s+in\s+the\s+last\s+year', html)
        if m_total:
            print(f'Total in last year header: {m_total.group(1)}')

        # Match td with data-date and id
        tds = re.findall(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"', html)
        tooltips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', html, re.DOTALL))

        daily = {}
        for date_str, comp_id in tds:
            tip = tooltips.get(comp_id, '')
            cnt_match = re.search(r'(\d+)\s+contribution', tip)
            cnt = int(cnt_match.group(1)) if cnt_match else 0
            daily[date_str] = cnt

        print(f'Total dates parsed: {len(daily)}')
        print(f'Sum of parsed counts: {sum(daily.values())}')
        sorted_dates = sorted(daily.keys())
        print('Recent 10 days:')
        for d in sorted_dates[-10:]:
            print(f'  {d}: {daily[d]} contributions')

    except Exception as e:
        print(f'Error fetching contributions: {e}')

if __name__ == '__main__':
    main()
