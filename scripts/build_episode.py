#!/usr/bin/env python3
"""Turn episodes/<id>/script.md into an MP3 with Google Cloud Text-to-Speech,
then update the podcast feed (docs/feed.xml) and the monthly usage counter.

Script format (see README.md): segments start with a heading like
    ## [vi] Tin tuc trong nuoc
    ## [en] World news
    ## [fr] L'actualite de la France
Everything before the first segment heading is ignored.

Only the Python standard library is used. The API key is read from the
GOOGLE_TTS_API_KEY environment variable (a GitHub Actions secret).
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
MAX_CHUNK_BYTES = 4500          # API limit is 5000 bytes per request
SEGMENT_RE = re.compile(r"^##\s*\[(vi|en|fr)\]\s*(.*)$", re.MULTILINE)


# ----------------------------------------------------------------- parsing
def parse_segments(text):
    matches = list(SEGMENT_RE.finditer(text))
    segments = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.append({"lang": m.group(1), "title": m.group(2).strip(),
                         "body": text[m.end():end]})
    return segments


def clean(text):
    """Strip Markdown so the voice does not read symbols aloud."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)      # links -> label
    text = re.sub(r"https?://\S+", "", text)                   # bare URLs
    text = re.sub(r"[`*_~>#|]", "", text)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long(sentence, limit):
    words, out, cur = sentence.split(" "), [], ""
    for w in words:
        if len((cur + " " + w).encode("utf-8")) > limit and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text, limit=MAX_CHUNK_BYTES):
    pieces = []
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        para = para.replace("\n", " ")
        if len(para.encode("utf-8")) <= limit:
            pieces.append(para)
            continue
        for sent in re.split(r"(?<=[.!?…])\s+", para):
            if len(sent.encode("utf-8")) <= limit:
                pieces.append(sent)
            else:
                pieces.extend(split_long(sent, limit))
    # merge small neighbours into chunks up to the limit
    chunks, cur = [], ""
    for p in pieces:
        cand = (cur + "\n\n" + p) if cur else p
        if len(cand.encode("utf-8")) <= limit:
            cur = cand
        else:
            chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------- synthesis
def synthesize(text, voice, api_key):
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": voice["languageCode"], "name": voice["name"]},
        "audioConfig": {"audioEncoding": "MP3",
                        "speakingRate": voice.get("speakingRate", 1.0),
                        "sampleRateHertz": 24000},
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": api_key})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return base64.b64decode(json.load(r)["audioContent"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            sys.exit(f"TTS API error {e.code}: {detail}")
        except urllib.error.URLError as e:
            if attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            sys.exit(f"TTS network error: {e}")


# ------------------------------------------------------------------- usage
def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def audio_duration(path, fallback_chars):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)], text=True)
        return int(float(out.strip()))
    except Exception:
        return int(fallback_chars / 14)  # ~14 spoken characters per second


# -------------------------------------------------------------------- feed
def build_feed(cfg, episodes):
    site = cfg["site_url"].rstrip("/")
    items = []
    for ep in episodes:
        pub = dt.datetime.fromisoformat(ep["published"])
        items.append(f"""    <item>
      <title>{escape(ep['title'])}</title>
      <description>{escape(ep['description'])}</description>
      <pubDate>{format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">daily-podcast-{escape(ep['id'])}</guid>
      <enclosure url="{escape(ep['url'])}" length="{ep['length']}" type="audio/mpeg"/>
      <itunes:duration>{ep['duration']}</itunes:duration>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(cfg['podcast_title'])}</title>
    <link>{escape(site)}/</link>
    <description>{escape(cfg['podcast_description'])}</description>
    <language>en</language>
    <itunes:author>{escape(cfg['podcast_author'])}</itunes:author>
    <itunes:explicit>false</itunes:explicit>
{chr(10).join(items)}
  </channel>
</rss>
"""


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True, help="folder name under episodes/, e.g. 2026-10-08 or sample")
    ap.add_argument("--dry-run", action="store_true", help="parse and count only; no API calls")
    args = ap.parse_args()

    cfg = load_json(ROOT / "config.json", None)
    if cfg is None:
        sys.exit("config.json missing")
    ep_dir = ROOT / "episodes" / args.episode
    script_path = ep_dir / "script.md"
    if not script_path.exists():
        sys.exit(f"{script_path} not found")

    segments = parse_segments(script_path.read_text(encoding="utf-8"))
    if not segments:
        sys.exit("No '## [vi|en|fr] ...' segment headings found in script.md")

    plan, total_chars = [], 0
    for seg in segments:
        chunks = chunk_text(clean(seg["body"]))
        chars = sum(len(c) for c in chunks)
        plan.append((seg, chunks, chars))
        total_chars += chars
    print(f"Episode {args.episode}: {len(segments)} segments, {total_chars} characters")
    for seg, chunks, chars in plan:
        print(f"  [{seg['lang']}] {seg['title'][:40]:40} {chars:6} chars in {len(chunks)} chunks")

    # ---- cost guards (keep inside the Google free tier)
    is_sample = args.episode == "sample"
    month = dt.date.today().strftime("%Y-%m")
    usage_path = ROOT / "state" / "usage.json"
    usage = load_json(usage_path, {})
    used = usage.get(month, 0)
    if total_chars > cfg["max_chars_per_episode"]:
        sys.exit(f"Refusing: {total_chars} chars exceeds per-episode limit {cfg['max_chars_per_episode']}")
    if used + total_chars > cfg["max_chars_per_month"]:
        sys.exit(f"Refusing: month total would be {used + total_chars}, limit {cfg['max_chars_per_month']}")
    if args.dry_run:
        print(f"Dry run OK. Month so far: {used} chars.")
        return

    api_key = os.environ.get("GOOGLE_TTS_API_KEY", "").strip()
    if not api_key:
        sys.exit("GOOGLE_TTS_API_KEY is not set")

    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    mp3_path = out_dir / f"podcast-{args.episode}.mp3"
    audio = bytearray()
    for seg, chunks, _ in plan:
        voice = cfg["voices"][seg["lang"]]
        for c in chunks:
            audio += synthesize(c, voice, api_key)
    mp3_path.write_bytes(bytes(audio))
    size = mp3_path.stat().st_size
    duration = audio_duration(mp3_path, total_chars)
    print(f"Wrote {mp3_path.name}: {size/1e6:.1f} MB, ~{duration//60} min")

    if is_sample:
        return  # samples are not added to the feed or the usage counter

    # ---- usage counter
    usage[month] = used + total_chars
    usage_path.parent.mkdir(exist_ok=True)
    usage_path.write_text(json.dumps(usage, indent=2) + "\n", encoding="utf-8")

    # ---- feed
    date = dt.date.fromisoformat(args.episode)
    published = dt.datetime(date.year, date.month, date.day, 8, 30,
                            tzinfo=dt.timezone(dt.timedelta(hours=7)))
    summary_path = ep_dir / "summary.md"
    desc = clean(summary_path.read_text(encoding="utf-8"))[:1500] if summary_path.exists() \
        else "Daily briefing: Vietnam, world and France."
    repo = cfg["github_repo"]
    entry = {
        "id": args.episode,
        "title": f"{cfg['episode_title_prefix']} - {date.strftime('%a %d %b %Y')}",
        "description": desc,
        "published": published.isoformat(),
        "url": f"https://github.com/{repo}/releases/download/ep-{args.episode}/podcast-{args.episode}.mp3",
        "length": size,
        "duration": duration,
    }
    ep_json = ROOT / "docs" / "episodes.json"
    episodes = [e for e in load_json(ep_json, []) if e["id"] != args.episode]
    episodes.append(entry)
    episodes.sort(key=lambda e: e["published"], reverse=True)
    episodes = episodes[: cfg["keep_episodes"]]
    ep_json.parent.mkdir(exist_ok=True)
    ep_json.write_text(json.dumps(episodes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "docs" / "feed.xml").write_text(build_feed(cfg, episodes), encoding="utf-8")
    print("Feed updated:", len(episodes), "episodes")


if __name__ == "__main__":
    main()
