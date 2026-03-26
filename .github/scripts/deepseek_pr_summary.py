#!/usr/bin/env python3
import os
import sys
import json
import datetime
import requests
from github import Github

# ---------- CONFIGURATION ----------
BRANCH = "main"            # Change to your main branch name
LOOKBACK_DAYS = 7             # Weekly summary
# ----------------------------------

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")

if not all([GITHUB_TOKEN, DEEPSEEK_API_KEY, REPO_NAME]):
    print("Missing environment variables")
    sys.exit(1)

# GitHub API client
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# Calculate date range
since = datetime.datetime.utcnow() - datetime.timedelta(days=LOOKBACK_DAYS)
print(f"Fetching PRs merged to {BRANCH} since {since.isoformat()}")

# Get merged PRs
prs = repo.get_pulls(state='closed', base=BRANCH, sort='updated', direction='desc')
merged_prs = []

for pr in prs:
    if pr.merged and pr.merged_at and pr.merged_at > since:
        merged_prs.append({
            'title': pr.title,
            'author': pr.user.login,
            'url': pr.html_url,
            'labels': [label.name for label in pr.labels],
            'description': (pr.body or '')[:300]
        })

if not merged_prs:
    print("No new merged PRs.")
    # Create empty file to skip sending
    with open("pr_summary.md", "w") as f:
        f.write("No PRs merged this week.")
    sys.exit(0)

# Limit to 15 PRs to avoid token overload
merged_prs = merged_prs[:15]

# Build the prompt
pr_text = "\n".join([
    f"- **{pr['title']}** by @{pr['author']}\n  {pr['url']}\n  Labels: {', '.join(pr['labels']) if pr['labels'] else 'none'}"
    for pr in merged_prs
])

prompt = f"""Summarize these merged pull requests for the team in a concise, friendly style:

{pr_text}

Group them into categories: Features, Bug Fixes, Documentation, Other. Use markdown bullet points.
Start with a brief intro sentence. End with total PR count."""

# Call DeepSeek API
headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.3,
    "max_tokens": 1000
}

try:
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    result = resp.json()
    summary = result["choices"][0]["message"]["content"]
except Exception as e:
    print(f"DeepSeek API error: {e}")
    summary = "⚠️ AI summary generation failed. Please check the logs."

# Save summary to a markdown file
with open("pr_summary.md", "w") as f:
    f.write(summary)

print("Summary saved to pr_summary.md")
