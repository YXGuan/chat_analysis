"""Open the reports for results you already have, without running the pipeline again.

Usage (from the repo root, with the virtual environment active):

    python examples/local/view.py                            # list every result
    python examples/local/view.py wildchat-3-english-users   # open one result

This starts a small web server on this computer only. It needs no API key and
makes no model calls. Press Ctrl+C to stop it.
"""

import argparse
import functools
import html
import json
import socket
import sys
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from report import TEMPLATE, sample_label, write_report

OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_DIR = OUTPUT_DIR / ".cache"
REPORT_CODE = Path(__file__).parent / "report.py"
DATA_FILES = ("conversations.jsonl", "summaries.jsonl", "dimensionality.jsonl")

INDEX_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kura Results</title>
<style>
  :root {{
    color-scheme: light; --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e;
    --border: rgba(11, 11, 11, 0.10); --wash: rgba(11, 11, 11, 0.04);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark; --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7;
      --border: rgba(255, 255, 255, 0.10); --wash: rgba(255, 255, 255, 0.05);
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark; --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7;
    --border: rgba(255, 255, 255, 0.10); --wash: rgba(255, 255, 255, 0.05);
  }}
  body {{ margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 32px 16px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: var(--ink-2); margin: 0 0 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
  .card {{
    display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; border-radius: 10px;
    background: var(--surface); border: 1px solid var(--border); color: inherit; text-decoration: none;
  }}
  .card:hover {{ background: var(--wash); }}
  .card:focus-visible {{ outline: 2px solid var(--ink); outline-offset: 2px; }}
  .label {{ font-weight: 600; font-size: 16px; }}
  .meta {{ color: var(--ink-2); }}
  .open {{ margin-top: 6px; font-weight: 600; }}
</style>
<script>
  try {{
    const saved = localStorage.getItem("kura-report-theme");
    if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
  }} catch (e) {{ /* storage can be blocked; the system theme still applies */ }}
</script>
</head>
<body>
<div class="wrap">
  <h1>Kura results</h1>
  <p class="sub">Pick a result to open its report. These were made earlier, so nothing runs again.</p>
  <div class="grid">
{cards}
  </div>
</div>
</body>
</html>
"""


def find_results() -> list[Path]:
    """Return every results folder that has the files a report needs."""
    return sorted(
        path.parent
        for path in OUTPUT_DIR.glob("*/*/dimensionality.jsonl")
        if all((path.parent / name).exists() for name in DATA_FILES)
    )


def refresh_report(result: Path) -> None:
    """Rebuild a result's report if it is missing or older than its data or the report code."""
    report = result / "report.html"
    sources = [result / name for name in DATA_FILES] + [TEMPLATE, REPORT_CODE]
    if not report.exists() or report.stat().st_mtime < max(p.stat().st_mtime for p in sources):
        write_report(result, CACHE_DIR)


def describe(result: Path) -> dict[str, Any]:
    """Collect the numbers the index page shows for one result."""
    with open(result / "dimensionality.jsonl") as f:
        levels = [json.loads(line)["level"] for line in f if line.strip()]
    users, chats = set(), 0
    with open(result / "conversations.jsonl") as f:
        for line in f:
            chats += 1
            user = json.loads(line)["metadata"].get("user")
            if user:
                users.add(user)
    return {
        "label": sample_label(result.parent.name),
        "model": result.name,
        "chats": chats,
        "users": len(users),
        "clusters": len(levels),
        "levels": max(levels) + 1,
        "updated": datetime.fromtimestamp((result / "dimensionality.jsonl").stat().st_mtime),
        "link": f"{result.parent.name}/{result.name}/report.html",
    }


def write_index(results: list[Path]) -> None:
    """Write output/index.html, with one card per result."""
    cards = []
    for info in map(describe, results):
        numbers = [f"{info['chats']:,} chats"]
        if info["users"]:
            numbers.append(f"{info['users']} users")
        numbers += [f"{info['clusters']} clusters", f"{info['levels']} levels"]
        cards.append(
            f'    <a class="card" href="{html.escape(info["link"])}">'
            f'<span class="label">{html.escape(info["label"])}</span>'
            f'<span class="meta">{html.escape(info["model"])} · {" · ".join(numbers)}</span>'
            f'<span class="meta">Made {info["updated"]:%b %d, %Y at %H:%M}</span>'
            f'<span class="open">Open report</span></a>'
        )
    (OUTPUT_DIR / "index.html").write_text(INDEX_PAGE.format(cards="\n".join(cards)))


def find_free_port(start: int) -> int:
    """Return the first port from start onward that nothing else is using."""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    sys.exit(f"Ports {start} to {start + 19} are all in use. Pick another with --port.")


class QuietHandler(SimpleHTTPRequestHandler):
    """Serve files without printing a line for every request."""

    def log_message(self, format: str, *args: Any) -> None:
        pass


def main() -> None:
    """Refresh the reports, then serve them until Ctrl+C."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "result", nargs="?", help="a results folder to open, such as wildchat-3-english-users"
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = parser.parse_args()

    results = find_results()
    if not results:
        sys.exit("No results yet. Make some first with: python examples/local/run.py")

    page = ""
    if args.result:
        name = args.result.strip("/")
        matches = [r for r in results if name in (r.parent.name, f"{r.parent.name}/{r.name}")]
        if not matches:
            names = "\n  ".join(sorted({f"{r.parent.name}/{r.name}" for r in results}))
            sys.exit(f"No results named {name}. These are available:\n  {names}")
        newest = max(matches, key=lambda r: (r / "dimensionality.jsonl").stat().st_mtime)
        page = f"{newest.parent.name}/{newest.name}/report.html"

    for result in results:
        refresh_report(result)
    write_index(results)

    port = find_free_port(args.port)
    handler = functools.partial(QuietHandler, directory=str(OUTPUT_DIR))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Showing {len(results)} results at http://localhost:{port}/  (press Ctrl+C to stop)", flush=True)
        if not args.no_open:
            webbrowser.open(f"http://localhost:{port}/{page}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
