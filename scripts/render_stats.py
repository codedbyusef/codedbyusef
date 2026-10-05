"""Render GitHub stats, streak, language and research cards as SVG.

Data comes from the GitHub REST and GraphQL APIs. The streak card needs a token
(GraphQL), so it is skipped with a note when GH_TOKEN is missing.
"""
import html
import json
import os
import pathlib

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CONFIG = json.loads((ROOT / "stats.json").read_text())

USER = os.environ.get("GH_USER") or CONFIG.get("username")
TOKEN = os.environ.get("GH_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
API = "https://api.github.com"

BG = "#0B0F14"
TEXT = "#E6EDF3"
DIM = "#8B949E"
GREEN = "#39FF88"
TEAL = "#2EC4B6"
MONO = "font-family='ui-monospace,SFMono-Regular,Menlo,Consolas,monospace'"


def get(path):
    r = requests.get(API + path, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def owned_repos():
    repos, page = [], 1
    while True:
        batch = get(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        if not batch:
            break
        repos += batch
        page += 1
    return [r for r in repos if not r["fork"]]


def language_totals(repos):
    totals = {}
    for repo in repos:
        for lang, n_bytes in get(f"/repos/{repo['full_name']}/languages").items():
            totals[lang] = totals.get(lang, 0) + n_bytes
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)


def contribution_days():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date } }
          }
        }
      }
    }"""
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": USER}},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    calendar = r.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for week in calendar["weeks"] for d in week["contributionDays"]]
    return calendar["totalContributions"], days


def streaks(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    # Today may not have activity yet, so skip it when counting the current streak.
    rev = days[::-1]
    start = 1 if rev and rev[0]["contributionCount"] == 0 else 0
    current = 0
    for d in rev[start:]:
        if d["contributionCount"] == 0:
            break
        current += 1
    return current, longest


def svg(width, height, body):
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
        f"<rect width='100%' height='100%' rx='12' fill='{BG}' "
        f"stroke='{GREEN}' stroke-opacity='0.35'/>{body}</svg>"
    )


def rows_card(title, rows, width=420):
    body = [f"<text x='24' y='38' {MONO} font-size='16' fill='{GREEN}'>{html.escape(title)}</text>"]
    for i, (label, value) in enumerate(rows):
        y = 74 + i * 26
        body.append(f"<text x='24' y='{y}' {MONO} font-size='14' fill='{DIM}'>{html.escape(label)}</text>")
        body.append(
            f"<text x='{width - 24}' y='{y}' text-anchor='end' {MONO} font-size='14' "
            f"fill='{TEXT}'>{html.escape(str(value))}</text>"
        )
    return svg(width, 60 + 26 * len(rows) + 30, "".join(body))


def language_card(totals, top=6, width=860):
    total = sum(n for _, n in totals) or 1
    top_langs = totals[:top]
    body = [f"<text x='24' y='38' {MONO} font-size='16' fill='{GREEN}'>Top languages</text>"]
    for i, (lang, n_bytes) in enumerate(top_langs):
        y = 66 + i * 26
        pct = 100 * n_bytes / total
        bar_w = (width - 220) * pct / 100
        body.append(f"<text x='24' y='{y + 12}' {MONO} font-size='14' fill='{TEXT}'>{html.escape(lang)}</text>")
        body.append(f"<rect x='160' y='{y}' width='{width - 220}' height='12' rx='6' fill='#161B22'/>")
        body.append(f"<rect x='160' y='{y}' width='{max(bar_w, 2):.1f}' height='12' rx='6' fill='{TEAL}'/>")
        body.append(f"<text x='{width - 24}' y='{y + 12}' text-anchor='end' {MONO} font-size='13' fill='{DIM}'>{pct:.1f}%</text>")
    return svg(width, 66 + 26 * len(top_langs) + 16, "".join(body))


def research_card(items, width=860):
    body = [f"<text x='24' y='38' {MONO} font-size='16' fill='{GREEN}'>Research &amp; community</text>"]
    for i, item in enumerate(items):
        y = 70 + i * 26
        body.append(f"<text x='24' y='{y}' {MONO} font-size='14' fill='{DIM}'>{html.escape(item['label'])}</text>")
        body.append(
            f"<text x='{width - 24}' y='{y}' text-anchor='end' {MONO} font-size='14' "
            f"fill='{TEXT}'>{html.escape(str(item['value']))}</text>"
        )
    return svg(width, 70 + 26 * len(items) + 16, "".join(body))


def write(name, content):
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / name).write_text(content)
    print(f"wrote assets/{name}")


def main():
    if not USER:
        raise SystemExit("Set GH_USER or fill in 'username' in stats.json")

    user = get(f"/users/{USER}")
    repos = owned_repos()
    stars = sum(r["stargazers_count"] for r in repos)
    languages = language_totals(repos)

    write("stats-card.svg", rows_card("GitHub stats", [
        ("Public repos", user["public_repos"]),
        ("Stars earned", stars),
        ("Followers", user["followers"]),
        ("Languages", len(languages)),
    ]))

    if TOKEN:
        total, days = contribution_days()
        current, longest = streaks(days)
        write("streak-card.svg", rows_card("Contribution streak", [
            ("Contributions (last year)", total),
            ("Current streak (days)", current),
            ("Longest streak (days)", longest),
        ]))
    else:
        print("GH_TOKEN not set: skipping streak card")

    write("langs-card.svg", language_card(languages))
    write("research-card.svg", research_card(CONFIG.get("research", [])))


if __name__ == "__main__":
    main()
