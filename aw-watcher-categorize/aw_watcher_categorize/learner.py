"""
Batch rule learning and server synchronization.
Analyzes past uncategorized events, groups activities by duration,
queries the AI engine, and synthesizes updated category rules.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from aw_client import ActivityWatchClient
from aw_client import queries
from aw_client.classes import default_classes, get_classes
from tabulate import tabulate

from .ai_client import AIClassifierClient, ClassificationResult
from .classifier import MultiTierClassifier

logger = logging.getLogger(__name__)


def fetch_uncategorized_events(
    client: ActivityWatchClient,
    days: int = 7,
    current_classes: Optional[List[Tuple[List[str], Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """Fetches canonical desktop activity events and extracts uncategorized entries."""
    classes = current_classes or get_classes()
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=days)
    timeperiods = [(start, now)]

    hostname = client.client_hostname
    bid_window = f"aw-watcher-window_{hostname}"
    bid_afk = f"aw-watcher-afk_{hostname}"

    # Verify buckets exist
    buckets = client.get_buckets()
    if bid_window not in buckets:
        logger.warning(f"Window bucket '{bid_window}' not found on server.")
        return []

    query = f"""
    events = flood(query_bucket("{bid_window}"));
    """
    if bid_afk in buckets:
        query = f"""
        events = flood(query_bucket("{bid_window}"));
        not_afk = flood(query_bucket("{bid_afk}"));
        events = filter_period_intersect(events, filter_keyvals(not_afk, "status", ["not-afk"]));
        """

    classes_json = json.dumps(classes)
    query += f"""
    events = categorize(events, {classes_json});
    events = filter_keyvals(events, "$category", [["Uncategorized"]]);
    RETURN = events;
    """

    try:
        res = client.query(query, timeperiods)
        if res and isinstance(res, list) and len(res) > 0:
            return res[0]
    except Exception as exc:
        logger.warning(f"Query for uncategorized events failed: {exc}")

    return []


def aggregate_uncategorized(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregates uncategorized events by (app, title), summing total duration."""
    aggregated: Dict[Tuple[str, str], float] = defaultdict(float)
    for event in events:
        data = event.get("data", {})
        app = data.get("app", "").strip()
        title = data.get("title", "").strip()
        duration = float(event.get("duration", 0.0))
        if app or title:
            aggregated[(app, title)] += duration

    # Convert to sorted list
    sorted_items = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    return [
        {"app": app, "title": title, "duration": dur}
        for (app, title), dur in sorted_items
    ]


def format_duration(seconds: float) -> str:
    """Formats duration in seconds into human-readable string (e.g. '1h 24m')."""
    mins = int(seconds // 60)
    hours = mins // 60
    rem_mins = mins % 60
    if hours > 0:
        return f"{hours}h {rem_mins}m"
    return f"{rem_mins}m"


def run_learning_session(
    client: ActivityWatchClient,
    ai_client: AIClassifierClient,
    classifier: MultiTierClassifier,
    days: int = 7,
    max_items: int = 25,
    apply_rules: bool = False,
) -> None:
    """Main batch learning workflow."""
    print(f"\n🔍 Scanning last {days} days of ActivityWatch history for uncategorized events...")
    events = fetch_uncategorized_events(client, days=days)
    if not events:
        print("🎉 No uncategorized events found or no window history available!")
        return

    aggregated = aggregate_uncategorized(events)
    top_items = aggregated[:max_items]
    print(f"📊 Found {len(events)} uncategorized events ({len(aggregated)} unique app/window titles).")
    print(f"🤖 Consulting AI model ({ai_client.model}) on top {len(top_items)} most frequent activities...\n")

    ai_results = ai_client.classify_batch(top_items, existing_categories=classifier.get_all_category_names())

    table_data = []
    new_rules: Dict[Tuple[str, ...], List[str]] = defaultdict(list)

    for item, ai_res in zip(top_items, ai_results):
        app = item["app"]
        title = item["title"]
        dur_str = format_duration(item["duration"])
        display_title = (title[:40] + "...") if len(title) > 40 else title

        if ai_res and ai_res.category and ai_res.category != ["Uncategorized"]:
            cat_name = " > ".join(ai_res.category)
            regex = ai_res.regex or app or title
            table_data.append([app, display_title, dur_str, cat_name, regex, f"{int(ai_res.confidence * 100)}%"])
            new_rules[tuple(ai_res.category)].append(regex)
        else:
            table_data.append([app, display_title, dur_str, "Uncategorized", "-", "-"])

    print(tabulate(table_data, headers=["App", "Title", "Duration", "Suggested Category", "Regex", "Confidence"], tablefmt="grid"))

    if not new_rules:
        print("\nNo new rules generated.")
        return

    print(f"\n✨ Generated rules for {len(new_rules)} categories.")

    # Check if we should apply rules
    should_apply = apply_rules
    if not should_apply:
        try:
            choice = input("\nWould you like to save these new rules to aw-server 'classes' setting? (y/N): ").strip().lower()
            should_apply = choice in ["y", "yes"]
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return

    if should_apply:
        apply_new_rules_to_server(client, new_rules)


def apply_new_rules_to_server(
    client: ActivityWatchClient,
    new_rules: Dict[Tuple[str, ...], List[str]],
) -> None:
    """Updates the server-side 'classes' setting by merging newly synthesized rules."""
    try:
        raw_classes = client.get_setting("classes")
    except Exception:
        raw_classes = None

    if not raw_classes or not isinstance(raw_classes, list):
        # Convert default_classes
        raw_classes = [
            {"id": i, "name": name, "rule": rule}
            for i, (name, rule) in enumerate(default_classes)
        ]

    # Existing category map: tuple(name) -> item dict
    existing_map = {}
    max_id = 0
    for item in raw_classes:
        name_key = tuple(item.get("name", []))
        existing_map[name_key] = item
        item_id = item.get("id", 0)
        if isinstance(item_id, int) and item_id > max_id:
            max_id = item_id

    # Merge new rules
    for cat_tuple, regex_list in new_rules.items():
        clean_regexes = [r for r in regex_list if r and r != "-"]
        if not clean_regexes:
            continue
        merged_pattern = "|".join(dict.fromkeys(clean_regexes))  # deduplicated

        if cat_tuple in existing_map:
            # Append regex
            existing_rule = existing_map[cat_tuple].setdefault("rule", {})
            current_pattern = existing_rule.get("regex", "")
            if current_pattern:
                existing_rule["regex"] = f"{current_pattern}|{merged_pattern}"
            else:
                existing_rule["regex"] = merged_pattern
                existing_rule["type"] = "regex"
                existing_rule["ignore_case"] = True
        else:
            max_id += 1
            new_item = {
                "id": max_id,
                "name": list(cat_tuple),
                "rule": {
                    "type": "regex",
                    "regex": merged_pattern,
                    "ignore_case": True,
                },
            }
            raw_classes.append(new_item)
            existing_map[cat_tuple] = new_item

    try:
        client.set_setting("classes", json.dumps(raw_classes))
        print("✅ Successfully updated server 'classes' setting with new rules!")
    except Exception as exc:
        logger.error(f"Failed to update server 'classes' setting: {exc}")
