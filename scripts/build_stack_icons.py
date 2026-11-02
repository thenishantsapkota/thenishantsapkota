#!/usr/bin/env python3
"""Build the tech-stack icon rows in assets/stack-*.svg.

Icons that skillicons.dev has are copied from it. The ones it doesn't have
(JWT, Socket.io, Keras, ...) are drawn here in the same style: a 256x256
rounded tile with the brand logo from Simple Icons. Each row is saved in the
repo, so the README never depends on these services at view time.

Run it again after editing ROWS:  python3 scripts/build_stack_icons.py
"""

import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets"
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/{}.svg"
TILE = "#242938"  # skillicons' dark tile colour

# Custom tiles: name -> (Simple Icons slug, logo colour readable on the dark tile)
CUSTOM = {
    "drf": ("django", "#FF1709"),
    "jwt": ("jsonwebtokens", "#FB015B"),
    "socketio": ("socketdotio", "#FFFFFF"),
    "swagger": ("swagger", "#85EA2D"),
    "keras": ("keras", "#D00000"),
    "numpy": ("numpy", "#4DABCF"),
    "pandas": ("pandas", "#E70488"),
    "jira": ("jira", "#2684FF"),
    "glitch": ("glitch", "#7A7AFF"),
    "gimp": ("gimp", "#A39A80"),
    "canva": ("canva", "#00C4CC"),
}

ROWS = {
    "languages": ["ts", "js", "py", "java", "cpp", "dart", "html", "css", "md"],
    "frameworks": ["nodejs", "nestjs", "express", "django", "drf", "fastapi", "flask", "flutter", "bootstrap", "socketio"],
    "databases": ["postgres", "mysql", "mongodb", "sqlite", "redis"],
    "devops": ["docker", "linux", "githubactions", "vercel", "firebase", "glitch", "postman", "swagger", "jwt", "npm", "yarn", "jira"],
    "ml": ["tensorflow", "keras", "sklearn", "numpy", "pandas"],
    "design": ["ps", "gimp", "figma", "canva"],
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stack-icons"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def skillicon(name):
    svg = get(f"https://skillicons.dev/icons?i={name}")
    inner = re.search(r'<g transform="translate\(0, 0\)">\s*(.*?)\s*</g>\s*</svg>\s*$', svg, re.S)
    if not inner:
        raise SystemExit(f"skillicons has no icon called {name!r}")
    return inner.group(1)


def custom_tile(name):
    slug, color = CUSTOM[name]
    path = re.search(r'<path d="([^"]+)"', get(SIMPLE_ICONS.format(slug))).group(1)
    # Simple Icons draw on a 24-unit grid; scale to a 152-unit logo centred on the tile.
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" fill="none" viewBox="0 0 256 256">'
            f'<rect width="256" height="256" fill="{TILE}" rx="60"/>'
            f'<g transform="translate(52 52) scale(6.3333)"><path fill="{color}" d="{path}"/></g></svg>')


def main():
    OUT.mkdir(exist_ok=True)
    for row, names in ROWS.items():
        tiles = [custom_tile(n) if n in CUSTOM else skillicon(n) for n in names]
        width_units = len(tiles) * 300 - 44
        body = "\n".join(f'  <g transform="translate({i * 300}, 0)">{t}</g>' for i, t in enumerate(tiles))
        svg = (f'<svg width="{width_units * 48 // 256}" height="48" viewBox="0 0 {width_units} 256" fill="none" '
               f'xmlns="http://www.w3.org/2000/svg">\n{body}\n</svg>\n')
        (OUT / f"stack-{row}.svg").write_text(svg, encoding="utf-8")
        print(f"stack-{row}.svg: {', '.join(names)}")


if __name__ == "__main__":
    main()
