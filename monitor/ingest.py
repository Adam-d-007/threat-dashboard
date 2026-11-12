"""Stage 1, ingest: news items become articles waiting for a label.

While the old pipeline runs beside this one, the items come from its hourly collector's buffer
(rss_buffer.json), so no news site is fetched twice. The keyword prefilter only decides what is
worth a model's time; it never labels anything.
"""

from datetime import datetime, timedelta

from pipeline.models import Item
from pipeline.process.prefilter import prefilter

from .models import Article

KEEP = timedelta(days=7)
# An article labelled "none", or given up, is only kept while the buffer can still hand it in
# again (48 hours), so it is not asked about twice.
KEEP_UNUSED = timedelta(hours=48)


def ingest(articles: dict[str, Article], items: list[Item], groups: dict[str, str],
           prefilter_cfg: dict, now: datetime, oldest: datetime) -> int:
    """Add the prefiltered items published since `oldest` and not seen before; returns how
    many. An article already known takes over the outlets that have reported the same story
    since. Unlabelled articles from before `oldest` are dropped: they are from before this
    pipeline started and were never its to label."""
    for a in [a for a in articles.values() if a.label is None and a.published_at < oldest]:
        del articles[a.id]
    new = 0
    for item in prefilter([i for i in items if i.published_at >= oldest], groups, prefilter_cfg):
        known = articles.get(item.id)
        if known:
            known.also_reported_by = sorted(set(known.also_reported_by) | set(
                item.also_reported_by))
            continue
        articles[item.id] = Article(
            id=item.id, source_id=item.source_id, tier=item.tier, url=item.url, title=item.title,
            lang=item.lang, published_at=item.published_at, fetched_at=item.fetched_at,
            snippet=item.snippet, domain=item.domain,
            also_reported_by=sorted(item.also_reported_by), first_seen=now)
        new += 1
    return new


def prune(articles: dict[str, Article], now: datetime) -> None:
    for a in list(articles.values()):
        unused = a.given_up or (a.label is not None and a.label.kind == "none")
        if now - a.first_seen > (KEEP_UNUSED if unused else KEEP):
            del articles[a.id]
