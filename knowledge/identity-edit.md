# Identity edit: faces, kits, crests (Nano Banana 2.1 Edit on fal.ai)

The art is done by Soul. This step only puts the real player into it: face, hair, kit details, crest,
sponsor, name and number. It must change nothing else.

## One player at a time (always, also for single-player shots)
One edit with 5–6 references loses both the kit and the face (the client's experience, and ours).
So the engine never edits several players in one call:

1. `selected.json` gives each player slot a box (`bbox`, fractions of the image) and who goes there.
2. For each slot, `engine.py identity` crops the box with padding, scales the crop so the model sees it at full
   resolution, and sends **only that player's** references:
   - image 1: the crop
   - images 2–4: up to 3 face photos from `private/archive/players/<slug>/faces/` (frontal first)
   - image 5: the kit reference for the assigned kit (`private/archive/clubs/<club>/kits/<kit>.jpg`)
   - image 6: the crest (`private/archive/clubs/<club>/crest.png`)
3. The edited crop is scaled back and blended into the shot with a feathered mask.
4. After all slots: an optional harmonisation pass on the whole image (light, grain, skin tone), then QC.

Single-player shots use the same path with one slot (the box can be the whole frame).

## Prompt templates (the engine fills the brackets)
**Player slot**
```text
Image 1 is a photograph of a footballer. Replace his face and hair with the man shown in images 2 to {n_faces_last}: same face shape, skin tone, eyes, nose, lips, hairline, hairstyle and beard. Keep his pose, body, expression direction, the light falling on him, the grain and the colours of image 1 exactly as they are. Make his shirt match the {club} {kit} kit in image {kit_index}: {kit_words}. Place the crest from image {crest_index} on the left chest, {sponsor_clause} {number_clause} All logos follow the folds and the light of the fabric. Change nothing else in image 1.
```
- `kit_words`: from `club.json → kits.<kit>.description`.
- `sponsor_clause`: "and the sponsor {sponsor} centred on the chest," when the kit has one.
- `number_clause`: only when the back or shorts are visible: "the name {shirt_name} and number {number} on the back."

**Harmonisation (whole image, optional)**
```text
Unify the lighting, colour grading, grain and skin rendering of this photograph so every part looks shot in one exposure. Do not change any face, any logo, any number, any pose or the composition.
```

## Blocks and fallbacks
Some models refuse some players (Messi on GPT Image). We never trick a filter with prompt games: it is
fragile and risks the account on a matchday. We route instead:
- `config.json → fal.edit_models` is an ordered list: `google/nano-banana-2.1/edit`, then
  `openai/gpt-image-2.6/flare/edit`.
- A slot moves to the next model when the call errors, returns no image, or returns an image where the
  face region barely changed (`fal.unchanged_threshold`: the model silently ignored the edit).
- Every attempt is logged in `private/requests/<id>/edits.json` with the model used.

## Settings
`resolution: 2K`, `output_format: png`, `aspect_ratio: auto` (keeps the crop's ratio), `num_images: 1`.
Multiple attempts per slot come from re-running, not from batch.

Safety (decided 2026-11-10): every edit is sent with the **least strict official setting** of its model,
from `config.json → fal.safety` (matched by id prefix):
- Nano Banana 2.1: `"safety_tolerance": "6"` (fal default "4", "1" is strictest).
- GPT Image 2.6 Flare / Sunburst: `"enable_safety_checker": false`. fal only honours this for accounts it
  has authorised; otherwise it is ignored and the normal check runs. Ask fal support to authorise the
  client's account.
This only relaxes fal's own filter (false positives on sweaty, shirtless or injury shots). Google's and
OpenAI's filters inside the models, including refusals of real public figures, are untouched: those are
handled by the fallback chain above, never by prompt tricks.

## Learned from tests
- **First real test (2026-11-10, one player, whole-frame edit, no crop):** Nano Banana 2.1 at "6" with 3 face
  photos + 1 kit photo turned a generic Soul player into a clearly recognisable star in 32 s, on 2 of 2
  shots. It rebuilt the full kit from the photo (stripes, crest, badges, trim), matched the skin tone of
  neck and arms and even added his real arm tattoo. Background players are left as they are.
- **The Soul base can be generic.** A base player of a different skin tone and age still worked; the
  prompt line "match the skin tone of his neck, arms and hands to that man" is doing its job.
- **GPT Image 2.6 Flare refuses real public figures** (fal 422 `content_policy_violation` on the prompt)
  even with `enable_safety_checker: false`. It stays as the fallback for other failures, but for a star it
  will not rescue a Nano Banana refusal.
- **Full-body action (2026-11-10, faces ~10% of frame height):** a whole-frame edit beat crop + paste back
  on both shots. The face was as good, and only the whole frame rebuilt the full kit (shorts, socks), the
  tattoo and the armband; the crop left the old shorts and socks below its edge. Keep the crop for small
  faces in group shots, or make the box cover the whole body.
- **The edit keeps the base's build.** A heavy Cinema body stays heavy under the new face. Describe the
  build in block 03 and prefer the base whose body is closest.
- **The kit photo's number is copied.** A kit reference showing a number puts that number on the edit:
  use a blank shop photo, or a photo of the same player.
- **A second, face-only pass is not worth it by default.** On a medium face the gain is barely visible; on a
  Cinema shot the likeness got stronger but the head came back larger and brighter than the body. It is a
  manual "Migliora il volto" option in the app instead.
- **For that face pass, give the model the body.** A crop of mostly face let the frontal reference photos
  turn and enlarge the head, and the paste-back left a ghost of the old head. A crop of about head to waist
  around the face box (margin 1.2× the box on each side), plus "do not copy their pose, angle or
  expression", kept size, position and gaze, and blended cleanly with a soft edge.
- **Never send `aspect_ratio: "auto"` to Nano Banana** (2026-11-10, trophy edit on a 3:4 shot): it came back
  2430×1760 landscape and re-framed the scene around bigger trophies. With the ratio fixed to the input's own
  (3:4) the framing held and only the trophies changed. Engine and app now send the nearest supported ratio.
- **Trophies (2026-11-10, Cubarsí):** a second edit with one reference photo per trophy, named by position
  ("the trophy on the far left becomes image 2…"), replaced four generic Soul trophies with the real ones:
  Aramco band, "YOUNG PLAYER OF THE TOURNAMENT", "FIFA WORLD CUP", "WORLD 11 · FIFPRO" all readable at
  normal size. Faces first, trophies second. Small engraved text can still come out garbled: zoom and check.
