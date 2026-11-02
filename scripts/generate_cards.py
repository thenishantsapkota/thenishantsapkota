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
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#58a6ff", "text": "#e6edf3",
             "muted": "#9198a1", "accent": "#f0883e", "ring": "#f0883e", "track": "#21262d"},
    "light": {"bg": "#ffffff", "border": "#d1d9e0", "title": "#0969da", "text": "#1f2328",
              "muted": "#59636e", "accent": "#bc4c00", "ring": "#fb8f44", "track": "#eff2f5"},
}
FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"


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
    .title {{ font-size: 18px; font-weight: 600; fill: {t['title']}; }}
    .label {{ font-size: 14px; fill: {t['muted']}; }}
    .value {{ font-size: 14px; font-weight: 600; fill: {t['text']}; }}
    .big {{ font-size: 28px; font-weight: 700; fill: {t['text']}; }}
    .hot {{ fill: {t['accent']}; }}
    .small {{ font-size: 12px; fill: {t['muted']}; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" fill="{t['bg']}" stroke="{t['border']}"/>
{body}
</svg>
"""


def stats_card(s, t):
    rows = [("⭐", "Total stars", s["stars"]), ("📦", "Commits (all time)", s["commits"]),
            ("🔀", "Pull requests", s["prs"]), ("🐞", "Issues", s["issues"]),
            ("👀", "Code reviews", s["reviews"]), ("🤝", "Contributed to (last year)", s["contributed"]),
            ("📁", "Public repos", s["repos"]), ("👥", "Followers", s["followers"])]
    body = [f'  <text x="25" y="38" class="title">{escape(s["name"])}\'s GitHub stats</text>']
    for i, (icon, label, value) in enumerate(rows):
        col, row = i % 2, i // 2
        x, y = 25 + col * 230, 78 + row * 32
        body.append(f'  <g class="fade" style="animation-delay:{i * 80}ms">'
                    f'<text x="{x}" y="{y}" class="label">{icon} {escape(label)}</text>'
                    f'<text x="{x + 205}" y="{y}" class="value" text-anchor="end">{value:,}</text></g>')
    return card(485, 215, t, f"{s['name']}'s GitHub stats", "\n".join(body))


def streak_card(s, t):
    st = streaks(s["days"], s["today"])
    cols = [
        (f"{st['total']:,}", "Total contributions", f"{fmt_date(st['first'])} - Present", False),
        (f"{st['current']:,}", "Current streak", " - ".join(filter(None, map(fmt_date, st["cur"]))) or "No active streak", True),
        (f"{st['longest']:,}", "Longest streak", " - ".join(filter(None, map(fmt_date, st["best"]))), False),
    ]
    body = []
    for i, (big, label, sub, hot) in enumerate(cols):
        cx = 81 + i * 162
        if hot:
            body.append(f'  <circle cx="{cx}" cy="70" r="40" fill="none" stroke="{t["ring"]}" stroke-width="5"/>'
                        f'<text x="{cx}" y="36" text-anchor="middle" font-size="18">🔥</text>')
        cls = "big hot" if hot else "big"
        y = 80 if hot else 74
        body.append(f'  <g class="fade" style="animation-delay:{i * 120}ms">'
                    f'<text x="{cx}" y="{y}" text-anchor="middle" class="{cls}">{big}</text>'
                    f'<text x="{cx}" y="{140 if hot else 108}" text-anchor="middle" class="value">{label}</text>'
                    f'<text x="{cx}" y="{162 if hot else 130}" text-anchor="middle" class="small">{escape(sub)}</text></g>')
    for x in (162, 324):
        body.append(f'  <line x1="{x}" y1="28" x2="{x}" y2="170" stroke="{t["border"]}"/>')
    return card(485, 195, t, "Contribution streak", "\n".join(body))


def langs_card(s, t):
    top = s["langs"][:8]
    total = sum(v["size"] for _, v in top) or 1
    body = ['  <text x="25" y="38" class="title">Most used languages</text>']
    x, w = 25, 435
    body.append(f'  <mask id="bar"><rect x="25" y="56" width="{w}" height="8" rx="4" fill="#fff"/></mask>'
                f'<g mask="url(#bar)">')
    for name, v in top:
        seg = v["size"] / total * w
        body.append(f'<rect x="{x:.2f}" y="56" width="{max(seg, 0.5):.2f}" height="8" fill="{v["color"]}"/>')
        x += seg
    body.append('</g>')
    for i, (name, v) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 230, 92 + row * 26
        body.append(f'  <g class="fade" style="animation-delay:{i * 60}ms">'
                    f'<circle cx="{lx + 5}" cy="{ly - 5}" r="5" fill="{v["color"]}"/>'
                    f'<text x="{lx + 16}" y="{ly}" class="label">{escape(name)}</text>'
                    f'<text x="{lx + 205}" y="{ly}" class="value" text-anchor="end">{v["size"] / total:.1%}</text></g>')
    height = 92 + ((len(top) + 1) // 2) * 26
    return card(485, height, t, "Most used languages", "\n".join(body))


def main():
    if not TOKEN:
        sys.exit("Set GITHUB_TOKEN (or GH_TOKEN) to read the GitHub API.")
    s = fetch()
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        (OUT / f"stats-{theme}.svg").write_text(stats_card(s, t), encoding="utf-8")
        (OUT / f"streak-{theme}.svg").write_text(streak_card(s, t), encoding="utf-8")
        (OUT / f"langs-{theme}.svg").write_text(langs_card(s, t), encoding="utf-8")
    st = streaks(s["days"], s["today"])
    print(f"Cards written to {OUT}: {st['total']:,} contributions, current streak {st['current']} days, "
          f"{s['stars']} stars, top language {s['langs'][0][0] if s['langs'] else 'n/a'}")


if __name__ == "__main__":
    main()
