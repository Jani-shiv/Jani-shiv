#!/usr/bin/env python3
"""
Generate animated SVG cards for GitHub profile README.
Reads contribution data from JSON, outputs SVGs to cards/ directory.
Supports STATIC=1 env var for final-frame screenshots.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

STATIC = os.getenv("STATIC", "0") == "1"

REPO_ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = REPO_ROOT / "cards"
DATA_FILE = REPO_ROOT / "contributions.json"
FONTS_DIR = REPO_ROOT / "fonts"

CARDS_DIR.mkdir(exist_ok=True)

# Brand colors matching README.md
COLORS = {
    "dark": {
        "bg": "#0d1117",
        "surface": "#161b22",
        "border": "#30363d",
        "text": "#ffffff",
        "muted": "#9198a1",
        "accent": "#FF6B35",
        "accent_soft": "#2d1a12",
        "blue": "#58A6FF",
        "blue_soft": "#0d1f2d",
        "ok": "#3fb950",
        "ok_soft": "#12261b",
        "bad": "#f85149",
        "warn": "#d29922",
    },
}

CARD_WIDTH = 1000
CARD_HEIGHT = 180
TILE_WIDTH = 325
TILE_HEIGHT = 180
CHART_WIDTH = 1000
CHART_HEIGHT = 300
REPO_CARD_WIDTH = 1000
REPO_CARD_HEIGHT = 160
GRAPH_WIDTH = 1000
GRAPH_HEIGHT = 200

ANIMATION_DURATION = "800ms"
STAGGER_DELAY = 150


def load_contributions() -> dict[str, Any]:
    if DATA_FILE.exists():
        with DATA_FILE.open() as f:
            return json.load(f)
    return {}


def subset_font(font_path: Path, text: str, weight: str = "400") -> str:
    """Subset a font file to only needed glyphs and return base64 WOFF2 data URI."""
    if not font_path.exists():
        return ""

    try:
        with tempfile.NamedTemporaryFile(suffix=".woff2", delete=False) as tmp:
            out_path = tmp.name

        subprocess.run(
            [
                "pyftsubset",
                str(font_path),
                f"--text={text}",
                "--flavor=woff2",
                f"--output-file={out_path}",
                "--layout-features=*",
            ],
            check=True,
            capture_output=True,
        )
        with open(out_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        Path(out_path).unlink(missing_ok=True)
        return f"data:font/woff2;base64,{b64}"
    except Exception as e:
        print(f"Warning: Font subsetting failed for {font_path}: {e}", file=sys.stderr)
        return ""


def font_face_css(font_family: str, font_url: str, weight: str = "400") -> str:
    return f"""
@font-face {{
  font-family: '{font_family}';
  src: url('{font_url}') format('woff2');
  font-weight: {weight};
  font-display: block;
}}"""


def prefers_reduced_motion_css() -> str:
    return """
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
  animate, animateMotion, animateTransform { display: none !important; }
}"""


def keyframes_css(card_index: int) -> str:
    delay = card_index * STAGGER_DELAY
    return f"""
@keyframes fadeInUp {{
  from {{ opacity: 0; transform: translateY(20px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes slideInLeft {{
  from {{ opacity: 0; transform: translateX(-30px); }}
  to   {{ opacity: 1; transform: translateX(0); }}
}}
@keyframes pulse {{
  0%, 100% {{ transform: scale(1); }}
  50%      {{ transform: scale(1.05); }}
}}
.card-{card_index} {{
  animation: fadeInUp {ANIMATION_DURATION} cubic-bezier(0.16, 1, 0.3, 1) {delay}ms forwards;
  opacity: 0;
}}
.tile-{card_index} {{
  animation: slideInLeft {ANIMATION_DURATION} cubic-bezier(0.16, 1, 0.3, 1) {delay + 100}ms forwards;
  opacity: 0;
}}"""


def svg_wrapper(
    width: int,
    height: int,
    inner: str,
    card_index: int = 0,
    font_css: str = "",
    extra_css: str = "",
) -> str:
    css = f"""
  <style>
    {font_css}
    {prefers_reduced_motion_css()}
    {keyframes_css(card_index) if not STATIC else ""}
    {extra_css}
    .stagger-{card_index} {{ animation-delay: {card_index * STAGGER_DELAY}ms; }}
    .stat-value {{ font-variant-numeric: tabular-nums; }}
  </style>
"""
    viewbox = f"0 0 {width} {height}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="{viewbox}" role="img" aria-hidden="true">
{css}
{inner}
</svg>"""


def rect(x: float, y: float, w: float, h: float, rx: float = 0, class_: str = "", **attrs) -> str:
    a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    cls = f' class="{class_}"' if class_ else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"{cls} {a}/>'


def text(x: float, y: float, content: str, **attrs) -> str:
    a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f'<text x="{x}" y="{y}" {a}>{content}</text>'


def circle(cx: float, cy: float, r: float, **attrs) -> str:
    a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" {a}/>'


def animate_id(attribute: str, from_val: str, to_val: str, dur: str, begin: str = "0s", **attrs) -> str:
    a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f'<animate attributeName="{attribute}" from="{from_val}" to="{to_val}" dur="{dur}" begin="{begin}" fill="freeze" {a}/>'


def animate_transform(type_: str, from_val: str, to_val: str, dur: str, begin: str = "0s", **attrs) -> str:
    a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f'<animateTransform attributeName="transform" type="{type_}" from="{from_val}" to="{to_val}" dur="{dur}" begin="{begin}" fill="freeze" {a}/>'


def generate_hero_card(data: dict, card_index: int, font_urls: dict[str, str]) -> str:
    c = COLORS["dark"]
    name = "Shiv Jani"
    tagline = "DevOps Engineer | Linux Enthusiast | Cloud Automation Expert"
    avatar_url = "https://github.com/Jani-shiv.png"

    font_css = (
        font_face_css("ProfileFont", font_urls.get("600", ""), "600")
        + font_face_css("ProfileFont", font_urls.get("400", ""), "400")
    )

    inner = f"""
  <defs>
    <clipPath id="avatar-clip"><circle cx="60" cy="60" r="56"/></clipPath>
  </defs>
  {rect(0, 0, CARD_WIDTH, CARD_HEIGHT, 16, fill=c["surface"], stroke=c["border"], stroke_width=1)}
  <image href="{avatar_url}" x="24" y="24" width="112" height="112" clip-path="url(#avatar-clip)"/>
  <text x="156" y="72" font-family="ProfileFont" font-size="32" font-weight="600" fill="{c['accent']}" class="card-{card_index}">{name}</text>
  <text x="156" y="110" font-family="ProfileFont" font-size="18" fill="{c['muted']}" class="card-{card_index}">{tagline}</text>
  <g class="card-{card_index}" transform="translate(156, 130)">
    <a href="https://youtube.com/@devopsnidiary" target="_blank" rel="noopener">
      <rect x="0" y="0" width="280" height="28" rx="14" fill="{c['accent_soft']}"/>
      <text x="140" y="19" font-family="ProfileFont" font-size="13" font-weight="600" fill="{c['accent']}" text-anchor="middle">🎥 youtube.com/@devopsnidiary</text>
    </a>
  </g>
"""

    if STATIC:
        inner = inner.replace(f'class="card-{card_index}"', f'class="static-card-{card_index}"')

    extra_css = """
  a:hover rect { fill: var(--accent-soft-hover, #3d2518); }
  a:focus rect { outline: 2px solid #FF6B35; outline-offset: 2px; }
"""
    return svg_wrapper(CARD_WIDTH, CARD_HEIGHT, inner, card_index, font_css, extra_css)


def generate_tiles_card(data: dict, card_index: int, font_urls: dict[str, str]) -> str:
    c = COLORS["dark"]

    tiles = [
        {
            "icon": "📊",
            "label": "Total Contributions",
            "value": str(data.get("total_contributions", 0)),
            "href": "https://github.com/Jani-shiv",
            "bg": c["blue_soft"],
            "icon_color": c["blue"],
        },
        {
            "icon": "🔥",
            "label": "Current Streak",
            "value": f"{data.get('current_streak', 0)} days",
            "href": "https://github.com/Jani-shiv",
            "bg": c["accent_soft"],
            "icon_color": c["accent"],
        },
        {
            "icon": "⚡",
            "label": "Active Days",
            "value": str(data.get("active_days", 0)),
            "href": "https://github.com/Jani-shiv",
            "bg": c["ok_soft"],
            "icon_color": c["ok"],
        },
    ]

    font_css = (
        font_face_css("ProfileFont", font_urls.get("600", ""), "600")
        + font_face_css("ProfileFont", font_urls.get("400", ""), "400")
    )

    tile_svgs = []
    for i, tile in enumerate(tiles):
        x = i * (TILE_WIDTH + 12)
        tile_svgs.append(f"""
    <a href="{tile['href']}" target="_blank" rel="noopener" class="tile-{card_index}-{i}">
      {rect(x, 0, TILE_WIDTH, TILE_HEIGHT, 16, fill=tile["bg"], stroke=c["border"], stroke_width=1)}
      <text x="{x + 24}" y="55" font-family="ProfileFont" font-size="40">{tile['icon']}</text>
      <text x="{x + TILE_WIDTH/2}" y="105" font-family="ProfileFont" font-size="32" font-weight="600" fill="{c['text']}" text-anchor="middle" class="stat-value tile-{card_index}-{i}">{tile['value']}</text>
      <text x="{x + TILE_WIDTH/2}" y="140" font-family="ProfileFont" font-size="14" fill="{c['muted']}" text-anchor="middle" class="tile-{card_index}-{i}">{tile['label']}</text>
    </a>
""")

    inner = "".join(tile_svgs)

    if STATIC:
        inner = inner.replace(f'class="tile-{card_index}-', f'class="static-tile-{card_index}-')

    extra_css = f"""
  a:hover rect {{ stroke: {c['accent']}; filter: brightness(1.1); }}
  a:focus rect {{ outline: 2px solid {c['accent']}; outline-offset: 2px; }}
"""
    return svg_wrapper(CARD_WIDTH, TILE_HEIGHT, inner, card_index, font_css, extra_css)


def generate_contributions_chart(data: dict, card_index: int, font_urls: dict[str, str]) -> str:
    c = COLORS["dark"]
    monthly = data.get("monthly", [])
    streak = data.get("current_streak", 0)
    active_days = data.get("active_days", 0)
    busiest = data.get("busiest_day", {"date": "", "count": 0})

    font_css = (
        font_face_css("ProfileFont", font_urls.get("600", ""), "600")
        + font_face_css("ProfileFont", font_urls.get("400", ""), "400")
    )

    max_count = max((m.get("count", 0) for m in monthly), default=1)
    bar_width = 60
    gap = 20
    start_x = 60
    chart_bottom = CHART_HEIGHT - 60

    bars = []
    for i, month in enumerate(monthly[-12:]):
        count = month.get("count", 0)
        label = month.get("month", "")
        h = (count / max_count) * (CHART_HEIGHT - 100) if max_count > 0 else 0
        x = start_x + i * (bar_width + gap)
        y = chart_bottom - h

        delay = i * 80
        anim = ""
        if not STATIC:
            anim = f"""
            <animate attributeName="height" from="0" to="{h}" dur="600ms" begin="{delay}ms" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.16 1 0.3 1"/>
            <animate attributeName="y" from="{chart_bottom}" to="{y}" dur="600ms" begin="{delay}ms" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.16 1 0.3 1"/>
"""

        bars.append(f"""
      <g class="bar-{i}">
        {rect(x, y, bar_width, h, 4, fill=c["accent"])}
        {anim}
        <text x="{x + bar_width/2}" y="{chart_bottom + 25}" font-family="ProfileFont" font-size="11" fill="{c['muted']}" text-anchor="middle">{label}</text>
        <text x="{x + bar_width/2}" y="{y - 8}" font-family="ProfileFont" font-size="11" font-weight="600" fill="{c['text']}" text-anchor="middle" opacity="0">
          <animate attributeName="opacity" from="0" to="1" dur="200ms" begin="{delay + 600}ms" fill="freeze"/>{count}
        </text>
      </g>
""")

    stats_y = 40
    stats = f"""
  <g transform="translate(60, {stats_y})">
    <text x="0" y="0" font-family="ProfileFont" font-size="18" font-weight="600" fill="{c['text']}" class="card-{card_index}">Contribution Stats</text>
    <g transform="translate(0, 30)">
      {rect(0, 0, 280, 50, 8, fill=c["accent_soft"])}
      <text x="140" y="22" font-family="ProfileFont" font-size="20" font-weight="600" fill="{c['accent']}" text-anchor="middle" class="stat-value">{streak}</text>
      <text x="140" y="42" font-family="ProfileFont" font-size="11" fill="{c['muted']}" text-anchor="middle">Current Streak</text>
    </g>
    <g transform="translate(300, 30)">
      {rect(0, 0, 280, 50, 8, fill=c["ok_soft"])}
      <text x="140" y="22" font-family="ProfileFont" font-size="20" font-weight="600" fill="{c['ok']}" text-anchor="middle" class="stat-value">{active_days}</text>
      <text x="140" y="42" font-family="ProfileFont" font-size="11" fill="{c['muted']}" text-anchor="middle">Active Days</text>
    </g>
    <g transform="translate(600, 30)">
      {rect(0, 0, 320, 50, 8, fill=c["blue_soft"])}
      <text x="160" y="22" font-family="ProfileFont" font-size="20" font-weight="600" fill="{c['blue']}" text-anchor="middle" class="stat-value">{busiest.get('count', 0)}</text>
      <text x="160" y="42" font-family="ProfileFont" font-size="11" fill="{c['muted']}" text-anchor="middle">Busiest Day ({busiest.get('date', '—')})</text>
    </g>
  </g>
"""

    inner = f"""
  {rect(0, 0, CHART_WIDTH, CHART_HEIGHT, 16, fill=c["surface"], stroke=c["border"], stroke_width=1)}
  <g transform="translate(0, 0)">
    {''.join(bars)}
  </g>
  {stats}
"""

    if STATIC:
        inner = inner.replace(f'class="card-{card_index}"', f'class="static-card-{card_index}"')
        inner = inner.replace('class="bar-', 'class="static-bar-')

    return svg_wrapper(CHART_WIDTH, CHART_HEIGHT, inner, card_index, font_css)


def generate_repo_card(repo: dict, card_index: int, font_urls: dict[str, str]) -> str:
    c = COLORS["dark"]
    name = repo.get("name", "")
    desc = repo.get("description", "No description")
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    language = repo.get("language", "")
    url = repo.get("html_url", "#")
    color = repo.get("language_color", c["accent"])

    font_css = (
        font_face_css("ProfileFont", font_urls.get("600", ""), "600")
        + font_face_css("ProfileFont", font_urls.get("400", ""), "400")
    )

    lang_badge = ""
    if language:
        lang_badge = f"""
      <g transform="translate(24, 110)">
        {circle(6, 6, 6, fill=color)}
        <text x="18" y="16" font-family="ProfileFont" font-size="12" fill="{c['muted']}">{language}</text>
      </g>
"""

    inner = f"""
  <a href="{url}" target="_blank" rel="noopener">
    {rect(0, 0, REPO_CARD_WIDTH, REPO_CARD_HEIGHT, 16, fill=c["surface"], stroke=c["border"], stroke_width=1, class_="repo-bg")}
    <text x="24" y="48" font-family="ProfileFont" font-size="20" font-weight="600" fill="{c['text']}" class="repo-name">{name}</text>
    <text x="24" y="80" font-family="ProfileFont" font-size="14" fill="{c['muted']}" width="900">{desc[:120]}{'…' if len(desc) > 120 else ''}</text>
    {lang_badge}
    <g transform="translate(800, 20)">
      <text x="0" y="0" font-family="ProfileFont" font-size="13" fill="{c['muted']}" text-anchor="end">⭐ {stars}</text>
      <text x="0" y="22" font-family="ProfileFont" font-size="13" fill="{c['muted']}" text-anchor="end">🍴 {forks}</text>
    </g>
  </a>
"""

    extra_css = f"""
  a:hover .repo-bg {{ stroke: {c['accent']}; }}
  a:hover .repo-name {{ fill: {c['accent']}; }}
  a:focus .repo-bg {{ outline: 2px solid {c['accent']}; outline-offset: 2px; }}
"""
    if STATIC:
        inner = inner.replace('class="repo-', 'class="static-repo-')

    return svg_wrapper(REPO_CARD_WIDTH, REPO_CARD_HEIGHT, inner, card_index, font_css, extra_css)


def generate_contribution_graph(data: dict, card_index: int, font_urls: dict[str, str]) -> str:
    c = COLORS["dark"]
    weeks = data.get("weeks", [])

    font_css = (
        font_face_css("ProfileFont", font_urls.get("600", ""), "600")
        + font_face_css("ProfileFont", font_urls.get("400", ""), "400")
    )

    if not weeks:
        inner = f"""
  {rect(0, 0, GRAPH_WIDTH, GRAPH_HEIGHT, 16, fill=c["surface"], stroke=c["border"], stroke_width=1)}
  <text x="{GRAPH_WIDTH/2}" y="{GRAPH_HEIGHT/2}" font-family="ProfileFont" font-size="16" fill="{c['muted']}" text-anchor="middle" dominant-baseline="middle">No contribution data available</text>
"""
        return svg_wrapper(GRAPH_WIDTH, GRAPH_HEIGHT, inner, card_index, font_css)

    cell_size = 12
    gap = 2
    start_x = 60
    start_y = 40
    max_count = max((max((day.get("count", 0) for day in week), default=0) for week in weeks), default=1)

    def intensity_color(count: int) -> str:
        if count == 0:
            return c["border"]
        ratio = min(count / max_count, 1.0)
        if ratio < 0.25:
            return "#ffd6cc"
        elif ratio < 0.5:
            return "#ffaa8c"
        elif ratio < 0.75:
            return "#ff7a4d"
        return "#FF6B35"

    cells = []
    for w, week in enumerate(weeks[-52:]):
        for d, day in enumerate(week):
            count = day.get("count", 0)
            x = start_x + w * (cell_size + gap)
            y = start_y + d * (cell_size + gap)
            color = intensity_color(count)
            date = day.get("date", "")

            anim = ""
            if not STATIC:
                delay = (w * 7 + d) * 15
                anim = f"""
                <animate attributeName="opacity" from="0" to="1" dur="200ms" begin="{delay}ms" fill="freeze"/>
                <animateTransform attributeName="transform" type="scale" from="0.5" to="1" dur="200ms" begin="{delay}ms" fill="freeze"/>
"""

            cells.append(f"""
      <g transform="translate({x}, {y})">
        <title>{date}: {count} contributions</title>
        {rect(0, 0, cell_size, cell_size, 2, fill=color, opacity="0")}
        {anim}
      </g>
""")

    month_labels = []
    for i, week in enumerate(weeks[-52:]):
        if i % 4 == 0 and week:
            date = week[0].get("date", "")
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    label = dt.strftime("%b")
                    x = start_x + i * (cell_size + gap) + cell_size / 2
                    month_labels.append(f'<text x="{x}" y="{start_y - 8}" font-family="ProfileFont" font-size="11" fill="{c["muted"]}" text-anchor="middle">{label}</text>')
                except Exception:
                    pass

    day_labels = ["Mon", "Wed", "Fri"]
    day_label_svg = ""
    for i, label in enumerate(day_labels):
        y = start_y + [0, 2, 4][i] * (cell_size + gap) + cell_size / 2 + 4
        day_label_svg += f'<text x="{start_x - 10}" y="{y}" font-family="ProfileFont" font-size="10" fill="{c["muted"]}" text-anchor="end" dominant-baseline="middle">{label}</text>'

    legend = f"""
  <g transform="translate({GRAPH_WIDTH - 200}, {GRAPH_HEIGHT - 30})">
    <text x="0" y="0" font-family="ProfileFont" font-size="11" fill="{c['muted']}">Less</text>
    <g transform="translate(50, -4)">
      {rect(0, 0, 10, 10, 2, fill=c["border"])}
      {rect(14, 0, 10, 10, 2, fill="#ffd6cc")}
      {rect(28, 0, 10, 10, 2, fill="#ffaa8c")}
      {rect(42, 0, 10, 10, 2, fill="#ff7a4d")}
      {rect(56, 0, 10, 10, 2, fill="#FF6B35")}
    </g>
    <text x="150" y="0" font-family="ProfileFont" font-size="11" fill="{c['muted']}">More</text>
  </g>
"""

    inner = f"""
  {rect(0, 0, GRAPH_WIDTH, GRAPH_HEIGHT, 16, fill=c["surface"], stroke=c["border"], stroke_width=1)}
  <text x="{GRAPH_WIDTH/2}" y="24" font-family="ProfileFont" font-size="18" font-weight="600" fill="{c['text']}" text-anchor="middle" class="card-{card_index}">Contribution Graph</text>
  {''.join(month_labels)}
  {day_label_svg}
  {''.join(cells)}
  {legend}
"""

    if STATIC:
        inner = inner.replace(f'class="card-{card_index}"', f'class="static-card-{card_index}"')

    return svg_wrapper(GRAPH_WIDTH, GRAPH_HEIGHT, inner, card_index, font_css)


def main() -> int:
    data = load_contributions()
    username = data.get("username", "Jani-shiv")

    # Collect all text for font subsetting
    monthly_labels = " ".join(m.get("month", "") for m in data.get("monthly", []))
    repo_names = " ".join(r.get("name", "") for r in data.get("featured_repos", [])[:4])
    all_text = (
        f"{username} DevOps Engineer Linux Cloud Automation YouTube "
        f"Contributions Streak Active Days Featured Repos "
        f"{monthly_labels} {repo_names}"
    )

    # Subset fonts from downloaded Fira Code
    font_urls = {}
    for weight_name, weight_val in [("400", "Regular"), ("500", "Medium"), ("600", "SemiBold"), ("700", "Bold")]:
        font_path = FONTS_DIR / f"FiraCode-{weight_val}.ttf"
        if font_path.exists():
            font_urls[weight_name] = subset_font(font_path, all_text, weight_name)
        else:
            font_urls[weight_name] = ""

    if not font_urls.get("600") or not font_urls.get("400"):
        print("Warning: Could not subset font, using system fallback", file=sys.stderr)
        font_urls = {"400": "", "600": ""}

    cards = []

    cards.append(("hero.svg", generate_hero_card(data, 0, font_urls)))

    cards.append(("tiles.svg", generate_tiles_card(data, 1, font_urls)))

    cards.append(("contributions.svg", generate_contributions_chart(data, 2, font_urls)))

    featured = data.get("featured_repos", data.get("repos", [])[:4])
    for i, repo in enumerate(featured):
        cards.append((f"repo-{i}.svg", generate_repo_card(repo, 3 + i, font_urls)))

    cards.append(("graph.svg", generate_contribution_graph(data, 3 + len(featured), font_urls)))

    for filename, svg in cards:
        out_path = CARDS_DIR / filename
        out_path.write_text(svg, encoding="utf-8")
        print(f"Generated {out_path.relative_to(REPO_ROOT)} ({len(svg)} bytes)")

    print(f"\nDone! {len(cards)} cards written to {CARDS_DIR.relative_to(REPO_ROOT)}/")
    if STATIC:
        print("STATIC=1 mode: animations disabled, final frame rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())