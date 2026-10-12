#!/usr/bin/env python3
"""Synthesize the same news excerpt with several Google Cloud TTS voices so the
voices can be compared by ear. Writes one MP3 per voice plus RESULTS.md into
out/voice-test/.

The excerpt is taken from the latest real episode script, so numbers, names and
sentence length are representative. Voices are discovered through the API
(voices:list), not guessed, and the voice currently set in config.json is always
included as the baseline.

Only the Python standard library is used. The API key is read from the
GOOGLE_TTS_API_KEY environment variable (a GitHub Actions secret).
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_episode import clean, parse_segments  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API = "https://texttospeech.googleapis.com/v1"
EXCERPT_CHARS = 450
HARD_CAP_CHARS = 15000  # whole run, keeps a test far inside the free tier


# --------------------------------------------------------------------- API
def api_get(path, key):
    req = urllib.request.Request(f"{API}/{path}", headers={"X-Goog-Api-Key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def synth(text, lang_code, voice_name, key, plain_audio_config):
    audio_config = {"audioEncoding": "MP3"}
    if not plain_audio_config:
        audio_config.update({"speakingRate": 1.0, "sampleRateHertz": 24000})
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": audio_config,
    }).encode("utf-8")
    req = urllib.request.Request(f"{API}/text:synthesize", data=body, method="POST", headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        return base64.b64decode(json.load(r)["audioContent"])


# ------------------------------------------------------------------ sample
def latest_script():
    folders = sorted((p for p in (ROOT / "episodes").iterdir()
                      if p.is_dir() and p.name != "sample" and (p / "script.md").exists()),
                     reverse=True)
    path = (folders[0] if folders else ROOT / "episodes" / "sample") / "script.md"
    return path


def excerpt(lang_prefix, limit=EXCERPT_CHARS):
    """About `limit` characters of real news text in the given language (vi/en/fr)."""
    path = latest_script()
    segs = [s for s in parse_segments(path.read_text(encoding="utf-8")) if s["lang"] == lang_prefix]
    if not segs:
        sys.exit(f"No [{lang_prefix}] segment in {path}")
    paras = [p.strip() for p in clean(segs[0]["body"]).split("\n\n") if p.strip()]
    paras = paras[1:] if len(paras) > 1 else paras  # skip the greeting paragraph
    out = ""
    for para in paras:
        for sent in re.split(r"(?<=[.!?…])\s+", para.replace("\n", " ")):
            if out and len(out) + len(sent) > limit:
                return out.strip()
            out += sent + " "
        if len(out) >= limit * 0.8:
            break
    return out.strip()


# ------------------------------------------------------------- voice choice
def pick_voices(voices, families, per_family, baseline):
    """Per family, up to `per_family` voices, alternating female/male so both
    genders are heard. The baseline voice from config.json always comes first."""
    chosen, seen = [], set()

    def add(v, family):
        if v["name"] not in seen:
            seen.add(v["name"])
            chosen.append({"name": v["name"], "gender": v.get("ssmlGender", "?").lower(),
                           "family": family})

    base = next((v for v in voices if v["name"] == baseline), None)
    if base:
        add(base, "current")
    for fam in families:
        matches = sorted((v for v in voices if fam.lower() in v["name"].lower()),
                         key=lambda v: v["name"])
        fem = [v for v in matches if v.get("ssmlGender") == "FEMALE"]
        mal = [v for v in matches if v.get("ssmlGender") != "FEMALE"]
        mixed = [x for pair in zip(fem, mal) for x in pair] + fem[len(mal):] + mal[len(fem):]
        for v in mixed[:per_family]:
            add(v, fam)
    return chosen


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", default="vi-VN,en-US", help="comma separated language codes")
    ap.add_argument("--families", default="Chirp3-HD,Studio,Neural2",
                    help="comma separated voice-name substrings to try")
    ap.add_argument("--per-family", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "out" / "voice-test"))
    args = ap.parse_args()

    key = os.environ.get("GOOGLE_TTS_API_KEY", "").strip()
    if not key:
        sys.exit("GOOGLE_TTS_API_KEY is not set")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    families = [f.strip() for f in args.families.split(",") if f.strip()]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, total_chars, ok_count = [], 0, 0
    for lang_code in [l.strip() for l in args.languages.split(",") if l.strip()]:
        prefix = lang_code.split("-")[0]
        if prefix not in cfg["voices"]:
            print(f"Skipping {lang_code}: no [{prefix}] segment type in this project")
            continue
        text = excerpt(prefix)
        data = api_get("voices?" + urllib.parse.urlencode({"languageCode": lang_code}), key)
        voices = [v for v in data.get("voices", []) if lang_code in v.get("languageCodes", [])]
        by_family = {}
        for v in voices:
            for fam in ("Chirp3-HD", "Studio", "Neural2", "WaveNet", "Polyglot", "Standard"):
                if fam.lower() in v["name"].lower():
                    by_family.setdefault(fam, []).append(v["name"].replace(lang_code + "-", ""))
        print(f"\n== {lang_code}: {len(voices)} voices available")
        for fam, names in sorted(by_family.items()):
            print(f"   {fam}: {len(names)} -> {', '.join(sorted(names))}")
        rows.append(f"\n### {lang_code}\n\nSample ({len(text)} chars): {text[:140]}...\n")
        rows.append("| Voice | Gender | Family | File |\n|---|---|---|---|")
        baseline = cfg["voices"][prefix]["name"] if cfg["voices"][prefix]["languageCode"] == lang_code else ""
        picks = pick_voices(voices, families, args.per_family, baseline)
        if not any(p["family"] == "Chirp3-HD" for p in picks):
            print(f"   NOTE: no Chirp3-HD voice is listed for {lang_code}")
            rows.append(f"| _no Chirp3-HD voice listed for {lang_code}_ | | | |")
        for p in picks:
            if total_chars + len(text) > HARD_CAP_CHARS:
                print("Character cap reached, stopping.")
                break
            short = p["name"].replace(lang_code + "-", "")
            fname = f"{lang_code}_{short}.mp3"
            try:
                audio = synth(text, lang_code, p["name"], key, plain_audio_config=("Chirp" in p["name"]))
                (out / fname).write_bytes(audio)
                total_chars += len(text)
                ok_count += 1
                label = "current" if p["family"] == "current" else p["family"]
                rows.append(f"| {short} | {p['gender']} | {label} | {fname} |")
                print(f"   ok   {p['name']} ({p['gender']}) -> {fname}, {len(audio)/1000:.0f} KB")
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:200].replace("\n", " ")
                rows.append(f"| {short} | {p['gender']} | {p['family']} | FAILED {e.code} |")
                print(f"   FAIL {p['name']}: HTTP {e.code} {detail}")
            except Exception as e:  # keep going, one bad voice must not stop the test
                rows.append(f"| {short} | {p['gender']} | {p['family']} | FAILED |")
                print(f"   FAIL {p['name']}: {e}")

    notes = ["# Voice test",
             "",
             "Same news excerpt read by each voice. Download the MP3s below and listen on your phone.",
             "The row marked `current` is the voice used in episodes today.",
             *rows,
             "",
             f"Characters synthesized: {total_chars}"]
    (out / "RESULTS.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n".join(notes) + "\n")
    print(f"\n{ok_count} clips, {total_chars} characters")
    if ok_count == 0:
        sys.exit("No clip was produced")


if __name__ == "__main__":
    main()
