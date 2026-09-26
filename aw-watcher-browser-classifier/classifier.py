"""
aw-watcher-browser-classifier
------------------------------
A custom ActivityWatch watcher that reads events from the existing
aw-watcher-web bucket (tab title + URL) and classifies each event into
a research-relevant category, then writes the classified events into
a new bucket so they're queryable/visualizable separately.
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from aw_client import ActivityWatchClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CLIENT_NAME = "aw-watcher-browser-classifier"
POLL_INTERVAL_SECONDS = 10
SOURCE_BUCKET_SUFFIX = "aw-watcher-web"
LOOKBACK_SECONDS = 30

CATEGORY_RULES = {
    "research": [
        "arxiv.org", "scholar.google.com", "jstor.org", "wikipedia.org",
        "pubmed.ncbi.nlm.nih.gov", "ieee.org", "acm.org", "researchgate.net",
    ],
    "dev_tools": [
        "github.com", "stackoverflow.com", "docs.python.org", "developer.mozilla.org",
        "leetcode.com", "neetcode.io", "npmjs.com", "pypi.org",
    ],
    "social_distraction": [
        "reddit.com", "instagram.com", "twitter.com", "x.com",
        "tiktok.com", "facebook.com", "youtube.com",
    ],
    "communication": [
        "mail.google.com", "outlook.com", "slack.com", "discord.com",
    ],
}

DEFAULT_CATEGORY = "uncategorized"


def classify_url(url: str) -> str:
    if not url:
        return DEFAULT_CATEGORY
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return DEFAULT_CATEGORY
    for category, domains in CATEGORY_RULES.items():
        if any(known_domain in domain for known_domain in domains):
            return category
    return DEFAULT_CATEGORY


def find_web_bucket(client: ActivityWatchClient):
    buckets = client.get_buckets()
    for bucket_id in buckets:
        if SOURCE_BUCKET_SUFFIX in bucket_id:
            return bucket_id
    return None


def main():
    client = ActivityWatchClient(CLIENT_NAME, testing=False)

    source_bucket = find_web_bucket(client)
    if not source_bucket:
        log.error(
            "Could not find an aw-watcher-web bucket. Make sure the "
            "ActivityWatch browser extension is installed and logging."
        )
        return

    output_bucket = f"{CLIENT_NAME}_{client.client_hostname}"
    client.create_bucket(output_bucket, event_type="classified_browser_activity", queued=True)
    log.info("Reading from: %s", source_bucket)
    log.info("Writing to:   %s", output_bucket)

    with client:
        while True:
            since = datetime.now(timezone.utc) - timedelta(seconds=LOOKBACK_SECONDS)
            recent_events = client.get_events(source_bucket, start=since, limit=50)

            for event in recent_events:
                url = event.data.get("url", "")
                title = event.data.get("title", "")
                category = classify_url(url)

                classified_event = {
                    "timestamp": event.timestamp,
                    "duration": event.duration.total_seconds() if event.duration else 0,
                    "data": {"url": url, "title": title, "category": category},
                }
                client.heartbeat(
                    output_bucket, classified_event,
                    pulsetime=POLL_INTERVAL_SECONDS + 5, queued=True,
                )
                log.info("Classified [%s] -> %s", category, url or title)

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped.")
