"""Pipeline entrypoint: one run = one weekly digest, committed by CI."""

from datetime import UTC, datetime, timedelta

from keepup.bucketize import bucketize
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
        stories = synthesize(topic.name, selected, cfg.model) if topic.synthesize else None

        # Buckets, when configured, replace source-grouping: the LLM sorts items
        # into the buckets (mutating item.source); a failed call leaves source
        # groups intact so the section degrades to a flat list.
        groups, group_of = topic.group_roster(), topic.group_of()
        bucketed = False
        if topic.buckets and (roster := bucketize(topic.name, selected, topic.buckets, cfg.model)):
            groups, group_of, bucketed = roster, {b: b for b in roster}, True

        if not topic.synthesize:
            outcome = f"{len(groups)} buckets" if bucketed else "verbatim headlines"
        elif stories is None:
            outcome = "links-only"
        else:
            outcome = f"{len(stories)} stories"
        note = f"; failed: {', '.join(failed)}" if failed else ""
        print(f"{topic.name}: {len(raw)} fetched → {len(selected)} selected → {outcome}{note}")
        digests.append(
            TopicDigest(
                topic.name,
                selected,
                stories,
                failed,
                topic.synthesize,
                topic.descriptions,
                groups,
                group_of,
            )
        )

    render(digests, week, now)
    print(f"rendered docs/index.html + docs/archive/{week}.html")


if __name__ == "__main__":
    main()
