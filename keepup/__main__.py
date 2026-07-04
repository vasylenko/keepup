"""Pipeline entrypoint: one run = one weekly digest, committed by CI."""

from datetime import UTC, datetime, timedelta

from keepup.config import load_config
from keepup.fetchers import fetch_topic
from keepup.models import TopicDigest
from keepup.render import render
from keepup.select import dedupe, select
from keepup.synthesize import synthesize


def main() -> None:
    cfg = load_config()
    now = datetime.now(UTC)
    since = now - timedelta(days=7)
    week = f"{now:%G}-W{now:%V}"  # ISO week names the archive page

    digests = []
    for topic in cfg.topics:
        raw, failed = fetch_topic(topic, since)
        selected = select(dedupe(raw))
        stories = synthesize(topic.name, selected, cfg.model)
        outcome = "links-only" if stories is None else f"{len(stories)} stories"
        note = f"; failed: {', '.join(failed)}" if failed else ""
        print(f"{topic.name}: {len(raw)} fetched → {len(selected)} selected → {outcome}{note}")
        digests.append(TopicDigest(topic.name, selected, stories, failed))

    render(digests, week, now)
    print(f"rendered docs/index.html + docs/archive/{week}.html")


if __name__ == "__main__":
    main()
