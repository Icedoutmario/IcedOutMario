#!/usr/bin/env python3
"""
Animated "jet over contribution graph" SVG for a GitHub profile README.

A jet flies left to right under your real contribution calendar and back
again, firing at your busiest days. Each hit flashes the cell and throws a
small shockwave. All motion is SMIL inside the SVG, so it plays on GitHub.

Data: GitHub GraphQL API. In GitHub Actions the built-in GITHUB_TOKEN is
enough (contribution calendars are public data), so no personal access
token is needed.

Env vars:
  GH_USERNAME   GitHub login (required)
  GITHUB_TOKEN  token for the GraphQL API (Actions provides this)
  OUTPUT_PATH   default: jet-heatmap.svg
  TERM_USER     name shown in the terminal title bar
  SAMPLE_DATA   path to a JSON list of {"date","count"} to render offline
Standard library only.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

USERNAME = os.environ.get("GH_USERNAME", "")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUTPUT = os.environ.get("OUTPUT_PATH", "jet-heatmap.svg")
TERM_USER = os.environ.get("TERM_USER") or USERNAME.lower() or "user"
SAMPLE = os.environ.get("SAMPLE_DATA")

# ---- layout ---------------------------------------------------------------
WEEKS = 53
CELL, GAP = 12, 3
STEP = CELL + GAP
PAD_L, PAD_R = 46, 24
BAR_H = 28                      # terminal title bar
GRID_Y = BAR_H + 34             # room for month labels
WIDTH = PAD_L + WEEKS * STEP - GAP + PAD_R
LANE_Y = GRID_Y + 7 * STEP + 46  # the jet's flight line
HEIGHT = LANE_Y + 30
LOOP = 22.0                     # seconds for one there-and-back pass
MAX_TARGETS = 18

# github dark palette
BG, BORDER, MUTED, TEXT = "#0d1117", "#30363d", "#7d8590", "#c9d1d9"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FLASH, BULLET, BLAST = "#aff5b4", "#7ee787", "#56d364"

QUERY = """query($login:String!){user(login:$login){contributionsCollection{
contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""


def fetch_days():
    if SAMPLE:
        with open(SAMPLE) as f:
            return json.load(f)
    if not USERNAME or not TOKEN:
        sys.exit("need GH_USERNAME and GITHUB_TOKEN (or SAMPLE_DATA)")
    body = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "jet-heatmap"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        sys.exit(json.dumps(data["errors"]))
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [{"date": d["date"], "count": d["contributionCount"]}
            for w in weeks for d in w["contributionDays"]]


def grid(days):
    """Place the last WEEKS weeks on a Sunday-first grid, like GitHub does."""
    by_date = {d["date"]: d["count"] for d in days}
    last = dt.date.fromisoformat(max(by_date)) if by_date else dt.date.today()
    first_sunday = last - dt.timedelta(days=(last.weekday() + 1) % 7) - dt.timedelta(weeks=WEEKS - 1)
    cells = []
    for col in range(WEEKS):
        for row in range(7):
            day = first_sunday + dt.timedelta(days=col * 7 + row)
            if day > last:
                continue
            cells.append({"col": col, "row": row, "date": day,
                          "count": by_date.get(day.isoformat(), 0)})
    return cells, first_sunday


def level(count, peak):
    if count <= 0:
        return 0
    if peak <= 4:
        return min(4, count)
    return 1 + min(3, int(3 * (count - 1) / max(1, peak - 1)) )


def f(n):
    return f"{n:.4f}".rstrip("0").rstrip(".")


def t_for(col, forward):
    """keyTime at which the jet sits under column `col` (0..0.5 out, 0.5..1 back)."""
    t = 0.02 + 0.46 * col / (WEEKS - 1)
    return t if forward else 1 - t


def cx(col):
    return PAD_L + col * STEP + CELL / 2


def build(days):
    cells, start = grid(days)
    total = sum(c["count"] for c in cells)
    peak = max([c["count"] for c in cells] + [0])
    targets = sorted([c for c in cells if c["count"] > 0],
                     key=lambda c: -c["count"])[:MAX_TARGETS]
    tkeys = {(c["col"], c["row"]) for c in targets}
    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
      f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">')
    # terminal window chrome
    a(f'<rect width="{WIDTH}" height="{HEIGHT}" rx="12" fill="{BG}"/>')
    a(f'<rect x=".5" y=".5" width="{WIDTH-1}" height="{HEIGHT-1}" rx="12" fill="none" stroke="{BORDER}"/>')
    a(f'<line x1="0" y1="{BAR_H}" x2="{WIDTH}" y2="{BAR_H}" stroke="{BORDER}"/>')
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        a(f'<circle cx="{18+15*i}" cy="14" r="4.5" fill="{c}"/>')
    a(f'<text x="{WIDTH/2}" y="18" fill="{MUTED}" font-size="11.5" text-anchor="middle">'
      f'{TERM_USER}@github: ~$ ./contributions.sh --jet</text>')

    # twinkling stars in the margins
    for x, y, d in [(14, 70, 1.3), (22, 120, 1.9), (12, 165, 1.5), (WIDTH-14, 72, 1.6),
                    (WIDTH-20, 118, 1.2), (WIDTH-12, 160, 2.1), (60, HEIGHT-12, 1.7),
                    (WIDTH-70, HEIGHT-12, 1.4), (WIDTH/2, HEIGHT-10, 2.3)]:
        a(f'<circle cx="{x}" cy="{y}" r="1.1" fill="#8b949e"><animate attributeName="opacity" '
          f'values=".15;1;.15" dur="{d}s" repeatCount="indefinite"/></circle>')

    # month + weekday labels
    starts = [col for col in range(WEEKS)
              if (start + dt.timedelta(weeks=col)).day <= 7]
    for i, col in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else WEEKS
        if nxt - col >= 3:
            d = start + dt.timedelta(weeks=col)
            a(f'<text x="{PAD_L + col*STEP}" y="{GRID_Y-9}" fill="{MUTED}" font-size="10">{d.strftime("%b")}</text>')
    for row, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        a(f'<text x="{PAD_L-8}" y="{GRID_Y + row*STEP + 9.5}" fill="{MUTED}" font-size="10" text-anchor="end">{name}</text>')

    # the grid
    for c in cells:
        x, y = PAD_L + c["col"] * STEP, GRID_Y + c["row"] * STEP
        fill = LEVELS[level(c["count"], peak)]
        rect = f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{fill}"'
        if (c["col"], c["row"]) in tkeys:
            t1, t2 = t_for(c["col"], True), t_for(c["col"], False)
            e = 0.008
            a(rect + f'><animate attributeName="fill" dur="{LOOP}s" repeatCount="indefinite" '
              f'keyTimes="0;{f(t1)};{f(t1+e)};{f(t1+4*e)};{f(t2)};{f(t2+e)};{f(t2+4*e)};1" '
              f'values="{fill};{fill};{FLASH};{fill};{fill};{FLASH};{fill};{fill}"/></rect>')
        else:
            a(rect + "/>")

    # bullets + shockwaves, fired on both passes
    for forward in (True, False):
        for c in targets:
            t = t_for(c["col"], forward)
            launch, hit = max(0.0, t - 0.018), t
            x = f(cx(c["col"]))
            ty = f(GRID_Y + c["row"] * STEP + CELL / 2)
            ly = LANE_Y - 16
            a(f'<circle cx="{x}" cy="{ly}" r="2.3" fill="{BULLET}" opacity="0">'
              f'<animate attributeName="cy" dur="{LOOP}s" repeatCount="indefinite" '
              f'keyTimes="0;{f(launch)};{f(hit)};1" values="{ly};{ly};{ty};{ty}"/>'
              f'<animate attributeName="opacity" dur="{LOOP}s" repeatCount="indefinite" '
              f'keyTimes="0;{f(max(0, launch-0.001))};{f(launch)};{f(hit)};{f(hit+0.002)};1" values="0;0;1;1;0;0"/></circle>')
            a(f'<circle cx="{x}" cy="{ty}" r="0" fill="none" stroke="{BLAST}" stroke-width="1.6" opacity="0">'
              f'<animate attributeName="r" dur="{LOOP}s" repeatCount="indefinite" '
              f'keyTimes="0;{f(hit)};{f(hit+0.02)};1" values="0;0;10;10"/>'
              f'<animate attributeName="opacity" dur="{LOOP}s" repeatCount="indefinite" '
              f'keyTimes="0;{f(hit-0.001)};{f(hit)};{f(hit+0.02)};1" values="0;0;1;0;0"/></circle>')

    # the jet
    x0, x1 = f(cx(0)), f(cx(WEEKS - 1))
    a(f'<g><g>'
      f'<polygon points="0,-17 8,5 4,2 -4,2 -8,5" fill="#58a6ff" stroke="#1f6feb"/>'
      f'<polygon points="-8,5 -15,12 -4,6" fill="#388bfd"/><polygon points="8,5 15,12 4,6" fill="#388bfd"/>'
      f'<circle cx="0" cy="-6" r="2.2" fill="#c9e6ff"/>'
      f'<polygon points="-3,6 3,6 0,15" fill="#f0883e"><animate attributeName="points" '
      f'values="-3,6 3,6 0,15;-3,6 3,6 0,20;-3,6 3,6 0,13;-3,6 3,6 0,15" dur=".2s" repeatCount="indefinite"/></polygon>'
      f'</g><animateTransform attributeName="transform" type="translate" dur="{LOOP}s" '
      f'repeatCount="indefinite" keyTimes="0;.02;.48;.52;.98;1" '
      f'values="{x0},{LANE_Y};{x0},{LANE_Y};{x1},{LANE_Y};{x1},{LANE_Y};{x0},{LANE_Y};{x0},{LANE_Y}"/></g>')

    # footer: total + legend
    fy = GRID_Y + 7 * STEP + 14
    a(f'<text x="{PAD_L}" y="{fy}" fill="{TEXT}" font-size="11.5" font-weight="700">'
      f'{total:,} contribution{"s" if total != 1 else ""} in the last year</text>')
    lx = WIDTH - PAD_R - 5 * STEP - 30
    a(f'<text x="{lx-6}" y="{fy}" fill="{MUTED}" font-size="10" text-anchor="end">Less</text>')
    for i, col in enumerate(LEVELS):
        a(f'<rect x="{lx + i*STEP}" y="{fy-10}" width="{CELL-2}" height="{CELL-2}" rx="2" fill="{col}"/>')
    a(f'<text x="{lx + 5*STEP + 2}" y="{fy}" fill="{MUTED}" font-size="10">More</text>')
    a("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    svg = build(fetch_days())
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT)), exist_ok=True)
    with open(OUTPUT, "w") as fh:
        fh.write(svg)
    print(f"wrote {OUTPUT} ({len(svg)/1024:.1f} KB)")
