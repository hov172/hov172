#!/usr/bin/env python3
import json, os, re, urllib.request
from datetime import datetime

README="README.md"
START="<!-- REPOS:START -->"
END="<!-- REPOS:END -->"

token=os.environ.get("GITHUB_TOKEN","")
headers={"Accept":"application/vnd.github+json","User-Agent":"profile-repo-updater"}
if token: headers["Authorization"]=f"Bearer {token}"

def pushed_at(repo):
    req=urllib.request.Request(f"https://api.github.com/repos/hov172/{repo}",headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.load(r)["pushed_at"]

def fmt(iso):
    d=datetime.fromisoformat(iso.replace("Z","+00:00"))
    return f"{d.strftime('%b')} {d.day}, {d.year}"

text=open(README,encoding="utf-8").read()
a=text.index(START)+len(START)
b=text.index(END,a)
block=text[a:b].strip()
lines=block.splitlines()
header=lines[:2]
rows=[]
pat=re.compile(r"^\| \[([^\]]+)\]\(https://github\.com/hov172/([^\)]+)\) \|")
for line in lines[2:]:
    m=pat.match(line)
    if not m: continue
    repo=m.group(2)
    stamp=pushed_at(repo)
    parts=line.rsplit(" | ",1)
    line=parts[0]+" | "+fmt(stamp)+" |"
    rows.append((stamp.lower(),line))
rows.sort(key=lambda x:x[0],reverse=True)
newblock="\n".join(header+[r[1] for r in rows])
new=text[:a]+"\n\n"+newblock+"\n\n"+text[b:]
open(README,"w",encoding="utf-8").write(new)
