#!/usr/bin/env python3
"""Build the profile stat cards (stats, streak, top languages) as SVG files.

Runs in the daily workflow. Reads GitHub's GraphQL API with the token in
GITHUB_TOKEN and writes assets/<card>-dark.svg and assets/<card>-light.svg.
Standard library only, so the workflow needs no pip install.
"""

import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "thenishantsapkota")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
# Notebook byte counts are mostly cell output, so they drown out real code.
HIDE_LANGS = {l.strip() for l in os.environ.get("HIDE_LANGS", "Jupyter Notebook").split(",") if l.strip()}
OUT = Path(__file__).resolve().parent.parent / "assets"

THEMES = {
    # One accent across every card: GitHub's contribution green.
    "dark": {"bg": "#0d1117", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e",
             "accent": "#3fb950", "cells": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
              "accent": "#1a7f37", "cells": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]},
}
FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": f"{USER}-profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch():
    base = gql("""
      query($login: String!) {
        user(login: $login) {
          name login createdAt
          followers { totalCount }
          repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
          pullRequests { totalCount }
          issues { totalCount }
          repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
            totalCount
            nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } } } }
          }
        }
      }""", {"login": USER})["user"]

    created = dt.datetime.fromisoformat(base["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    days, commits, reviews = {}, 0, 0
    for year in range(created.year, now.year + 1):
        start = max(created, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
        end = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        c = gql("""
          query($login: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $login) { contributionsCollection(from: $from, to: $to) {
              totalCommitContributions restrictedContributionsCount totalPullRequestReviewContributions
              contributionCalendar { weeks { contributionDays { date contributionCount } } } } }
          }""", {"login": USER, "from": start.isoformat(), "to": end.isoformat()})["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        reviews += c["totalPullRequestReviewContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    langs = {}
    for repo in base["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n in HIDE_LANGS:
                continue
            langs.setdefault(n, {"size": 0, "color": e["node"]["color"] or "#8b949e"})
            langs[n]["size"] += e["size"]

    return {
        "name": base["name"] or base["login"],
        "stars": sum(r["stargazerCount"] for r in base["repositories"]["nodes"]),
        "commits": commits,
        "prs": base["pullRequests"]["totalCount"],
        "issues": base["issues"]["totalCount"],
        "reviews": reviews,
        "contributed": base["repositoriesContributedTo"]["totalCount"],
        "repos": base["repositories"]["totalCount"],
        "followers": base["followers"]["totalCount"],
        "days": dict(sorted(days.items())),
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]["size"]),
        "today": now.date().isoformat(),
    }


def streaks(days, today):
    items = [(d, n) for d, n in days.items() if d <= today]
    total = sum(n for _, n in items)
    longest, run, run_start, best = 0, 0, None, (None, None)
    for d, n in items:
        if n > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, best = run, (run_start, d)
        else:
            run = 0
    # Today's square can still be empty without breaking the streak.
    tail = items[:-1] if items and items[-1][1] == 0 else items
    current, cur_start, cur_end = 0, None, None
    for d, n in reversed(tail):
        if n == 0:
            break
        current += 1
        cur_start = d
        cur_end = cur_end or d
    return {"total": total, "first": items[0][0] if items else today, "current": current,
            "cur": (cur_start, cur_end), "longest": longest, "best": best}


def fmt_date(s):
    if not s:
        return ""
    d = dt.date.fromisoformat(s)
    return d.strftime("%b %-d, %Y")


def card(width, height, t, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <title>{escape(title)}</title>
  <style>
    text {{ font-family: {FONT}; }}
    .title {{ font-size: 15px; font-weight: 600; fill: {t['text']}; }}
    .label {{ font-size: 13px; fill: {t['muted']}; }}
    .value {{ font-size: 13px; font-weight: 600; fill: {t['text']}; font-family: {MONO}; }}
    .hero {{ font-size: 56px; font-weight: 600; fill: {t['text']}; letter-spacing: -.03em; }}
    .unit {{ font-size: 17px; fill: {t['muted']}; }}
    .line {{ font-size: 13px; fill: {t['muted']}; }}
    .line tspan.v {{ fill: {t['text']}; font-weight: 600; }}
    .tiny {{ font-size: 11px; fill: {t['muted']}; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" fill="{t['bg']}" stroke="{t['border']}"/>
{body}
</svg>
"""


def stats_card(s, t):
    rows = [("Stars", s["stars"]), ("Commits, all time", s["commits"]),
            ("Pull requests", s["prs"]), ("Issues", s["issues"]),
            ("Code reviews", s["reviews"]), ("Recently contributed to", s["contributed"]),
            ("Public repos", s["repos"]), ("Followers", s["followers"])]
    body = ['  <text x="24" y="36" class="title">GitHub stats</text>']
    for i, (label, value) in enumerate(rows):
        col, row = i % 2, i // 2
        x, y = 24 + col * 232, 74 + row * 30
        body.append(f'  <text x="{x}" y="{y}" class="label">{escape(label)}</text>'
                    f'<text x="{x + 206}" y="{y}" class="value" text-anchor="end">{value:,}</text>')
    return card(485, 196, t, "GitHub stats", "\n".join(body))


def streak_card(s, t, theme):
    st = streaks(s["days"], s["today"])
    days = s["days"]
    today = dt.date.fromisoformat(s["today"])
    best_day, best_n = max(days.items(), key=lambda kv: kv[1]) if days else ("", 0)
    target = (st["current"] // 100 + 1) * 100
    W, H = 840, 196

    num = f"{st['current']:,}"
    num_w = sum(12 if ch == "," else 27 for ch in num)  # 56px semibold digits, narrow comma
    since = fmt_date(st["cur"][0]) if st["cur"][0] else ""
    record = st["current"] > 0 and st["current"] >= st["longest"]
    tail = "My longest streak so far." if record else f"Longest: {st['longest']:,} days."
    note = f"Every day since {since}. {tail}"
    left = [
        f'<text x="28" y="44" class="title">Contribution streak</text>',
        f'<text x="26" y="104" class="hero">{num}</text>',
        f'<text x="{28 + num_w + 10:.0f}" y="104" class="unit">days</text>',
        f'<text x="28" y="132" class="line">{escape(note)}</text>',
    ]

    # The last 26 weeks, ending on this week's column, in GitHub's own green steps.
    weeks, cell, gap = 26, 12, 3
    end = today + dt.timedelta(days=(5 - today.weekday()) % 7)
    start = end - dt.timedelta(days=weeks * 7 - 1)
    gx = W - 28 - (weeks * (cell + gap) - gap)
    gy = 30
    peak = max([n for d, n in days.items() if d >= start.isoformat()] or [1])

    def step(n):
        if n <= 0:
            return 0
        r = n / peak
        return 1 if r < .2 else 2 if r < .45 else 3 if r < .7 else 4

    grid = []
    for i in range(weeks * 7):
        d = start + dt.timedelta(days=i)
        if d > today:
            continue
        x, y = gx + (i // 7) * (cell + gap), gy + (i % 7) * (cell + gap)
        ring = f' stroke="{t["text"]}" stroke-width="1.5"' if d == today else ""
        grid.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{t["cells"][step(days.get(d.isoformat(), 0))]}"{ring}/>')

    # One plain line of facts under a hairline. No labels in caps, no bars.
    fy = 172
    facts = (f'<text x="28" y="{fy}" class="line"><tspan class="v">{st["total"]:,}</tspan> contributions since '
             f'{dt.date.fromisoformat(st["first"]).strftime("%b %Y")}</text>')
    if best_day:
        facts += (f'<text x="{W // 2 - 60}" y="{fy}" class="line">Best day <tspan class="v">{best_n:,}</tspan> on '
                  f'{dt.date.fromisoformat(best_day).strftime("%b %-d, %Y")}</text>')
    facts += (f'<text x="{W - 28}" y="{fy}" class="line" text-anchor="end"><tspan class="v">{target - st["current"]}</tspan> '
              f'days to {target:,}</text>')
    rule = f'<line x1="28" y1="{fy - 24}" x2="{W - 28}" y2="{fy - 24}" stroke="{t["border"]}"/>'

    body = "\n  ".join(left + grid + [rule, facts])
    return card(W, H, t, f"{num}-day contribution streak", "  " + body)


def langs_card(s, t):
    top = s["langs"][:8]
    total = sum(v["size"] for _, v in top) or 1
    body = ['  <text x="25" y="36" class="title">Most used languages</text>']
    x, w = 25, 435
    body.append(f'  <mask id="bar"><rect x="25" y="54" width="{w}" height="6" rx="3" fill="#fff"/></mask>'
                f'<g mask="url(#bar)">')
    for name, v in top:
        seg = v["size"] / total * w
        body.append(f'<rect x="{x:.2f}" y="54" width="{max(seg - 2, 0.5):.2f}" height="6" fill="{v["color"]}"/>')
        x += seg
    body.append('</g>')
    for i, (name, v) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 230, 92 + row * 26
        body.append(f'  <g class="fade" style="animation-delay:{i * 60}ms">'
                    f'<rect x="{lx}" y="{ly - 9}" width="9" height="9" rx="2" fill="{v["color"]}"/>'
                    f'<text x="{lx + 16}" y="{ly}" class="label">{escape(name)}</text>'
                    f'<text x="{lx + 205}" y="{ly}" class="value" text-anchor="end">{v["size"] / total:.1%}</text></g>')
    height = 92 + ((len(top) + 1) // 2) * 26
    return card(485, height, t, "Most used languages", "\n".join(body))



RIDGE = {
    "dark": {"back": "#0e4429", "front": "#196c2e", "snow": "#e6edf3", "base": "#30363d"},
    "light": {"back": "#c6efce", "front": "#2da44e", "snow": "#e1e6eb", "base": "#d0d7de"},
}


def hero_card(s, t, theme):
    """Header banner: every month since joining GitHub is one peak in a mountain range.

    Peak height is that month's contributions. The busiest months get snow caps, and
    the highest one is labelled like a summit on a map. A taller, paler range behind
    uses the busiest month of each season, so the picture has depth.
    """
    r = RIDGE[theme]
    W, H = 840, 270
    left, right, base, top = 28, W - 28, H - 44, 96
    days = sorted((d, n) for d, n in s["days"].items() if d <= s["today"])
    start = dt.date.fromisoformat(days[0][0])
    today = dt.date.fromisoformat(s["today"])
    month_index = lambda d: (d.year - start.year) * 12 + d.month - start.month
    count = month_index(today) + 1
    series = [0] * count
    for d, n in days:
        series[month_index(dt.date.fromisoformat(d))] += n
    peak_i = max(range(count), key=lambda i: series[i])
    peak_n = series[peak_i] or 1
    step = (right - left) / count
    xs = [left + step * (i + .5) for i in range(count)]
    # Square root keeps the quiet early years visible next to the busy recent ones.
    hgt = lambda n: (n / peak_n) ** .5 * (base - top)

    def range_path(points, valley):
        """Peaks at each point, with a valley between neighbours, closed along the base."""
        d = [f"M{left},{base}"]
        prev = None
        for x, h in points:
            if prev is not None:
                px, ph = prev
                d.append(f"L{(px + x) / 2:.1f},{base - min(ph, h) * valley:.1f}")
            d.append(f"L{x:.1f},{base - h:.1f}")
            prev = (x, h)
        d.append(f"L{right},{base} Z")
        return " ".join(d)

    front = [(x, hgt(n)) for x, n in zip(xs, series)]
    season = [max(series[i:i + 3]) for i in range(0, count, 3)]
    back = [(left + step * (i * 3 + 1.5), min(hgt(n) * 1.12, base - top + 18)) for i, n in enumerate(season)]

    # Snow on the upper part of the busiest peaks.
    caps = []
    for i, (x, h) in enumerate(front):
        if series[i] < peak_n * .55:
            continue
        lv = min(front[i - 1][1], h) * .6 if i > 0 else 0
        rv = min(front[i + 1][1], h) * .6 if i + 1 < count else 0
        f = .3
        lx, ly = x - step / 2 * f, base - (h - (h - lv) * f)
        rx, ry = x + step / 2 * f, base - (h - (h - rv) * f)
        caps.append(f'<path d="M{lx:.1f},{ly:.1f} L{x:.1f},{base - h:.1f} L{rx:.1f},{ry:.1f} '
                    f'L{x + step * .05:.1f},{(ly + ry) / 2 - h * .04:.1f} L{x - step * .06:.1f},{(ly + ry) / 2 + 1:.1f} Z" fill="{r["snow"]}"/>')

    ticks = []
    for year in range(start.year + 1, today.year + 1):
        x = left + step * month_index(dt.date(year, 1, 1))
        ticks.append(f'<line x1="{x:.1f}" y1="{base + 1}" x2="{x:.1f}" y2="{base + 6}" stroke="{t["muted"]}"/>'
                     f'<text x="{x:.1f}" y="{base + 20}" class="tiny" text-anchor="middle">{year}</text>')

    px, py = xs[peak_i], base - hgt(peak_n)
    month_name = dt.date(start.year + (start.month - 1 + peak_i) // 12, (start.month - 1 + peak_i) % 12 + 1, 1).strftime("%B %Y")
    anchor, dx = ("end", -18) if px > W / 2 else ("start", 18)
    summit = (f'<path d="M{px:.1f},{py - 6:.1f} L{px:.1f},{py - 26:.1f} L{px + (-9 if anchor == "end" else 9):.1f},{py - 22:.1f} L{px:.1f},{py - 18:.1f}" '
              f'fill="{t["text"]}" stroke="{t["text"]}" stroke-width="1" stroke-linejoin="round"/>'
              f'<text x="{px + dx:.1f}" y="{py - 32:.1f}" class="summit" text-anchor="{anchor}">{peak_n:,} contributions</text>'
              f'<text x="{px + dx:.1f}" y="{py - 18:.1f}" class="tiny" text-anchor="{anchor}">{month_name}, the summit so far</text>')

    body = f"""  <style>
    .name {{ font-size: 46px; font-weight: 700; letter-spacing: -.025em; fill: {t['text']}; }}
    .sub {{ font-size: 16px; fill: {t['muted']}; }}
    .summit {{ font-size: 12px; font-weight: 600; fill: {t['text']}; }}
  </style>
  <text x="{left - 2}" y="64" class="name">Nishant Sapkota</text>
  <text x="{left}" y="92" class="sub">Developer from Nepal. TypeScript and Python, learning DevOps.</text>
  <path d="{range_path(back, .55)}" fill="{r['back']}"/>
  <path d="{range_path(front, .6)}" fill="{r['front']}"/>
  {''.join(caps)}
  <line x1="{left}" y1="{base + .5}" x2="{right}" y2="{base + .5}" stroke="{r['base']}"/>
  {''.join(ticks)}
  {summit}"""
    return card(W, H, t, "Nishant Sapkota. Each month of GitHub contributions since 2020 drawn as a mountain peak.", body)


# 5x7 pixel letters for the snake's name. "1" is a lit square.
GLYPHS = {
    "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
}
SNAKE = {
    "dark": {"cells": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "lit": "#3fb950",
             "dim": .3, "snake": "#8b949e", "head": "#e6edf3"},
    "light": {"cells": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "lit": "#1a7f37",
              "dim": .35, "snake": "#8c959f", "head": "#1f2328"},
}


def snake_card(s, theme, word=None):
    """A snake that crawls over the last year's graph and writes the name in lit squares."""
    word = (word or os.environ.get("SNAKE_WORD", "NISHANT")).upper()
    p = SNAKE[theme]
    weeks, rows, pitch, size, pad = 53, 7, 14, 11, 10
    gap_cols = 2
    word_cols = len(word) * 5 + (len(word) - 1) * gap_cols
    first_col = (weeks - word_cols) // 2
    lit = set()
    for i, ch in enumerate(word):
        g = GLYPHS.get(ch)
        if not g:
            sys.exit(f"No pixel glyph for {ch!r}; add it to GLYPHS.")
        for r, line in enumerate(g):
            for c, bit in enumerate(line):
                if bit == "1":
                    lit.add((first_col + i * (5 + gap_cols) + c, r))

    # The snake goes down one column and up the next, like a printer head, from
    # one column before the word to one after it.
    route = []
    for k, col in enumerate(range(first_col - 1, first_col + word_cols + 1)):
        rng = range(rows) if k % 2 == 0 else range(rows - 1, -1, -1)
        route += [(col, r) for r in rng]
    step = 0.045
    hold = 4.0  # the finished name stays up this long, and is what a still frame shows
    write = len(route) * step
    total = hold + write + 1.0
    h0 = hold / total
    when = {cell: hold + i * step for i, cell in enumerate(route)}

    today = dt.date.fromisoformat(s["today"])
    end = today + dt.timedelta(days=(5 - today.weekday()) % 7)
    start = end - dt.timedelta(days=weeks * 7 - 1)
    recent = [n for d, n in s["days"].items() if d >= start.isoformat()]
    peak = max(recent or [1])

    def level(n):
        if n <= 0:
            return 0
        r = n / peak
        return 1 if r < .2 else 2 if r < .45 else 3 if r < .7 else 4

    xy = lambda c, r: (pad + c * pitch, pad + r * pitch)
    cells = []
    for i in range(weeks * 7):
        c, r = divmod(i, 7)
        d = start + dt.timedelta(days=i)
        if d > today:
            continue
        x, y = xy(c, r)
        base = p["cells"][level(s["days"].get(d.isoformat(), 0))]
        if (c, r) in lit:
            f0 = when[(c, r)] / total
            f1 = f0 + 0.003
            kt = f"0;{h0:.4f};{h0 + 0.003:.4f};{f0:.4f};{f1:.4f};1"
            cells.append(
                f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="2" fill="{p["lit"]}">'
                f'<animate attributeName="fill" values="{p["lit"]};{p["lit"]};{base};{base};{p["lit"]};{p["lit"]}" '
                f'keyTimes="{kt}" dur="{total:.2f}s" repeatCount="indefinite"/>'
                f'<animate attributeName="opacity" values="1;1;{p["dim"]};{p["dim"]};1;1" '
                f'keyTimes="{kt}" dur="{total:.2f}s" repeatCount="indefinite"/></rect>')
        else:
            cells.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="2" fill="{base}" opacity="{p["dim"]}"/>')

    half = size / 2
    path = "M" + " L".join(f"{xy(c, r)[0] + half},{xy(c, r)[1] + half}" for c, r in route)
    w_frac = write / total
    segs = []
    body_len = 6
    for k in range(body_len - 1, -1, -1):
        lag = k * step / total
        sz = size + 1 if k == 0 else size - min(k, 4)
        color = p["head"] if k == 0 else p["snake"]
        segs.append(
            f'<rect x="{-sz / 2}" y="{-sz / 2}" width="{sz}" height="{sz}" rx="{sz / 3:.1f}" fill="{color}">'
            f'<animateMotion path="{path}" dur="{total:.2f}s" repeatCount="indefinite" calcMode="linear" '
            f'keyPoints="0;0;1;1" keyTimes="0;{h0 + lag:.4f};{h0 + w_frac + lag:.4f};1"/></rect>')
    done = h0 + w_frac + body_len * step / total
    fade = (f'<animate attributeName="opacity" values="0;0;1;1;0;0" '
            f'keyTimes="0;{h0 - 0.01:.4f};{h0:.4f};{done:.4f};{min(done + 0.03, 0.999):.4f};1" '
            f'dur="{total:.2f}s" repeatCount="indefinite"/>')

    W, H = pad * 2 + weeks * pitch - (pitch - size), pad * 2 + rows * pitch - (pitch - size)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="A snake writes {escape(word)} across the contribution graph">\n'
            f'  <title>{escape(word)}</title>\n  ' + "\n  ".join(cells) +
            f'\n  <g opacity="0">{fade}\n  ' + "\n  ".join(segs) + "\n  </g>\n</svg>\n")


def main():
    if not TOKEN:
        sys.exit("Set GITHUB_TOKEN (or GH_TOKEN) to read the GitHub API.")
    s = fetch()
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        (OUT / f"stats-{theme}.svg").write_text(stats_card(s, t), encoding="utf-8")
        (OUT / f"streak-{theme}.svg").write_text(streak_card(s, t, theme), encoding="utf-8")
        (OUT / f"langs-{theme}.svg").write_text(langs_card(s, t), encoding="utf-8")
        (OUT / f"snake-{theme}.svg").write_text(snake_card(s, theme), encoding="utf-8")
        (OUT / f"hero-{theme}.svg").write_text(hero_card(s, t, theme), encoding="utf-8")
    st = streaks(s["days"], s["today"])
    print(f"Cards written to {OUT}: {st['total']:,} contributions, current streak {st['current']} days, "
          f"{s['stars']} stars, top language {s['langs'][0][0] if s['langs'] else 'n/a'}")


if __name__ == "__main__":
    main()
