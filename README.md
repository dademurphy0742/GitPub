# GitPub


![Alt text](file_0000000024cc71f7a411e879922fcc94.png)


GitPub is a powerful command-line tool for monitoring and analyzing GitHub repositories across multiple keywords. It fetches, merges, and scores repositories to provide a trendiness report, helping you spot hot projects, emerging tools, and cross-signal patterns in real-time.


---

Features

🔍 Search GitHub repositories by multiple keywords.

📊 Merge and normalize results from multiple queries.

🌟 Trendiness scoring based on stars, multi-source signals, and novelty.

📈 Extract hot terms and naming patterns across repositories.

🔄 Track new repositories since last scan.

🧩 Detect repositories appearing in multiple queries (cross-signal repos).

💾 Save scans in JSON format for historical tracking.



---

Installation

1. Clone the repository:


'''bash
git clone https://github.com/dademurphy0742/GitPub.git
cd GitPub

2. Install dependencies (requires Python 3.x):


python3 -m venv venv

source venv/bin/activate

pip install requests


---

Usage

Run GitPub from the command line:

python3 gitpub.py <keyword1> <keyword2> ... [--limit N] [--merge]

Options

<keywords> – List of keywords to search for on GitHub.

--limit N – Number of repositories to fetch per keyword (default: 30).

--merge – Merge results from all queries and auto-tag repos.


Example

python3 gitpub.py kali ai scraping cli --merge

This will:

Fetch repositories for the keywords kali, ai, scraping, and cli.

Merge results into a unified report.

Detect hot terms, patterns, cross-signal repos, new repos, and top interesting projects.

Save the scan in scans/ with a timestamped JSON file.



---

Output

GitPub generates a merged signal report in the terminal, including:

Hot Terms – Frequently occurring words across repo names and descriptions.

Patterns – Common naming patterns like *-ai or auto-*.

Cross-Signal Repos – Repos appearing in multiple queries.

New Repos – Repositories not seen in the previous scan.

Newly Cross-Signal Repos – Repos newly appearing in multiple queries.

Top Interesting Repos – Trendiness scored repositories with stars, tags, and sources.


A JSON scan file is saved in scans/ for historical tracking.


---

Dependencies

Python 3.x

requests



---

License

MIT License – Free to use, modify, and distribute.
