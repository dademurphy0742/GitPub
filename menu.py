#!/usr/bin/env python3

import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# Import your main script as a module
import subprocess

console = Console()

BANNER = r"""
[bold cyan]
   ____ _ _   ____        _     
  / ___(_) |_|  _ \ _   _| |__  
 | |  _| | __| |_) | | | | '_ \ 
 | |_| | | |_|  __/| |_| | |_) |
  \____|_|\__|_|    \__,_|_.__/ 

        GitPub
[/bold cyan]
"""

# ── Helpers ──────────────────────────────────────────

def run_scan(queries, limit, merge, token):
    cmd = ["python3", "gitpub.py"]

    cmd.extend(queries)

    if limit:
        cmd.extend(["--limit", str(limit)])

    if merge:
        cmd.append("--merge")

    if token:
        cmd.extend(["--token", token])

    console.print(f"\n[green][+] Running:[/green] {' '.join(cmd)}\n")
    subprocess.run(cmd)


def get_queries():
    console.print("\n[yellow]Enter queries (space-separated)[/yellow]")
    q = Prompt.ask(">>>")
    return q.strip().split()


def load_last_queries():
    history_file = "last_queries.txt"
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return f.read().strip().split()
    return []


def save_last_queries(queries):
    with open("last_queries.txt", "w") as f:
        f.write(" ".join(queries))


# ── Menu ─────────────────────────────────────────────

def menu():
    queries = []
    limit = 30
    merge = True
    token = None

    while True:
        console.clear()
        console.print(Panel(BANNER, expand=True))

        console.print("[bold]Current Settings:[/bold]")
        console.print(f" Queries : {queries or '[red]None[/red]'}")
        console.print(f" Limit   : {limit}")
        console.print(f" Merge   : {merge}")
        console.print(f" Token   : {'Set' if token else 'None'}")

        console.print("\n[bold cyan]Menu:[/bold cyan]")
        console.print(" 1) Set Queries")
        console.print(" 2) Load Last Queries")
        console.print(" 3) Set Result Limit")
        console.print(" 4) Toggle Merge Mode")
        console.print(" 5) Set GitHub Token")
        console.print(" 6) Run Scan")
        console.print(" 7) Quick Scan (AI preset)")
        console.print(" 0) Exit")

        choice = Prompt.ask("\nSelect option", default="6")

        if choice == "1":
            queries = get_queries()
            save_last_queries(queries)

        elif choice == "2":
            queries = load_last_queries()
            console.print(f"[green]Loaded:[/green] {queries}")
            input("Press Enter...")

        elif choice == "3":
            limit = int(Prompt.ask("Enter limit", default=str(limit)))

        elif choice == "4":
            merge = not merge

        elif choice == "5":
            token = Prompt.ask("Enter GitHub token (leave blank to unset)", default="") or None

        elif choice == "6":
            if not queries:
                console.print("[red][!] No queries set[/red]")
                input("Press Enter...")
                continue
            run_scan(queries, limit, merge, token)
            input("\nPress Enter to return to menu...")

        elif choice == "7":
            queries = ["ai", "automation", "cli", "scraper"]
            save_last_queries(queries)
            run_scan(queries, limit, True, token)
            input("\nPress Enter to return to menu...")

        elif choice == "0":
            console.print("[red]Exiting...[/red]")
            sys.exit()

        else:
            console.print("[red]Invalid choice[/red]")
            input("Press Enter...")


# ── Entry ────────────────────────────────────────────

if __name__ == "__main__":
    menu()
