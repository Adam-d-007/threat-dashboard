"""Hourly RSS collection: python -m pipeline.collect [--fixtures]

Feeds keep only their newest items (teraz.sk: 15), so fetching twice a day misses most of
them. This job fetches every enabled RSS source each hour and keeps the last 48 h of items
in rss_buffer.json, which the twice-daily pipeline merges into its own fetch. It writes no
other file, so its commits and the pipeline's never touch the same file.
"""

import argparse
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from .main import FIXTURE_NOW, fetch_all, load_config, normalize_all
from .process.dedupe import dedupe
from .store import state

KEEP = timedelta(hours=48)

log = logging.getLogger("pipeline.collect")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m pipeline.collect")
    p.add_argument("--fixtures", action="store_true", help="read pipeline/fixtures, no network")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    p.add_argument("--commit-msg-file", type=Path)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    now = FIXTURE_NOW if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    sources, _ = load_config()
    rss_sources = [s for s in sources if s["enabled"] and s["adapter"] == "rss"]
    results = fetch_all(rss_sources, [], now, now, args.fixtures)
    # Read-only: dates undated items the way the pipeline already did.
    seen = state.load(args.state_dir)["seen"]
    fresh = normalize_all(rss_sources, results, now, seen)

    try:
        old, reset = state.load_buffer(args.state_dir), False
    except ValidationError:
        log.exception("rss_buffer.json is invalid; starting a new buffer")
        old, reset = [], True
    old_ids = {i.id for i in old}
    kept = [i for i in dedupe(old + fresh) if now - i.fetched_at <= KEEP]
    new = sum(1 for i in kept if i.id not in old_ids)
    state.write_buffer(args.state_dir, kept, now)

    failed = [r.source_id for r in results.values() if not r.ok]
    msg = f"collect {now:%Y-%m-%dT%H:%M} +{new} new, {len(kept)} buffered"
    if failed:
        msg += f", failed: {' '.join(failed)}"
    if reset:
        msg += ", invalid buffer replaced"
    log.info(msg)
    if args.commit_msg_file:
        args.commit_msg_file.write_text(msg + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
