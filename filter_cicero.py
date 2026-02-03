import time
import traceback
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime

SOURCE_RSS = "https://www.cicero.de/rss.xml"
OUTPUT_FILE = "index.xml"
DEBUG_FILE = "debug.txt"

PAYWALL_MARKERS = [
    "Cicero-Plus",
    "Cicero Plus",
    "JETZT TESTEN",
    "Monatsabo",
    "Sie haben schon ein Cicero-Plus Abo",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; cicero-free-rss/1.0)"}

def xml_escape(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )

def fetch_source_feed():
    # Fetch RSS via requests (more reliable in GitHub Actions than feedparser fetching itself)
    r = requests.get(SOURCE_RSS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return feedparser.parse(r.content), r.status_code, r.headers.get("content-type", "")

def is_paywalled(url: str) -> bool:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    html = r.text

    if any(m in html for m in PAYWALL_MARKERS):
        return True

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return any(m in text for m in PAYWALL_MARKERS)

def main():
    debug_lines = []
    debug_lines.append(f"run_utc={datetime.now(timezone.utc).isoformat()}")

    try:
        feed, status, ctype = fetch_source_feed()
        debug_lines.append(f"source_rss_http_status={status}")
        debug_lines.append(f"source_rss_content_type={ctype}")
        debug_lines.append(f"source_entries_count={len(feed.entries)}")
    except Exception as e:
        debug_lines.append("ERROR_fetch_source_feed")
        debug_lines.append(repr(e))
        debug_lines.append(traceback.format_exc())
        # Write empty RSS + debug and exit
        write_outputs([], debug_lines)
        return

    items_xml = []
    kept = 0
    dropped_paywalled = 0
    dropped_no_link = 0
    check_errors = 0

    for e in feed.entries[:40]:
        link = e.get("link")
        if not link:
            dropped_no_link += 1
            continue

        try:
            if is_paywalled(link):
                dropped_paywalled += 1
                continue
        except Exception:
            # fail-open here so the feed is not empty if Cicero blocks article fetches
            check_errors += 1

        title = xml_escape(e.get("title", ""))
        desc = xml_escape(e.get("summary", ""))
        pub = xml_escape(e.get("published", ""))

        items_xml.append(f"""
    <item>
      <title>{title}</title>
      <link>{xml_escape(link)}</link>
      <pubDate>{pub}</pubDate>
      <description>{desc}</description>
    </item>
        """)
        kept += 1
        time.sleep(1.0)

    debug_lines.append(f"kept_items={kept}")
    debug_lines.append(f"dropped_paywalled={dropped_paywalled}")
    debug_lines.append(f"dropped_no_link={dropped_no_link}")
    debug_lines.append(f"paywall_check_errors={check_errors}")

    write_outputs(items_xml, debug_lines)

def write_outputs(items_xml, debug_lines):
    now = format_datetime(datetime.now(timezone.utc))
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Cicero (free-only-ish)</title>
    <link>https://www.cicero.de/</link>
    <description>Filtered RSS feed; see debug.txt for run details</description>
    <lastBuildDate>{now}</lastBuildDate>
    {''.join(items_xml)}
  </channel>
</rss>
"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(debug_lines) + "\n")

if __name__ == "__main__":
    main()
