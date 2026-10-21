#!/usr/bin/env python3
"""Novelty and format guard for a daily episode (warn-only unless --strict).

Compares episodes/<id>/summary.md bullets with the previous --lookback
episodes and flags near-duplicate stories. Also checks length, recap
sentences, verbatim repeated sentences, and the required TCB / telecom
coverage. With --update-index it rewrites state/covered.json, the compact
story index the editorial brief tells the generator to read before writing.

Only the Python standard library is used.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EP_DIR = ROOT / "episodes"
INDEX = ROOT / "state" / "covered.json"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RECAP_RE = re.compile(r"^\s*(tóm lại|tom lai|to recap|in summary|en résumé|en resume)\b", re.I)
EXEMPT_RE = re.compile(r"vn-index|\bsjc\b|\btcb\b|techcombank", re.I)  # daily market lines
STOP = set("""that this with from have were been will which their about after
into over than also more most other some such only still while where when
nhung cung trong cuoc cua cho nhu duoc khong mot cac nhieu nguoi nam thang
dans pour avec plus sont mais cette comme entre apres selon leur nous vous
tout tous elle elles ainsi donc dont chez sans sous vers les des une aux""".split())


def norm(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokens(text):
    t = norm(text)
    nums = set(re.findall(r"\d+(?:[.,]\d+)?", t))
    words = {w for w in re.findall(r"[a-z]{4,}", t) if w not in STOP}
    return nums, words


def episodes():
    return sorted(p.name for p in EP_DIR.iterdir()
                  if p.is_dir() and DATE_RE.match(p.name) and (p / "script.md").exists())


def bullets(summary_path):
    out, lang, in_sources = [], "", False
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            head = norm(line[3:])
            in_sources = head.startswith("sources")
            lang = "vi" if "tin" in head else "en" if "world" in head else "fr"
        elif line.startswith("- ") and not in_sources:
            out.append((lang, line[2:].strip()))
    return out


def sentences(text):
    text = re.sub(r"^#.*$", "", text, flags=re.M)
    for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        if len(s.split()) >= 12:
            yield norm(re.sub(r"\W+", " ", s)).strip()


def segment(text, lang):
    m = re.search(r"^##\s*\[%s\].*$" % lang, text, re.M)
    if not m:
        return ""
    n = re.search(r"^##\s*\[", text[m.end():], re.M)
    return text[m.end(): m.end() + n.start()] if n else text[m.end():]


def similar(a, b, cfg):
    (na, wa), (nb, wb) = a, b
    if not wa or not wb:
        return 0.0
    jac = len(wa & wb) / len(wa | wb)
    if len(na & nb) >= cfg["shared_numbers"] and len(wa & wb) >= cfg["shared_words"]:
        jac = max(jac, cfg["jaccard"])
    return jac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", help="episode id (default: latest)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any warning")
    ap.add_argument("--update-index", action="store_true", help="rewrite state/covered.json")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("novelty", {})
    cfg = {"lookback": 5, "jaccard": 0.5, "shared_numbers": 2, "shared_words": 3,
           "min_words": 2400, "max_words": 3300, "index_days": 10, **cfg}

    eps = episodes()
    if args.update_index:
        keep = eps[-cfg["index_days"]:]
        data = {"note": "Stories already covered. Read before writing; skip unless materially new.",
                "episodes": {e: [{"lang": l, "story": t} for l, t in bullets(EP_DIR / e / "summary.md")]
                             for e in keep if (EP_DIR / e / "summary.md").exists()}}
        INDEX.parent.mkdir(exist_ok=True)
        INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Wrote {INDEX.relative_to(ROOT)} ({len(data['episodes'])} episodes)")
        return 0

    ep = args.episode or (eps[-1] if eps else None)
    if ep is None or not (EP_DIR / ep / "script.md").exists():
        print(f"No such episode: {ep}")
        return 0
    prev = [e for e in eps if e < ep][-cfg["lookback"]:]
    warns = []

    script = (EP_DIR / ep / "script.md").read_text(encoding="utf-8")
    words = len(script.split())
    if not cfg["min_words"] <= words <= cfg["max_words"]:
        warns.append(f"length: {words} words (target {cfg['min_words']}-{cfg['max_words']})")
    for line in script.splitlines():
        if RECAP_RE.match(line):
            warns.append(f"recap paragraph: \"{line.strip()[:60]}...\"")
    if "tcb" not in norm(segment(script, "vi")):
        warns.append("vi section has no TCB item (price + news required)")
    en = norm(segment(script, "en"))
    if "ericsson" not in en and "telecom" not in en:
        warns.append("en section has no Ericsson / telecom item")

    seen = {s: e for e in prev for s in sentences((EP_DIR / e / "script.md").read_text(encoding="utf-8"))}
    for s in sentences(script):
        if s in seen:
            warns.append(f"sentence repeated from {seen[s]}: \"{s[:70]}...\"")

    sp = EP_DIR / ep / "summary.md"
    if sp.exists():
        old = [(e, l, t, tokens(t)) for e in prev if (EP_DIR / e / "summary.md").exists()
               for l, t in bullets(EP_DIR / e / "summary.md")]
        for lang, text in bullets(sp):
            if EXEMPT_RE.search(text):
                continue
            tk = tokens(text)
            best = max(((similar(tk, o[3], cfg), o) for o in old if o[1] == lang),
                       key=lambda x: x[0], default=(0, None))
            if best[0] >= cfg["jaccard"]:
                warns.append(f"repeat of {best[1][0]} ({best[0]:.0%}): \"{text[:70]}...\"")
    else:
        warns.append("no summary.md")

    print(f"Novelty check {ep} vs {', '.join(prev) or 'nothing'}: {words} words")
    for w in warns:
        print(f"  WARN {w}")
    if not warns:
        print("  OK")
    return 1 if (warns and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
