# FR-engine: football graphics engine

Turns football events into finished graphics: artistic shots with Soul 2.0 / Soul Cinema (Higgsfield),
real faces and kits with Nano Banana 2.1 Edit (fal.ai), measured quality control, delivery with an AI tag,
and a daily pre-match automation driven by fixtures (football-data.org). Claude Code orchestrates it; a web
platform can sit on top of the same folders and commands.

This public repo is the engine only. Client material lives in a separate private repo (see `SECURITY.md`).

## Setup
1. `FR_PRIVATE_REPO=<private repo url> scripts/setup.sh` (installs the security hooks, clones `private/`, creates `.env`).
2. Fill `.env`: Higgsfield key id + secret, `FAL_KEY`, `FOOTBALL_DATA_TOKEN`.
3. Python 3.9+ with Pillow and numpy. Optional face similarity: `pip install insightface onnxruntime`.
4. `python3 scripts/engine.py archive-check` to see which players and clubs still miss photos.
Without access to the private repo, copy `private.example/` to `private/` to try the engine on your own data.

## Flow
```
request ─▶ ideas.md ─▶ prompts.json ─▶ lint ─▶ shots (Soul 2.0 + Cinema) ─▶ select (+ player boxes)
        ─▶ identity (Nano Banana, one player at a time, fallback chain) ─▶ qc (+ Claude's eye) ─▶ deliver ─▶ library
prematch.py plan (daily) ─▶ opens one request per big match ─▶ same flow
```
Full steps and commands: `knowledge/pipeline.md`.

## Folders
| Path | What |
|---|---|
| `knowledge/` | pipeline, prompt system, identity edit, archive rules |
| `scripts/` | `engine.py`, `prematch.py`, API clients (`higgsfield.py`, `fal.py`), `images.py`, `security_check.py`, `setup.sh`, `hooks/` |
| `config.json` | engine settings (models, counts, QC thresholds, formats, pre-match rules) |
| `private/` (private repo) | `config.json` overrides, brief, concepts, references, `archive/`, `moodboards/`, `requests/`, `library/` |
| `private.example/` | the same structure with invented data |

## For the platform
Each request folder is the state. The platform can create a request (`engine.py new`), show `sheet-*.jpg`
and `edited/*.png` with `qc.json`, send picks (`engine.py deliver`), switch kits (`engine.py kit`) and
trigger re-runs. Every command prints JSON.
