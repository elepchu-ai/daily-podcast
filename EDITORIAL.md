# Editorial brief for the daily script

This is the brief the scheduled task follows each day. Paste it (or point the
task at this file) so the prompt and the repo guard stay in sync.

## 0. Before writing: read what was already covered

1. Read `state/covered.json` (stories from the last 10 episodes) and the
   previous episode's `summary.md`.
2. For every candidate story ask: *what is new since it was last covered?*
3. Include it only if there is a **material new development** (new decision,
   number, event, or outcome). Then say only what changed, with at most one
   sentence of background. If nothing new, drop it and find another story.
4. Never report an event older than 48 hours as news. Results and awards
   (sport, Nobel, prizes) are allowed once, on the first morning after they
   happen, and never again.
5. Slow-moving stories (Iran war and Hormuz, Budget 2027, AI company IPOs,
   lycéen movement) get at most **one sentence each**, in a short "ongoing"
   strip, and only on days something changed.

## 1. Structure and length

- Target **2,800 to 3,200 words** in total, about 20 minutes of audio
  (`config.json` -> `novelty`). Per-section words: `[vi]` 900 to 1,100,
  `[en]` 1,100 to 1,400, `[fr]` 700 to 900. A section under its minimum
  needs more fresh stories, not padding or background.
- **No hedging sentences** such as "I do not have…", "I could not confirm…",
  "chưa thể xác nhận…" or "je n'ai pas pu…". If a fact is missing, drop it
  and research a replacement. For a TCB quote without a verified close, give
  the last verified close with its date instead.
- Greeting in one sentence. **No recap or "Tóm lại / To recap / En résumé"
  paragraphs.** End each section with a single short transition line.
- Do not start two days in a row with the same phrasing; vary the story order.

## 2. Vietnam section (`[vi]`)

1. **Numbers strip, about 30 seconds, always present:** VN-Index close and
   change, SJC gold buy/sell, USD/VND. Frame as change since yesterday, with
   the trend in one clause (for example "sixth falling session").
2. **TCB (Techcombank), always present:**
   - Closing price on HOSE in VND, daily change in VND and %, volume, and
     foreign net buying or selling if reported. Use a real quote from a cited
     source. If no verified price is available, say so plainly. Never guess.
   - Related news, only if new: earnings or guidance, credit growth, bond or
     share issuance, analyst rating or target-price changes, Techcom Securities
     (TCBS), Masan or Vinhomes links, SBV rate or regulation news affecting
     banks. If there is no new TCB news, give the price and one line on the
     banking-sector driver.
3. GDP, CPI, trade and FDI figures only on the day they are released or
   revised. Otherwise skip them.
4. The rest: 3 to 4 genuinely new domestic stories (policy, laws, incidents,
   weather, health), each with a date and a source.

## 3. English section (`[en]`)

1. **Telecom and Ericsson, always present, 2 to 3 stories:**
   - Ericsson: earnings, restructuring or job cuts, major contracts (for
     example operators in India, the US and the Middle East), 5G and 6G
     standards, Ericsson Mobility Report, patent or licensing disputes,
     share price move on Nasdaq Stockholm.
   - Wider telecom: Nokia, Huawei, Samsung Networks, Qualcomm, operators
     (AT&T, Verizon, Viettel, VNPT), spectrum auctions, open RAN, satellite
     direct-to-device (Starlink, AST), submarine cable cuts, AI-RAN, and
     regulation (FCC, EU Digital Networks Act).
   - If Ericsson has no new item that day, cover another telecom story. Never
     rerun an old Ericsson item.
2. Then 5 to 7 other new world stories: technology and AI, geopolitics,
   economy, **at least 2 sport results** from the last 24 to 48 hours,
   and **at least 1 science or health item**. Apply the section 0
   rules strictly.

## 4. France section (`[fr]`)

3 to 4 new stories: politics, economy, society, one sport or culture item.
Budget 2027, lycéens and Goncourt only with a new development.

## 5. `summary.md`

Short bullets of **what is new today only**, one list per language, then
`## Sources` with links. Do not copy any bullet from a previous summary. Keep
the TCB price line and the Ericsson/telecom line as their own bullets.

## 6. Numbers for the voice

Write numbers as words (as in existing scripts) so the text-to-speech reads
them correctly, and keep plain paragraphs: no lists, URLs or tables.

## 7. After writing

1. Run `python scripts/check_novelty.py --episode YYYY-MM-DD`. Fix every
   warning (rewrite the repeated story, or drop it) before committing.
2. Run `python scripts/check_novelty.py --update-index` and commit
   `state/covered.json` together with the episode.

## 8. Requested follow-ups (check every day, remove when done)

Stories the listener asked to follow. Cover each as a **new development
only** (the outcome, not a repeat of the preview), then delete the line in the
same commit as the episode.

_(No open follow-ups.)_
