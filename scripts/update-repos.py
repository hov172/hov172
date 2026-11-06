#!/usr/bin/env python3
"""Refresh the profile repository table, discovering new public repositories."""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime

README = "README.md"
OWNER = "hov172"
START = "<!-- REPOS:START -->"
END = "<!-- REPOS:END -->"
FEATURED_START = "<!-- FEATURED:START -->"
FEATURED_END = "<!-- FEATURED:END -->"

token = os.environ.get("GITHUB_TOKEN", "")
headers = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "profile-repo-updater",
    "X-GitHub-Api-Version": "2022-11-28",
}
if token:
    headers["Authorization"] = f"Bearer {token}"


def get_json(url):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def public_repositories():
    # GitHub paginates at 100 repositories; don't silently miss later pages.
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{OWNER}/repos"
            f"?type=owner&per_page=100&page={page}"
        )
        repos = get_json(url)
        for repo in repos:
            if not repo.get("private") and repo["name"].lower() != OWNER.lower():
                yield repo
        if len(repos) < 100:
            break
        page += 1


def fmt(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def cell(value):
    # Keep GitHub-provided descriptions from breaking the Markdown table.
    return re.sub(r"\s+", " ", (value or "").replace("|", "\\|")).strip()


with open(README, encoding="utf-8") as file:
    text = file.read()

a = text.index(START) + len(START)
b = text.index(END, a)
block = text[a:b]
existing = {}
pattern = re.compile(
    r"^\| \[([^\]]+)\]\(https://github\.com/hov172/([^\)]+)\) \|"
)
for line in block.splitlines():
    match = pattern.match(line)
    if match:
        existing[urllib.parse.unquote(match.group(2)).lower()] = line

rows = []
public_by_name = {}
for repo in public_repositories():
    public_by_name[repo["name"].lower()] = repo
    name = repo["name"]
    stamp = repo.get("pushed_at") or repo.get("updated_at") or repo["created_at"]
    old = existing.get(name.lower())
    if old:
        # Keep the hand-curated project name, description, and tech stack.
        parts = old.rsplit(" | ", 1)
        line = parts[0] + " | " + fmt(stamp) + " |"
    else:
        description = cell(repo.get("description")) or "Public GitHub repository."
        language = cell(repo.get("language")) or "Other"
        label = cell(name).replace("[", "\\[").replace("]", "\\]")
        url = f"https://github.com/{OWNER}/{urllib.parse.quote(name)}"
        line = f"| [{label}]({url}) | {description} | {language} | {fmt(stamp)} |"
    rows.append((stamp, name.lower(), line))

rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
table = [
    "| Project | Description | Tech | Updated |",
    "|---------|-------------|------|---------|",
] + [line for _, _, line in rows]
new = text[:a] + "\n\n" + "\n".join(table) + "\n\n" + text[b:]
# Refresh featured rows from public repository activity, preserving curated descriptions.
if FEATURED_START in new and FEATURED_END in new:
    fa = new.index(FEATURED_START) + len(FEATURED_START)
    fb = new.index(FEATURED_END, fa)
    featured_rows = []
    pattern_featured = re.compile(r"^\| \*\*\[[^\]]+\]\(https://github\.com/hov172/([^)]+)\)\*\* \|")
    for line in new[fa:fb].splitlines():
        match = pattern_featured.match(line)
        if not match:
            continue
        name = urllib.parse.unquote(match.group(1)).lower()
        repo = public_by_name.get(name)
        if not repo:
            continue  # Never expose private or unavailable repositories.
        stamp = repo.get("pushed_at") or repo.get("updated_at") or repo["created_at"]
        parts = line.strip().strip("|").strip().split(" | ")
        curated = parts[:4] if len(parts) >= 5 else parts[:3] + ["Other"]
        featured_rows.append((stamp, name, "| " + " | ".join(curated) + " | " + fmt(stamp) + " |"))
    featured_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    featured_table = ["| Project | What it does | Platform | Category | Updated |", "|---|---|---|---|---|"]
    featured_table.extend(line for _, _, line in featured_rows)
    new = new[:fa] + "\n\n" + "\n".join(featured_table) + "\n\n" + new[fb:]

if new != text:
    with open(README, "w", encoding="utf-8") as file:
        file.write(new)
    print(f"Updated README with {len(rows)} public repositories.")
else:
    print(f"README already current ({len(rows)} public repositories).")
