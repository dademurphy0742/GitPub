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
from rich.table import Table
from rich.panel import Panel
from rich import box

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
                console.print(f"[red][!] Rate limit hit. Waiting {wait_time} seconds...[/red]")
                time.sleep(wait_time)
            else:
                console.print(f"[red][!] Forbidden: {r.json().get('message')}[/red]")
                return []
        else:
            console.print(f"[red][!] API error for '{query}': {r.status_code}[/red]")
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
    multi = [r for r in data if len(r["sources"]) > 1]
    return sorted(multi, key=lambda x: len(x["sources"]), reverse=True)

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
            console.print(f"[red][!] Skipping corrupted scan file: {latest}[/red]")
    return []

# ── Detect New and Newly Cross-Signal Repos ───────────
def detect_new_and_cross(current_data, previous_data):
    prev_fullnames = {r["full_name"]: r for r in previous_data}
    new_repos = []
    newly_cross = []
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

# ── Report ──────────────────────────────────────────
def report(data):
    term_freq = extract_terms(data)
    patterns = detect_patterns(data)
    interesting = find_interesting(data, term_freq)
    cross = cross_signal(data)
    previous = load_last_scan()
    new_repos, newly_cross = detect_new_and_cross(data, previous)

    console.rule("[bold cyan]MERGED SIGNAL REPORT[/bold cyan]")

    # Hot Terms
    hot_terms = "\n".join(f"[yellow]- {t} ({c})[/yellow]" for t, c in term_freq.most_common(10))
    console.print(Panel(hot_terms, title="[bold green]HOT TERMS[/bold green]", expand=True))

    # Patterns
    pattern_text = "\n".join(f"[magenta]- {p} ({c})[/magenta]" for p, c in patterns.most_common(5))
    console.print(Panel(pattern_text, title="[bold green]PATTERNS[/bold green]", expand=True))

    def display_repos(title, repos):
        for r in repos[:10]:
            table = Table(box=box.SIMPLE, expand=True)
            table.add_column("Field", style="bold cyan", no_wrap=True)
            table.add_column(
                "Value",
                style="white",
                no_wrap=False,
                overflow="fold",
                justify="left",
                min_width=30
            )

            full_name = f"[link={r.get('url','')}][yellow]{r.get('full_name','')}[/yellow][/link]"
            url = f"[link={r.get('url','')}][yellow]{r.get('url','')}[/yellow][/link]"

            table.add_row("📛 Full Name", full_name)
            table.add_row("⭐ Stars", str(r.get("stars", 0)))
            table.add_row("🔥 Trendiness", str(trendiness_score(r, new_repos, newly_cross)))
            table.add_row("🌐 Sources", ", ".join(r.get("sources", [])) or "None")
            table.add_row("🏷️ Tags", ", ".join(r.get("tags", [])) or "None")
            table.add_row("🔗 URL", url)
            table.add_row("📝 Description", r.get("desc", ""))

            console.print(Panel(table, title=f"[bold blue]{title}[/bold blue]", expand=True))

    display_repos("CROSS-SIGNAL REPOS", cross)
    display_repos("NEW REPOS SINCE LAST SCAN", new_repos)
    display_repos("NEWLY CROSS-SIGNAL REPOS", newly_cross)

    scored = []
    for r, base_score in interesting[:20]:
        t_score = trendiness_score(r, new_repos, newly_cross)
        scored.append((r, base_score + t_score))
    scored = sorted(scored, key=lambda x: x[1], reverse=True)
    display_repos("TOP INTERESTING REPOS", [r for r, _ in scored[:10]])

    console.rule(f"[bold cyan]SCAN TIME: {datetime.now()}[/bold cyan]")

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
        console.print(f"[green][+] Fetching: {q}[/green]")
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
