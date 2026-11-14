#!/usr/bin/env python3
"""Fetch headlines from Fox News, Fox Business, Tousi TV and the PBD Podcast.

Writes data/news.json. Browsers cannot read these feeds directly (CORS),
so this script is meant to run in GitHub Actions on a schedule.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
MAX_ITEMS = 300
TZ = ZoneInfo("America/Chicago")
UA = "NewsTracker/1.0 (personal news reader; +https://phillipalvaranga-arch.github.io/news-tracker/)"
CTX = ssl.create_default_context()

NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

# Official Fox News and Fox Business Google Publisher RSS feeds,
# listed at https://www.foxnews.com/story/foxnews-com-rss-feeds
# Texas / Dallas / DFW feeds at this host return HTTP 400, so that section is omitted.
FOX_FEEDS = [
    {"id": "fox-news-latest", "name": "Fox News — Latest", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/latest.xml", "sections": ["latest"], "kind": "article"},
    {"id": "fox-news-us", "name": "Fox News — U.S.", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/us.xml", "sections": ["us"], "kind": "article"},
    {"id": "fox-news-world", "name": "Fox News — World", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/world.xml", "sections": ["world"], "kind": "article"},
    {"id": "fox-news-politics", "name": "Fox News — Politics", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/politics.xml", "sections": ["politics"], "kind": "article"},
    {"id": "fox-news-health", "name": "Fox News — Health", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/health.xml", "sections": ["health"], "kind": "article"},
    {"id": "fox-news-tech", "name": "Fox News — Tech", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/tech.xml", "sections": ["tech"], "kind": "article"},
    {"id": "fox-news-sports", "name": "Fox News — Sports", "source": "Fox News", "source_id": "fox-news",
     "url": "https://moxie.foxnews.com/google-publisher/sports.xml", "sections": ["sports"], "kind": "article"},
    {"id": "fox-business-latest", "name": "Fox Business — Latest", "source": "Fox Business", "source_id": "fox-business",
     "url": "https://moxie.foxbusiness.com/google-publisher/latest.xml", "sections": ["business"], "kind": "article"},
    {"id": "fox-business-markets", "name": "Fox Business — Markets", "source": "Fox Business", "source_id": "fox-business",
     "url": "https://moxie.foxbusiness.com/google-publisher/markets.xml", "sections": ["business"], "kind": "article"},
    {"id": "fox-business-economy", "name": "Fox Business — Economy", "source": "Fox Business", "source_id": "fox-business",
     "url": "https://moxie.foxbusiness.com/google-publisher/economy.xml", "sections": ["business"], "kind": "article"},
    {"id": "fox-business-technology", "name": "Fox Business — Technology", "source": "Fox Business", "source_id": "fox-business",
     "url": "https://moxie.foxbusiness.com/google-publisher/technology.xml", "sections": ["business", "tech"], "kind": "article"},
    {"id": "fox-business-personal-finance", "name": "Fox Business — Personal Finance", "source": "Fox Business", "source_id": "fox-business",
     "url": "https://moxie.foxbusiness.com/google-publisher/personal-finance.xml", "sections": ["business"], "kind": "article"},
    {"id": "fox-business-real-estate", "name": "Fox Business — Real Estate", "source": "Fox Business", "source_id": "fox-business",
     "url": "https://moxie.foxbusiness.com/google-publisher/real-estate.xml", "sections": ["business"], "kind": "article"},
]

# Official YouTube channels, confirmed via https://www.youtube.com/@tousitv
# and https://www.youtube.com/@pbdpodcast (canonical channel URLs).
YOUTUBE = [
    {"id": "tousi-tv", "name": "Tousi TV", "source": "Tousi TV", "source_id": "tousi-tv",
     "channel_id": "UCjJec0wv1EUomjrBNt1xCTA", "handle": "@tousitv",
     "feed": "https://www.youtube.com/feeds/videos.xml?channel_id=UCjJec0wv1EUomjrBNt1xCTA",
     "sections": ["video"], "kind": "video"},
    {"id": "pbd-podcast", "name": "PBD Podcast", "source": "PBD Podcast", "source_id": "pbd-podcast",
     "channel_id": "UCGX7nGXpz-CmO_Arg-cgJ7A", "handle": "@pbdpodcast",
     "feed": "https://www.youtube.com/feeds/videos.xml?channel_id=UCGX7nGXpz-CmO_Arg-cgJ7A",
     "sections": ["video"], "kind": "video"},
]

ALLOWED_ARTICLE_HOSTS = (
    "foxnews.com", "foxbusiness.com",
)
ALLOWED_THUMB_HOSTS = (
    "foxnews.com", "foxbusiness.com", "fncstatic.com",
    "ytimg.com", "youtube.com",
)


def now_ct() -> datetime:
    return datetime.now(TZ)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def fetch_bytes(url: str, timeout: int = 25) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/atom+xml,application/rss+xml,application/xml,text/xml,text/html;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp else b""
        return e.code, body, e.headers.get("content-type", "") if e.headers else ""


def strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", " ", text)
    text = re.sub(r"(?i)</p>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmlmod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shorten(text: str, limit: int = 320) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "…" if cut else text[:limit]


def xml_text(el, path: str) -> str:
    if el is None:
        return ""
    node = el.find(path, NS)
    if node is None:
        node = el.find(path)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def first_attr(el, paths, attr: str) -> str:
    if el is None:
        return ""
    for path in paths:
        node = el.find(path, NS)
        if node is not None and node.get(attr):
            return node.get(attr)
    return ""


def host_ok(url: str, allowed: tuple[str, ...]) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return any(host == h or host.endswith("." + h) for h in allowed)
    except Exception:
        return False


def canon_url(url: str) -> str:
    from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
    try:
        p = urlparse(url.strip())
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(q), ""))
    except Exception:
        return url.strip()


def parse_rss_date(value: str) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        return to_iso(parsedate_to_datetime(value))
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            if fmt.endswith("Z"):
                return to_iso(datetime.strptime(value, fmt).replace(tzinfo=timezone.utc))
            return to_iso(datetime.strptime(value, fmt))
        except Exception:
            continue
    # +00:00 style already handled by fromisoformat in 3.11+
    try:
        return to_iso(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except Exception:
        return None


def parse_fox_feed(xml_bytes: bytes, feed: dict) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item"):
        title = htmlmod.unescape(xml_text(item, "title"))
        link = xml_text(item, "link") or xml_text(item, "guid")
        if not title or not link:
            continue
        if not host_ok(link, ALLOWED_ARTICLE_HOSTS):
            continue
        summary = shorten(strip_html(xml_text(item, "description")))
        published = parse_rss_date(xml_text(item, "pubDate"))
        thumb = first_attr(
            item,
            ["./media:content", "./media:thumbnail", "./media:group/media:content", "./media:group/media:thumbnail"],
            "url",
        )
        if thumb and not host_ok(thumb, ALLOWED_THUMB_HOSTS):
            thumb = None
        url = canon_url(link)
        items.append({
            "id": f"{feed['source_id']}:{url}",
            "title": title,
            "summary": summary,
            "url": link.strip(),
            "source": feed["source"],
            "source_id": feed["source_id"],
            "sections": list(feed["sections"]),
            "published": published,
            "published_precision": "minute" if published else "unknown",
            "thumbnail": thumb or None,
            "kind": "article",
            "feed_id": feed["id"],
        })
    return items


def parse_youtube_atom(xml_bytes: bytes, chan: dict) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for entry in list(root):
        if not entry.tag.endswith("entry"):
            continue
        title = htmlmod.unescape(xml_text(entry, "{http://www.w3.org/2005/Atom}title") or xml_text(entry, "title"))
        link = ""
        for ln in entry.findall("{http://www.w3.org/2005/Atom}link"):
            if ln.get("rel") in (None, "alternate") and ln.get("href"):
                link = ln.get("href")
                break
        video_id = xml_text(entry, "{http://www.youtube.com/xml/schemas/2015}videoId")
        if not video_id:
            m = re.search(r"(?:v=|/videos/|youtu\.be/)([A-Za-z0-9_-]{11})", link)
            video_id = m.group(1) if m else ""
        if not title or not video_id:
            continue
        url = f"https://www.youtube.com/watch?v={video_id}"
        published = parse_rss_date(
            xml_text(entry, "{http://www.w3.org/2005/Atom}published") or xml_text(entry, "published")
        )
        desc = strip_html(
            xml_text(entry, "{http://search.yahoo.com/mrss/}group/{http://search.yahoo.com/mrss/}description")
            or xml_text(entry, "media:group/media:description")
        )
        thumb = first_attr(entry, ["./media:group/media:thumbnail", "./media:thumbnail"], "url")
        if not thumb:
            thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        items.append({
            "id": f"yt:{video_id}",
            "title": title,
            "summary": shorten(desc),
            "url": url,
            "source": chan["source"],
            "source_id": chan["source_id"],
            "sections": ["video"],
            "published": published,
            "published_precision": "minute" if published else "unknown",
            "thumbnail": thumb,
            "kind": "video",
            "feed_id": chan["id"],
            "video_id": video_id,
        })
    return items


def extract_json_assignment(html: str, name: str):
    m = re.search(rf"\b{name}\s*=\s*", html)
    if not m:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[m.end():])
        return obj
    except Exception:
        return None


def walk_lockups(obj):
    found = []
    def rec(o):
        if isinstance(o, dict):
            if "lockupViewModel" in o:
                vm = o["lockupViewModel"]
                if vm.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO" or vm.get("contentId"):
                    found.append(vm)
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
    rec(obj)
    return found


def parse_channel_page(html: str, chan: dict) -> list[dict]:
    data = extract_json_assignment(html, "ytInitialData")
    if not data:
        return []
    items = []
    seen = set()
    for vm in walk_lockups(data):
        vid = vm.get("contentId") or ""
        if not isinstance(vid, str) or len(vid) != 11 or vid in seen:
            continue
        meta = (vm.get("metadata") or {}).get("lockupMetadataViewModel") or {}
        title = ((meta.get("title") or {}).get("content")) or ""
        if not title:
            continue
        relative = None
        rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows")) or []
        for row in rows:
            for part in row.get("metadataParts") or []:
                label = (part.get("accessibilityLabel") or "")
                content = ((part.get("text") or {}).get("content")) or ""
                if "ago" in label.lower() or "ago" in content.lower() or "streamed" in label.lower():
                    relative = label or content
        thumb = None
        image = (((vm.get("contentImage") or {}).get("thumbnailViewModel") or {}).get("image") or {})
        sources = image.get("sources") or []
        if sources:
            # prefer the widest listed official thumbnail
            sources = sorted(sources, key=lambda s: s.get("width") or 0, reverse=True)
            thumb = sources[0].get("url")
        if not thumb:
            thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        seen.add(vid)
        items.append({
            "id": f"yt:{vid}",
            "title": htmlmod.unescape(title),
            "summary": "",
            "url": f"https://www.youtube.com/watch?v={vid}",
            "source": chan["source"],
            "source_id": chan["source_id"],
            "sections": ["video"],
            "published": None,
            "published_precision": "unknown",
            "published_text": relative,
            "thumbnail": thumb,
            "kind": "video",
            "feed_id": chan["id"],
            "video_id": vid,
        })
    return items


def fill_watch_dates(items: list[dict], existing_by_id: dict) -> None:
    """When the Atom feed is unavailable, read the official watch page date text."""
    need = []
    for it in items:
        prev = existing_by_id.get(it["id"])
        if prev and prev.get("published") and prev.get("published_precision") == "minute":
            it["published"] = prev["published"]
            it["published_precision"] = "minute"
            if prev.get("summary") and not it.get("summary"):
                it["summary"] = prev["summary"]
            continue
        if it.get("published"):
            continue
        need.append(it)
    # Cap new lookups so a refresh stays bounded.
    for it in need[:15]:
        try:
            code, body, _ = fetch_bytes(it["url"], timeout=20)
            if code != 200:
                continue
            html = body.decode("utf-8", "replace")
            data = extract_json_assignment(html, "ytInitialData")
            if not data:
                continue
            date_text = None
            relative = None
            def find_dates(o):
                nonlocal date_text, relative
                if date_text and relative:
                    return
                if isinstance(o, dict):
                    if "dateText" in o and isinstance(o["dateText"], dict):
                        date_text = o["dateText"].get("simpleText") or date_text
                    if "relativeDateText" in o and isinstance(o["relativeDateText"], dict):
                        relative = (
                            (o["relativeDateText"].get("accessibility") or {})
                            .get("accessibilityData", {})
                            .get("label")
                            or o["relativeDateText"].get("simpleText")
                            or relative
                        )
                    for v in o.values():
                        find_dates(v)
                elif isinstance(o, list):
                    for v in o:
                        find_dates(v)
            find_dates(data)
            if date_text:
                it["published_date_text"] = date_text
                parsed = parse_date_text(date_text)
                if parsed:
                    it["published"] = parsed
                    it["published_precision"] = "day"
            if relative:
                it["published_text"] = relative
        except Exception:
            continue


MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_date_text(text: str) -> str | None:
    """Parse a calendar date such as 'Nov 13, 2026' as midnight Central, precision=day."""
    if not text:
        return None
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text.strip())
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        dt = datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=TZ)
        return to_iso(dt)
    except Exception:
        return None



REL_AGO = re.compile(
    r"(?:streamed\s+)?(\d+)\s*"
    r"(minutes?|mins?|hours?|hrs?|h|days?|d|weeks?|w|months?|mo|years?|yrs?|y)\b",
    re.I,
)


def relative_published(text: str, now: datetime) -> datetime | None:
    """Turn a source phrase such as '7 hours ago' into a timestamp for sorting only."""
    if not text:
        return None
    raw = text.strip().lower().replace("\xa0", " ")
    if raw in {"just now", "now"}:
        return now
    m = REL_AGO.search(raw)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    from datetime import timedelta
    if unit.startswith("min"):
        return now - timedelta(minutes=n)
    if unit.startswith("hour") or unit in {"hr", "hrs", "h"}:
        return now - timedelta(hours=n)
    if unit.startswith("day") or unit == "d":
        return now - timedelta(days=n)
    if unit.startswith("week") or unit == "w":
        return now - timedelta(weeks=n)
    if unit.startswith("month") or unit == "mo":
        return now - timedelta(days=30 * n)
    if unit.startswith("year") or unit in {"yr", "yrs", "y"}:
        return now - timedelta(days=365 * n)
    return None


def apply_relative_time(item: dict, now: datetime) -> None:
    if item.get("published") and item.get("published_precision") in {"minute", "day"}:
        return
    dt = relative_published(item.get("published_text") or "", now)
    if dt:
        item["published"] = to_iso(dt)
        item["published_precision"] = "relative"


def merge_items(existing: list, incoming: list) -> list:
    by_id = {}
    for it in existing:
        if isinstance(it, dict) and it.get("id"):
            by_id[it["id"]] = it
    for it in incoming:
        prev = by_id.get(it["id"])
        if not prev:
            by_id[it["id"]] = it
            continue
        # Union sections; keep the newest known fields without inventing text.
        sections = list(dict.fromkeys((prev.get("sections") or []) + (it.get("sections") or [])))
        merged = dict(prev)
        merged.update({k: v for k, v in it.items() if v not in (None, "", [], {})})
        # Prefer a more precise published time if we just got one.
        prev_prec = prev.get("published_precision") or "unknown"
        new_prec = it.get("published_precision") or "unknown"
        rank = {"unknown": 0, "day": 1, "minute": 2}
        if rank.get(prev_prec, 0) > rank.get(new_prec, 0) and prev.get("published"):
            merged["published"] = prev["published"]
            merged["published_precision"] = prev_prec
        if prev.get("summary") and not it.get("summary"):
            merged["summary"] = prev["summary"]
        merged["sections"] = sections
        by_id[it["id"]] = merged

    def sort_key(it):
        pub = it.get("published") or ""
        return pub

    items = list(by_id.values())
    items.sort(key=sort_key, reverse=True)
    # Keep the newest stories from every source so YouTube episodes are not
    # dropped when many Fox articles share the same 300-item window.
    per_source = 25
    guaranteed_ids = set()
    counts = {}
    for it in items:
        sid = it.get("source_id") or "other"
        n = counts.get(sid, 0)
        if n < per_source:
            guaranteed_ids.add(it["id"])
            counts[sid] = n + 1
    guaranteed = [it for it in items if it["id"] in guaranteed_ids]
    rest = [it for it in items if it["id"] not in guaranteed_ids]
    room = max(0, MAX_ITEMS - len(guaranteed))
    chosen = guaranteed + rest[:room]
    chosen.sort(key=sort_key, reverse=True)
    return chosen


def load_existing() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main() -> int:
    existing = load_existing()
    existing_items = existing.get("items") or []
    existing_by_id = {it["id"]: it for it in existing_items if it.get("id")}
    incoming = []
    status = []

    for feed in FOX_FEEDS:
        entry = {"id": feed["id"], "name": feed["name"], "url": feed["url"], "ok": False,
                 "count": 0, "http": None, "checked": to_iso(now_ct()), "error": None}
        try:
            code, body, ctype = fetch_bytes(feed["url"])
            entry["http"] = code
            if code == 200 and body and b"<item" in body:
                items = parse_fox_feed(body, feed)
                entry["count"] = len(items)
                entry["ok"] = True
                incoming.extend(items)
            else:
                entry["error"] = f"HTTP {code}; no RSS items returned"
        except Exception as e:
            entry["error"] = type(e).__name__ + ": " + str(e)
        status.append(entry)

    for chan in YOUTUBE:
        entry = {"id": chan["id"], "name": chan["name"], "url": chan["feed"],
                 "channel_id": chan["channel_id"], "ok": False, "count": 0,
                 "http": None, "checked": to_iso(now_ct()), "error": None, "method": None}
        used = []
        try:
            code, body, ctype = fetch_bytes(chan["feed"])
            entry["http"] = code
            if code == 200 and body and (b"<entry" in body or b"<item" in body):
                used = parse_youtube_atom(body, chan)
                entry["method"] = "youtube-atom"
            else:
                # Official Atom feed is sometimes blocked; fall back to the official channel videos page.
                page_url = f"https://www.youtube.com/{chan['handle']}/videos"
                pcode, pbody, _ = fetch_bytes(page_url, timeout=30)
                entry["http"] = f"{code},{pcode}"
                if pcode == 200:
                    used = parse_channel_page(pbody.decode("utf-8", "replace"), chan)
                    fill_watch_dates(used, existing_by_id)
                    entry["method"] = "youtube-channel-page"
                    if not used:
                        entry["error"] = f"Atom HTTP {code}; channel page had no videos"
                else:
                    entry["error"] = f"Atom HTTP {code}; channel page HTTP {pcode}"
            if used:
                now = now_ct()
                for it in used:
                    apply_relative_time(it, now)
                entry["count"] = len(used)
                entry["ok"] = True
                incoming.extend(used)
        except Exception as e:
            entry["error"] = type(e).__name__ + ": " + str(e)
        status.append(entry)

    items = merge_items(existing_items, incoming)
    payload = {
        "updated": to_iso(now_ct()),
        "timezone": "America/Chicago",
        "item_count": len(items),
        "items": items,
        "status": status,
        "sources": [
            {"id": "fox-news", "name": "Fox News", "site": "https://www.foxnews.com/"},
            {"id": "fox-business", "name": "Fox Business", "site": "https://www.foxbusiness.com/"},
            {"id": "tousi-tv", "name": "Tousi TV", "site": "https://www.youtube.com/@tousitv"},
            {"id": "pbd-podcast", "name": "PBD Podcast", "site": "https://www.youtube.com/@pbdpodcast"},
        ],
        "notes": [
            "Headlines, summaries and times come from the source feeds or the official source pages. This file does not add commentary.",
            "Fox News does not publish a Texas or DFW RSS feed at moxie.foxnews.com, so that section is not included.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for s in status if s["ok"])
    print(f"Wrote {OUT} with {len(items)} items. Sources ok: {ok}/{len(status)}")
    for s in status:
        flag = "OK" if s["ok"] else "FAIL"
        extra = s.get("method") or ""
        err = s.get("error") or ""
        print(f"  [{flag}] {s['name']}: {s['count']}  http={s.get('http')} {extra} {err}".rstrip())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
