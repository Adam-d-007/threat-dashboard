"""Hourly collection: python -m pipeline.collect [--fixtures]

Feeds keep only their newest items (teraz.sk: 15), so fetching twice a day misses most of
them; and GDELT rate-limits GitHub's shared servers, so one attempt per twice-daily run
usually fails. This job fetches every enabled RSS source and runs the GDELT DOC queries
(3-hour windows) each hour, keeps the last 48 h of items in rss_buffer.json with a health
record per source, and the twice-daily pipeline merges the buffer into its own fetch. It
writes no other file, so its commits and the pipeline's never touch the same file.
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
GDELT_WINDOW = timedelta(hours=3)

log = logging.getLogger("pipeline.collect")


def update_health(health: dict, results: dict, now: datetime) -> dict:
    """Each collected source's last success and error, from this run's results."""
    out = dict(health)
    for sid, res in results.items():
        h = health.get(sid, {})
        last = now.isoformat() if res.ok else h.get("last_success")
        entry = {"last_error": h.get("last_error") if res.ok else now.isoformat(),
                 "error": None if res.ok else res.error, "items": len(res.items)}
        if res.parts:
            # GDELT rate-limits GitHub, so all queries rarely succeed in one run. The source
            # counts as succeeding once every query has succeeded at some point: its
            # last_success is the oldest of its queries' last successes.
            parts = {q: t for q, t in (h.get("parts") or {}).items() if q in res.parts}
            parts |= dict.fromkeys(res.parts_ok, now.isoformat())
            last = min(parts[q] for q in res.parts) if set(parts) >= set(res.parts) else None
            entry["parts"] = parts
        out[sid] = {"last_success": last, **entry}
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m pipeline.collect")
    p.add_argument("--fixtures", action="store_true", help="read pipeline/fixtures, no network")
    p.add_argument("--state-dir", type=Path, default=Path("state"))
    p.add_argument("--commit-msg-file", type=Path)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    now = FIXTURE_NOW if args.fixtures else datetime.now(UTC).replace(microsecond=0)
    sources, queries = load_config()
    wanted = {"rss"} if args.fixtures else {"rss", "gdelt_doc"}
    collected = [s for s in sources
                 if s["enabled"] and s["adapter"] in wanted and s.get("hourly", True)]
    results = fetch_all(collected, queries, now - GDELT_WINDOW, now, args.fixtures)
    # Read-only: dates undated items the way the pipeline already did.
    seen = state.load(args.state_dir)["seen"]
    fresh = normalize_all(collected, results, now, seen)

    try:
        buf, reset = state.load_buffer_full(args.state_dir), False
        old, health = buf.items, dict(buf.health)
    except ValidationError:
        log.exception("rss_buffer.json is invalid; starting a new buffer")
        old, health, reset = [], {}, True
    health = update_health(health, results, now)
    old_ids = {i.id for i in old}
    kept = [i for i in dedupe(old + fresh) if now - i.fetched_at <= KEEP]
    new = sum(1 for i in kept if i.id not in old_ids)
    state.write_buffer(args.state_dir, kept, now, health)

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
