import time
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime

SOURCE_RSS = "https://www.cicero.de/rss.xml"
OUTPUT_FILE = "index.xml"  # Pages will host this at https://<user>.github.io/<repo>/index.xml

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

def is_paywalled(url: str) -> bool:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    html = r.text

    # Fast check
    for m in PAYWALL_MARKERS:
        if m in html:
            return True

    # Visible text check
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return any(m in text for m in PAYWALL_MARKERS)

def main():
    feed = feedparser.parse(SOURCE_RSS)

    items_xml = []
    entries = feed.entries[:40]  # adjust if you want more/less

    for e in entries:
        link = e.get("link")
        if not link:
            continue

        try:
            if is_paywalled(link):
                continue
        except Exception:
            # Fail-closed: if request fails, drop item so paid items do not slip through
            continue

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

        time.sleep(1.0)  # polite delay

    now = format_datetime(datetime.now(timezone.utc))

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Cicero (free-only)</title>
    <link>https://www.cicero.de/</link>
    <description>Filtered RSS feed that removes Cicero+ paywalled articles</description>
    <lastBuildDate>{now}</lastBuildDate>
    {''.join(items_xml)}
  </channel>
</rss>
"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

if __name__ == "__main__":
    main()
