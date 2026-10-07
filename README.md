# Daily Podcast

Turns a daily text script into a streaming podcast episode.

```
Claude scheduled task -> episodes/YYYY-MM-DD/script.md (+ summary.md)
   -> push to main -> GitHub Action
   -> Google Cloud Text-to-Speech (one voice per language)
   -> MP3 attached to a GitHub Release (last 14 kept)
   -> docs/feed.xml (podcast feed served by GitHub Pages)
   -> your podcast app streams it
```

## One-time setup

1. **Secret**: Settings -> Secrets and variables -> Actions -> secret `GOOGLE_TTS_API_KEY`
   (a Google Cloud API key restricted to *Cloud Text-to-Speech API*).
2. **Public repo**: GitHub Pages and public release downloads need a public repo on
   the Free plan. Everything here is public news, so this is fine. Keep API keys
   only in Actions secrets, never in files.
3. **Pages**: Settings -> Pages -> Source: *Deploy from a branch* -> Branch `main`,
   folder `/docs`.
4. **Test the voices**: Actions tab -> *Build podcast episode* -> *Run workflow* with
   `episode = sample`. Open the new release `ep-sample` and play the MP3.
5. **Subscribe** in your podcast app (Add show by URL):
   `https://elepchu-ai.github.io/daily-podcast/feed.xml`

## Script format

```
# Title (ignored)

## [vi] Tin tuc trong nuoc
...Vietnamese text, plain paragraphs, no lists or URLs...

## [en] World news
...English text...

## [fr] L'actualite de la France
...texte en francais...
```

Optional `summary.md` in the same folder becomes the episode description.

## Voices and limits

Edit `config.json`:
- `voices`: Google voice names. Stay with **Neural2** or **WaveNet** voices to remain in the free tier.
- `max_chars_per_episode` and `max_chars_per_month` stop a run before it can exceed the free allowance.
- `state/usage.json` tracks characters used per month.
