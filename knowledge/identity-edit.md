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
- `config.json → fal.edit_models` is an ordered list. The first is `google/nano-banana-2.1/edit`.
- A slot moves to the next model when the call errors, returns no image, or returns an image where the
  face region barely changed (`fal.unchanged_threshold`: the model silently ignored the edit).
- Every attempt is logged in `private/requests/<id>/edits.json` with the model used.

## Settings
`resolution: 2K`, `output_format: png`, `aspect_ratio: auto` (keeps the crop's ratio), `num_images: 1`.
`safety_tolerance` stays at the default. Multiple attempts per slot come from re-running, not from batch.
