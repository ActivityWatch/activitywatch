"""
Main entry point for aw-watcher-categorize.
Handles real-time categorization heartbeats and CLI commands.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from time import sleep
from typing import Optional

from aw_client import ActivityWatchClient
from aw_client.classes import get_classes
from aw_core.log import setup_logging
from aw_core.models import Event

from .ai_client import AIClassifierClient
from .classifier import MultiTierClassifier
from .config import parse_args
from .learner import run_learning_session, apply_new_rules_to_server

logger = logging.getLogger(__name__)


def compute_pulsetime(poll_time: float) -> float:
    """Scale pulsetime with poll_time so OS scheduling jitter doesn't break heartbeat chains."""
    return max(poll_time * 1.5, poll_time + 1.0)


def main():
    args = parse_args()

    setup_logging(
        name="aw-watcher-categorize",
        testing=args.testing,
        verbose=args.verbose,
        log_stderr=True,
        log_file=True,
    )

    client = ActivityWatchClient(
        "aw-watcher-categorize", host=args.host, port=args.port, testing=args.testing
    )

    ai_client = AIClassifierClient(
        provider=args.ai_provider,
        api_key=args.ai_api_key,
        base_url=args.ai_base_url,
        model=args.ai_model,
    )

    logger.info(
        f"Initialized AI client: provider={ai_client.provider}, model={ai_client.model}, "
        f"configured={'yes' if ai_client.is_configured() else 'no'}"
    )

    # Fetch server rules
    server_rules = get_classes()
    classifier = MultiTierClassifier(
        server_rules=server_rules,
        ai_client=ai_client,
        enable_heuristics=args.enable_heuristics,
    )

    # If --learn mode requested, run batch learner and exit
    if args.learn:
        client.wait_for_start()
        run_learning_session(
            client=client,
            ai_client=ai_client,
            classifier=classifier,
            days=args.learn_days,
            apply_rules=args.apply_learned_rules,
        )
        return

    # Real-time watcher mode
    bucket_id = f"{client.client_name}_{client.client_hostname}"
    event_type = "categorization"

    client.create_bucket(bucket_id, event_type, queued=True)
    logger.info(f"aw-watcher-categorize started. Target bucket: {bucket_id}")
    client.wait_for_start()

    window_bucket = f"aw-watcher-window_{client.client_hostname}"
    web_bucket = f"aw-watcher-web_{client.client_hostname}"

    with client:
        while True:
            # Check for orphan process
            if os.getppid() == 1:
                logger.info("aw-watcher-categorize stopped because parent process died")
                break

            try:
                # 1. Fetch latest window event
                window_events = client.get_events(window_bucket, limit=1)
                if not window_events:
                    sleep(args.poll_time)
                    continue

                latest_window = window_events[0]
                app = latest_window.data.get("app", "")
                title = latest_window.data.get("title", "")
                url = ""

                # Try to fetch current web tab URL if available
                try:
                    web_events = client.get_events(web_bucket, limit=1)
                    if web_events:
                        web_data = web_events[0].data
                        # Verify web event is roughly contemporaneous
                        if abs((latest_window.timestamp - web_events[0].timestamp).total_seconds()) < 10:
                            url = web_data.get("url", "")
                except Exception:
                    pass

                # 2. Run multi-tier classification
                category, confidence, source, suggested_regex = classifier.classify(
                    app=app,
                    title=title,
                    url=url,
                    use_ai=True,
                )

                logger.debug(
                    f"Classified '{app} - {title}': {category} (conf={confidence:.2f}, source={source})"
                )

                # 3. Emit heartbeat
                now = datetime.now(timezone.utc)
                data = {
                    "app": app,
                    "title": title,
                    "url": url,
                    "$category": category,
                    "confidence": confidence,
                    "source": source,
                }
                event = Event(timestamp=now, data=data)
                pulsetime = compute_pulsetime(args.poll_time)
                client.heartbeat(bucket_id, event, pulsetime=pulsetime, queued=True)

                # 4. Optional auto-update server rules
                if args.auto_update_classes and source == "ai" and suggested_regex and confidence >= 0.85:
                    new_rule = {tuple(category): [suggested_regex]}
                    apply_new_rules_to_server(client, new_rule)
                    # Refresh server rules in classifier
                    classifier.set_server_rules(get_classes())

            except KeyboardInterrupt:
                logger.info("aw-watcher-categorize stopped by keyboard interrupt")
                break
            except Exception as exc:
                logger.exception(f"Error in categorization loop: {exc}")

            sleep(args.poll_time)


if __name__ == "__main__":
    main()
