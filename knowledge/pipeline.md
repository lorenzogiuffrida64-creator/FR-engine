# Pipeline: from request to delivery

Brief steps (knowledge/brief.md) → what happens and who does it. **Claude** = the creative and judging
work done by Claude Code. **engine** = `python3 scripts/engine.py …`. Review points belong to the client.

## 0. A request arrives
- **Immediate:** the client writes what happened ("goal by X, I want graphics"). Claude maps it to players
  in `private/archive/players/` and opens it:
  `engine.py new x-goal --text "..." --player <player-slug>:home`
- **Pre-match:** the daily job opens them (see section 8).
- **Group (5–9 players):** `--type group`, shots at 3:2.
Missing a player or club in the archive? Stop and add it first (`knowledge/archive.md`). Never guess a face.

## 1. Ideas → `requests/<id>/ideas.md`
Claude writes 3–5 directions from `private/knowledge/concepts.md`: concept, mood board, why it fits this player
(signature traits from `player.json`), the symbol of the event. Positive tone only.
If the client gave their own idea in the request, write that one only.
*Review point (optional): the client picks or corrects. Immediate requests skip it.*

## 2. Prompts → `requests/<id>/prompts.json`
One entry per direction kept (usually 2–3):
```json
[{"id": "p1", "concept": "night pitch alone", "moodboard": "night-stadium", "model": "both",
  "aspect_ratio": "3:4", "text": "<nine-block prompt>"}]
```
Rules: `knowledge/prompt-system.md` (blocks 01/08/09 pasted from `private/moodboards/<style>/dna.json`, edit-ready,
no names). Set `request.json → concept / moodboard` to the main one. Then `engine.py lint <id>` must say ok.

## 3. Shots
`engine.py shots <id>` → Soul 2.0 + Soul Cinema in parallel, 16 shots (immediate) or 24 (planned),
downloaded to `shots/`, numbered contact sheet `sheet-shots.jpg`.

Measured on the API (2026-11-10):
- `resolution: 1080p` at 3:4 returns **1536×2048**, the same size as "2k" on the Higgsfield web app.
- Cost (free `POST /estimate/<model>` with the same body): Soul 2.0 1080p ×4 = **$0.023**, ×1 = $0.006,
  720p ×4 = $0.013; Soul Cinema 1080p ×4 = $0.022. A 16-shot request costs about $0.10 in Higgsfield.
- Output files are deleted by Higgsfield after 7 days: the engine downloads every shot straight away.
- Failed and moderated (`nsfw`) requests are not charged.

Concurrency on the API (open.higgsfield.ai/pricing + docs, read 2026-11-10):
- Unlocked by **funds added in the past 28 days** (not the current balance): new account 2 · ≥$25 → 10 ·
  ≥$100 → 20 · ≥$1,000 → 40 · more via sales (support@higgsfield.ai), incl. dedicated capacity.
- Account limit covers all models; some models have their own extra limit. Current value: Console only
  (no API endpoint, no rate-limit headers).
- Above the limit, requests are still accepted as `queued` and start on their own. The queue is capped at a
  multiple of the limit (each batch output counts); when full → `429 account_queue_full` + `Retry-After`,
  nothing charged. Resubmit after `Retry-After` with the same Idempotency-Key.
- Set `config.json → higgsfield.max_parallel` to the account's current limit.

## 4. Pre-selection (Claude)
Open the contact sheet, then the strongest shots at full size. Keep the best ~10 that are both:
- **on mood board** (light, palette, grain, the concept reads at a glance), and
- **edit-ready** (faces big, frontal or three-quarter, chest blank, players separated, hands clean).
`engine.py select <id> 3 7 9 …`. For several players, fill each `bbox` in `selected.json`
(`[x0, y0, x1, y1]` as fractions, from the top of the head to at least the waist; `engine.py grid <id> <n>`
draws a grid to read them). Add `"back": true` to a slot whose back is visible (name and number).

## 5. Identity (faces and kits)
`engine.py identity <id>` → one Nano Banana 2.1 Edit call per player, fallback chain on refusals,
harmonisation pass, `edited/NN.png`, `sheet-edited.jpg`. Details: `knowledge/identity-edit.md`.

Platform (checked 2026-11-10): the edit models stay on **fal.ai**. The Higgsfield API has no Nano Banana and
no stand-alone GPT Image edit (only Soul, Grok Image 2.0, Qwen Image 3, Recraft, Ideogram, Marketing/Ads
Studio). Nano Banana 2.1 is only in the Higgsfield web app. fal also exposes the safety settings
(Nano Banana `safety_tolerance` "1"–"6", default "4"; GPT Image `enable_safety_checker`, default true), while
Higgsfield adds its own moderation on input and output with no setting. The model makers' own filters
(Google, OpenAI) apply on both.

## 6. Quality control
`engine.py qc <id>` measures kit colour coverage (and face similarity when insightface is installed).
Then Claude checks **every** edited image by eye against the face archive and the kit photo:
face, hair, beard · crest shape and position · sponsor spelling · name/number · hands · seams · extra text.
`engine.py verdict <id> <n> pass|fail --note "..."`. For a fail on one player: `identity --only n --slot X`
(max 2 retries), then drop it. Aim to hand the client 4–8 passes.

## 7. Delivery
The client picks (in the platform, or numbers in chat). `engine.py deliver <id> 3 7 --formats feed,story,x`
→ `final/` with the AI tag, copied to `private/library/` and logged in `private/library/library.json`.
Kit wrong? `engine.py kit <id> B away` then `engine.py identity <id> --slot B`.
"Rifai queste": back to step 2 with his notes written into `ideas.md`.

## 8. Pre-match automation (daily, config `prematch.run_local_time`)
1. `prematch.py fixtures` → tomorrow's matches in the configured competitions, big ones marked
   (two tier-1 clubs, Champions League knockout, listed derbies).
2. `prematch.py plan` → one `prematch` request per big match: 2 players per team from the archive
   (priority order, `available: true` only), kits by the clash rule (home in home; away in home unless the
   colours clash, then away).
3. For each opened request run steps 1–6 without waiting for the client (concept: a VS face-off from
   `private/knowledge/concepts.md`, both clubs in one shared setting).
4. Message the summary (request ids + the edited contact sheets) so the client picks the evening before.
Injured or suspended player? Set `"available": false` in `player.json` (the next in priority is used).

## 9. Learning
After posting, write the likes into `private/library/library.json → likes`. When choosing concepts, prefer the ones
with the highest likes for that event type. New winning graphics go to `private/knowledge/concepts.md`.
