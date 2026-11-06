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


def new_project_description(repo):
    """Use a concise README introduction for newly discovered repositories."""
    fallback = clean(repo.get("description")) or "Public GitHub project."
    url = f"https://api.github.com/repos/{OWNER}/{urllib.parse.quote(repo['name'])}/readme"
    try:
        request = urllib.request.Request(
            url, headers={**HEADERS, "Accept": "application/vnd.github.raw+json"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(45000).decode("utf-8", errors="replace")
        for paragraph in re.split(r"\n\s*\n", raw):
            paragraph = paragraph.strip()
            if not paragraph or paragraph.startswith(("#", "!", "<", "|", "-", "*", ">")):
                continue
            if "](" in paragraph or paragraph.startswith(chr(96) * 3):
                continue
            sentence = clean(re.sub(r"[\x60*_]", "", paragraph))
            if 45 <= len(sentence) <= 320:
                return sentence
    except (OSError, ValueError, UnicodeError):
        pass
    return fallback


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
# Preserve existing hand-written details across scheduled updates.
existing = {}
card_pattern = re.compile(r"^### \[([^\]]+)\]\(https://github\.com/hov172/([^)]+)\)$")
meta_pattern = re.compile(
    r"^\*\*Category:\*\* (.*?) · \*\*Platform:\*\* (.*?) · \*\*Updated:\*\* (.*?)$"
)
sections = re.split(r"\n\n---\n\n", block.strip())
for section in sections:
    lines = section.splitlines()
    if len(lines) < 5:
        continue
    match = card_pattern.match(lines[0])
    metadata = meta_pattern.match(lines[-1])
    if match and metadata:
        name = urllib.parse.unquote(match.group(2)).lower()
        description = "\n".join(lines[2:-2]).strip()
        existing[name] = (match.group(1), description, metadata.group(1), metadata.group(2))

rows = []
for repo in public_repositories():
    name = repo["name"]
    stamp = repo.get("pushed_at") or repo.get("updated_at") or repo["created_at"]
    curated = existing.get(name.lower())
    if curated:
        label, description, group, platform = curated
    else:
        label = clean(name).replace("[", r"\[").replace("]", r"\]")
        description = new_project_description(repo)
        platform = clean(repo.get("language")) or "Other"
        group = category(repo)
    url = f"https://github.com/{OWNER}/{urllib.parse.quote(name)}"
    card = (
        f"### [{label}]({url})\n\n"
        f"{description}\n\n"
        f"**Category:** {group} · **Platform:** {platform} · "
        f"**Updated:** {date_label(stamp)}"
    )
    rows.append((stamp, name.lower(), card))

rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
updated_block = "\n\n" + "\n\n---\n\n".join(card for _, _, card in rows) + "\n\n"
updated = original[:start] + updated_block + original[end:]
if updated != original:
    with open(README, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print(f"Updated {len(rows)} featured public repositories.")
else:
    print(f"Featured projects already current ({len(rows)} public repositories).")
