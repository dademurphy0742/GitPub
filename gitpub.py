#!/usr/bin/env python3
import requests
import argparse
import re
import json
import os
import time
from collections import Counter
from datetime import datetime
from rich.console import Console
from rich.table import Table, box

# ── Config ─────────────────────────────────────────────
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
SCAN_DIR = "scans"
KEYWORDS = {
    "ai": ["ai", "llm", "autogpt", "agent", "comfyui", "dify", "langchain"],
    "python": ["python", "py", "tensorflow", "thealgorithms", "system-design"],
    "cli": ["cli", "command", "terminal", "ohmyzsh", "ratchet"],
    "api": ["api", "rest", "endpoint", "openapi", "firecrawl"],
    "automation": ["automation", "workflow", "n8n", "openclaw"]
}

os.makedirs(SCAN_DIR, exist_ok=True)
console = Console()

# ── Fetch ─────────────────────────────────────────────
def fetch_repos(query, limit, token=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": limit}

    while True:
        r = requests.get(GITHUB_SEARCH_URL, headers=headers, params=params)
        if r.status_code == 200:
            return r.json().get("items", [])
        elif r.status_code == 403:
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            remaining = int(r.headers.get("X-RateLimit-Remaining", 0))
            if remaining == 0:
                wait_time = max(reset - int(time.time()), 1)
                console.print(f"[bold red][!] Rate limit hit. Waiting {wait_time} seconds...[/bold red]")
                time.sleep(wait_time)
            else:
                console.print(f"[bold red][!] Forbidden: {r.json().get('message')}[/bold red]")
                return []
        else:
            console.print(f"[bold red][!] API error for '{query}': {r.status_code}[/bold red]")
            return []

# ── Normalize + Merge ──────────────────────────────────
def normalize_and_merge(results_by_query):
    merged = {}
    for query, repos in results_by_query.items():
        for r in repos:
            key = r["full_name"]
            if key not in merged:
                merged[key] = {
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "desc": r["description"] or "",
                    "stars": r["stargazers_count"],
                    "url": r["html_url"],
                    "sources": set(),
                    "tags": set()
                }
            merged[key]["sources"].add(query)
            for tag, kws in KEYWORDS.items():
                if any(kw in (r["name"] or "").lower() or kw in (r["description"] or "").lower() for kw in kws):
                    merged[key]["tags"].add(tag)
    for v in merged.values():
        v["sources"] = list(v["sources"])
        v["tags"] = list(v["tags"])
    return list(merged.values())

# ── Term Extraction ───────────────────────────────────
def extract_terms(data):
    words = []
    for r in data:
        text = f"{r['name']} {r['desc']}".lower()
        tokens = re.findall(r'\b[a-z]{4,}\b', text)
        words.extend(tokens)
    return Counter(words)

# ── Pattern Detection ─────────────────────────────────
def detect_patterns(data):
    patterns = []
    for r in data:
        name = r["name"]
        if "-" in name:
            parts = name.split("-")
            patterns.append(f"*-{parts[-1]}")
        if name.startswith("auto"):
            patterns.append("auto-*")
        if "ai" in name.lower():
            patterns.append("*-ai")
    return Counter(patterns)

# ── Scoring ──────────────────────────────────────────
def score_repo(repo, term_freq):
    score = repo["stars"] // 10
    keywords = ["scraper", "tracker", "monitor", "automation", "crawler"]
    for kw in keywords:
        if kw in repo["name"].lower() or kw in repo["desc"].lower():
            score += 5
    for word in repo["desc"].split():
        if term_freq[word.lower()] == 1:
            score += 2
    if len(repo["sources"]) > 1:
        score += 10
    return score

# ── Cross-Signal Detection ───────────────────────────
def cross_signal(data):
    return sorted([r for r in data if len(r["sources"]) > 1], key=lambda x: len(x["sources"]), reverse=True)

# ── Find Interesting ─────────────────────────────────
def find_interesting(data, term_freq):
    scored = [(r, score_repo(r, term_freq)) for r in data if score_repo(r, term_freq) > 15]
    return sorted(scored, key=lambda x: x[1], reverse=True)

# ── Save JSON Scan ───────────────────────────────────
def save_scan(data):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(SCAN_DIR, f"scan_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    console.print(f"[green][+] Saved scan to {filename}[/green]")

# ── Load Last Scan ───────────────────────────────────
def load_last_scan():
    files = sorted([f for f in os.listdir(SCAN_DIR) if f.startswith("scan_")])
    if not files:
        return []
    for latest in reversed(files):
        path = os.path.join(SCAN_DIR, latest)
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            console.print(f"[bold red][!] Skipping corrupted scan file: {latest}[/bold red]")
    return []

# ── Detect New and Newly Cross-Signal Repos ───────────
def detect_new_and_cross(current_data, previous_data):
    prev_fullnames = {r["full_name"]: r for r in previous_data}
    new_repos, newly_cross = [], []
    for r in current_data:
        full_name = r["full_name"]
        if full_name not in prev_fullnames:
            new_repos.append(r)
        else:
            prev_sources = set(prev_fullnames[full_name]["sources"])
            if len(r["sources"]) > 1 and len(prev_sources) <= 1:
                newly_cross.append(r)
    return new_repos, newly_cross

# ── Trendiness Score ─────────────────────────────────
def trendiness_score(repo, new_repos, newly_cross):
    score = repo["stars"] // 100
    if repo in new_repos:
        score += 20
    if repo in newly_cross:
        score += 30
    if len(repo["sources"]) > 1:
        score += 10
    return score

# ── Display Repos ───────────────────────────────────
def display_repos(title, repos, new_repos=None, newly_cross=None):
    console.print(f"\n[bold magenta]╭──────────── {title.upper()} ─────────────╮[/bold magenta]")
    for r in repos[:10]:
        table = Table(box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("Field", style="bold cyan", width=16, no_wrap=True)
        table.add_column("Value", style="white", overflow="fold", justify="left", min_width=50)

        full_name = f"[link={r.get('url','')}][yellow]{r.get('full_name','')}[/yellow][/link]"
        url = f"[link={r.get('url','')}][yellow]{r.get('url','')}[/yellow][/link]"
        tags = ", ".join(r.get("tags", [])) or "None"
        sources = ", ".join(r.get("sources", [])) or "None"

        table.add_row("📛 Full Name", full_name)
        table.add_row("⭐ Stars", str(r.get("stars", 0)))
        if new_repos is not None and newly_cross is not None:
            table.add_row("🔥 Trendiness", str(trendiness_score(r, new_repos, newly_cross)))
        table.add_row("🌐 Sources", sources)
        table.add_row("🏷️ Tags", tags)
        table.add_row("🔗 URL", url)
        table.add_row("📝 Description", r.get("desc", ""))

        console.print(table)
    console.print(f"[bold magenta]╰────────────────────────────────────────────╯[/bold magenta]")

# ── Report ──────────────────────────────────────────
def report(data):
    term_freq = extract_terms(data)
    patterns = detect_patterns(data)
    interesting = find_interesting(data, term_freq)
    cross = cross_signal(data)
    previous = load_last_scan()
    new_repos, newly_cross = detect_new_and_cross(data, previous)

    console.print("\n[bold green]=== HOT TERMS ===[/bold green]")
    for term, count in term_freq.most_common(10):
        console.print(f"- {term:<15} {count}")

    console.print("\n[bold green]=== PATTERNS ===[/bold green]")
    for p, count in patterns.most_common(5):
        console.print(f"- {p:<10} {count}")

    display_repos("Cross-Signal Repos (appear in multiple queries)", cross)
    display_repos("New Repos Since Last Scan", new_repos)
    display_repos("Newly Cross-Signal Repos", newly_cross)
    display_repos("Top Interesting Repos", [r for r,_ in interesting[:10]], new_repos, newly_cross)

    console.print(f"\n[bold green]=== SCAN TIME ===[/bold green] {datetime.now()}")
    save_scan(data)

# ── Main ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GitHub Signal Engine (Intelligence + Trends)")
    parser.add_argument("queries", nargs="+", help="Search keywords")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--token", type=str, help="GitHub Personal Access Token for higher rate limits")
    args = parser.parse_args()

    results = {}
    for q in args.queries:
        console.print(f"[bold blue][+] Fetching: {q}[/bold blue]")
        results[q] = fetch_repos(q, args.limit, token=args.token)

    if args.merge:
        data = normalize_and_merge(results)
    else:
        data = []
        for repos in results.values():
            data.extend(repos)
        data = normalize_and_merge({"single": data})

    report(data)

if __name__ == "__main__":
    main()
