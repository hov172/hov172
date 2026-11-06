#!/usr/bin/env python3
"""Automatically maintain featured projects using public GitHub repositories only."""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime

README = "README.md"
OWNER = "hov172"
START = "<!-- FEATURED:START -->"
END = "<!-- FEATURED:END -->"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "profile-featured-project-updater",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def public_repositories():
    page = 1
    while True:
        url = f"https://api.github.com/users/{OWNER}/repos?type=owner&per_page=100&page={page}"
        batch = get_json(url)
        for repo in batch:
            if not repo.get("private") and repo["name"].lower() != OWNER.lower():
                yield repo
        if len(batch) < 100:
            break
        page += 1


def clean(value):
    return re.sub(r"\s+", " ", str(value or "").replace("|", r"\|")).strip()


def date_label(stamp):
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def category(repo):
    name = repo["name"].lower()
    description = (repo.get("description") or "").lower()
    combined = name + " " + description
    if any(term in combined for term in ("authenticator", "2fa", "totp", "security", "secure-webapp")):
        return "Security"
    if any(term in combined for term in ("wifi", "wi-fi", "network", "bonjour", "printer")):
        return "Networking"
    if any(term in combined for term in ("mdm", "munki", "endpoint", "device management")):
        return "Endpoint Management"
    if any(term in combined for term in ("mcp", "ai assistant", "automation")):
        return "AI & Automation"
    if any(term in combined for term in ("autopkg", "homebrew", "signing", "notariz", "deployment")):
        return "Deployment"
    if any(term in combined for term in ("ios", "iphone", "translation")):
        return "Mobile Apps"
    return "Desktop Utilities"


with open(README, encoding="utf-8") as handle:
    original = handle.read()

if original.count(START) != 1 or original.count(END) != 1:
    raise ValueError("Expected exactly one pair of featured project markers")

start = original.index(START) + len(START)
end = original.index(END, start)
block = original[start:end]
# Preserve curated descriptions, platform and category from existing rows.
existing = {}
row_pattern = re.compile(
    r"^\| \*\*\[[^\]]+\]\(https://github\.com/hov172/([^)]+)\)\*\* \|"
)
for line in block.splitlines():
    match = row_pattern.match(line)
    if match:
        name = urllib.parse.unquote(match.group(1)).lower()
        # A featured row has five columns: project, description, platform, category, date.
        parts = re.split(r"(?<!\\) \| ", line.strip().strip("|").strip())
        if len(parts) >= 4:
            existing[name] = parts[:4]

rows = []
for repo in public_repositories():
    name = repo["name"]
    stamp = repo.get("pushed_at") or repo.get("updated_at") or repo["created_at"]
    curated = existing.get(name.lower())
    if curated:
        project, description, platform, group = curated
    else:
        url = f"https://github.com/{OWNER}/{urllib.parse.quote(name)}"
        project = f"**[{clean(name)}]({url})**"
        description = clean(repo.get("description")) or "Public GitHub project."
        platform = clean(repo.get("language")) or "Other"
        group = category(repo)
    row = "| " + " | ".join([project, description, platform, group, date_label(stamp)]) + " |"
    rows.append((stamp, name.lower(), row))

rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
header = [
    "| Project | What it does | Platform | Category | Updated |",
    "|---|---|---|---|---|",
]
updated_block = "\n\n" + "\n".join(header + [row for _, _, row in rows]) + "\n\n"
updated = original[:start] + updated_block + original[end:]
if updated != original:
    with open(README, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print(f"Updated {len(rows)} featured public repositories.")
else:
    print(f"Featured projects already current ({len(rows)} public repositories).")
