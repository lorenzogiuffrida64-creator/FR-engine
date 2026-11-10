# Prompt system: football edition

Every Soul 2.0 / Soul Cinema prompt the engine writes follows this file: a nine-block photography
method adapted to football, plus the rules that make a shot **edit-ready** for the identity step.

## The four laws (unchanged)
1. **Order is weight.** The capture medium opens the prompt. Small details come last.
2. **Prose, not tag soup.** Full sentences, written like a brief to a photographer.
3. **Physical causes, not adjectives.** "Hard white floodlight from high behind both shoulders" can be drawn. "Epic lighting" can't.
4. **Identical, not similar.** Inside one request, the look blocks (01, 08, 09) are pasted word for word.

## Banned words
8k · 4k · masterpiece · best quality · ultra detailed · hyperrealistic · hyper-detailed · photorealistic ·
stunning · breathtaking · award-winning · trending on artstation · cinematic lighting · epic · beautiful ·
perfect skin · flawless · octane render · unreal engine · "high quality" · "model-like features"

Football-specific bans (they break the identity step): **real player names, club names, sponsor names,
crest descriptions, shirt numbers, shirt names.** Soul never knows who the player is. Identity comes later.
`engine.py lint` rejects prompts that contain them (names come from `private/archive/`).

## Edit-ready rules (block 03 and 06 must respect them)
The identity step (Nano Banana 2.1 Edit) works best when the shot was built to receive a face and a kit.
- **Face:** large in frame (the head is at least ~8% of the image height), frontal or three-quarter, eyes
  visible, nothing across the face (no hands, hair, ball, mask) unless the concept needs it.
- **Light on the face:** readable. Rim light is fine, a face lost in shadow is not.
- **Kit:** the right base colours (from the kit archive, as words, e.g. "deep navy blue with a red centre
  stripe edged in white"), but **a blank chest: no crest, no sponsor, no number, no name.** Write it
  literally: "the chest completely blank with no crest, no sponsor and no number".
- **Several players:** bodies clearly separated, no overlapping heads, each face at a similar size. Name
  them by position ("the player on the left", "the player standing behind on the right"), never by name.
  Maximum 4 players for a 3:4 frame; 5–9 only in wide group concepts (Ballon d'Or style) at 16:9 or 3:2.
- **Build:** describe build, skin tone by value, hair and beard in neutral terms close to the real player
  (from `player.json → look`). The closer the base, the less the edit has to change.

## The nine blocks (one paragraph of prose, 180–350 words)
```
[01 CAPTURE]      ___ photograph on ___ (camera / film / sensor), ___ (genre). From the mood board DNA.
[02 CAMERA]       Shot from ___ with a ___mm lens at ___ height. Framing from ___ to ___.
[03 PLAYERS]      Per player: age range, build, skin tone by value, hair, beard, expression and gaze LAST.
                  Position in frame for multi-player shots. Face frontal or three-quarter.
[04 ACTION]       The concept's single action. Every hand has a job. Secondary motion.
[05 COLOUR LOCK]  Every [club A] garment is the same ___ (value + cast), never ___, never ___.
                  One sentence per club in multi-club shots, so the two kits never blend.
[06 KIT]          Shirt construction (collar, cuffs, stripes, panels) in the locked colours, shorts, socks,
                  boots. Chest blank. Off-pitch concepts: tailoring / training gear described the same way.
[07 ENVIRONMENT]  Setting, materials, two boring real details, the symbolic prop, what is cropped out.
[08 LIGHT]        Source + quality + K + direction + a contact shadow. From the mood board DNA.
[09 TEXTURE]      Palette (5–6 named colours) + contrast & black level + grain + skin pores, fabric weave.
```
- Blocks 01 · 08 · 09 come from the chosen mood board (`private/moodboards/<style>/dna.json`), pasted as written.
- Blocks 02 · 04 · 07 come from the concept.
- Blocks 03 · 05 · 06 come from the archive (player look, kit colours) translated into neutral words.

## Soul 2.0 vs Soul Cinema
- **Soul 2.0** (`higgsfield-ai/soul/v2/standard`): editorial, faithful to prose, best for daylight, interiors,
  studio, accepts a `style_id`. Use it for colour-critical kits.
- **Soul Cinema** (`higgsfield-ai/soul/cinema`): more contrast and drama, fixed style (style_id ignored).
  It saturates: ban the bright neighbours of every kit colour by name in block 05 for the Cinema leg
  ("never magenta, never fuchsia" for a claret kit).
- Default split per request: half and half. Both at 3:4, 1080p (4:5 crop later). Wide group concepts at 3:2.

## The concept formula (block 04 + 07)
**one signature trait of the player + one symbol of the event + one strong, simple composition.**
The glasses close-up with the Ballon d'Or in the lenses (2M likes) is the model. See `private/knowledge/concepts.md`.

## Audit before generating
Read each prompt once looking only for leftovers: names, numbers, sponsors, crests, objects that are not in
the concept. Every orphan word is an instruction. `engine.py lint <request>` catches the obvious ones.

## Example (Soul 2.0 / Cinema, hat-trick night, single player)
```text
Medium-format digital sports editorial photograph on a Hasselblad, a real magazine shoot inside a football stadium at night rather than a render. Shot from a low position just above the grass with a 50mm lens, framing the player centred from the top of his head to mid-shin, with the empty stands rising behind him. He is a professional footballer in his late twenties, lean and athletic, with olive skin, short dark hair in a tight fade, a short trimmed beard, a defined jaw, and a calm, proud stare straight into the lens, his face frontal and fully lit. He stands square to camera with his weight on his right leg, the match ball tucked against his right hip under his forearm, and his left hand raised at chest height with three fingers open. Two more match balls rest on the wet grass at his feet. Every blue garment is the same deep royal blue, a saturated mid-dark blue, never navy-black, never turquoise, never violet. His shirt is a short-sleeve football jersey in that royal blue with a thin white ribbed crew collar and white cuffs, the chest completely blank with no crest, no sponsor and no number. He wears matching shorts in that blue and white socks pulled over shin pads. The pitch is freshly watered, with droplets on the grass and the white centre-circle line curving behind his boots. The stands are rows of empty seats fading into darkness, and the edge of the stadium roof is cut off by the top of the frame. Hard white floodlight from high behind both shoulders at 5600K rims his hair and shoulders, a soft frontal fill keeps his face readable, fine mist catches the light, and a sharp contact shadow sits under his boots. The palette is royal blue, white, wet green, black and warm skin, with deep blacks that are not crushed. There is fine grain over the whole frame, visible weave in the jersey fabric, and sweat and pores on the skin.
```

## Learned from tests
- **"Cropped out of frame" doesn't remove stadium advertising boards** (Soul 2.0, 2026-11-10, 4 of 4 shots
  at pitch level had boards, 3 with made-up lettering). Soul draws what a pitch-side stadium has. Fix in
  block 02/07: frame so the boards are physically not there (camera low looking up at stands and night
  sky, or a tighter crop above the boards), and describe only what *is* behind the player.
- **The blank-chest sentence mostly holds** (3 of 4); the fourth grew a small made-up logo with letters.
  Keep the sentence, and expect to reject or fix about one shot in four at pre-selection.
- **Soul Cinema with the same prompt (2026-11-10, 4 shots):**
  - Chest blank in 4 of 4: better than Soul 2.0.
  - Tighter framing and larger faces on its own, with more contrast, softer film and more drama.
  - **Deep navy turns bright cobalt / electric blue**, slightly violet in 2 shots. In the Cinema leg, block 05
    must ban the bright neighbours of navy by name: "never cobalt, never electric blue, never bright royal blue".
  - **The centre stripe drifts** off-centre or narrows in 3 of 4. Pin it: "one wide red stripe exactly in the
    centre of the chest, running straight from the collar to the hem".
  - It also adds LED boards in magenta and pink with made-up lettering, so the block 02/07 fix above
    applies to both models.

## How to iterate
Change one variable per pass. Name what failed ("the claret went magenta"), find the block responsible
(05), fix only that block. Everything else stays word for word.
- **Soul 2.0 + "Theatrical light" style (2026-11-10, full-body night action):** warmer, darker and more
  filmic than Soul 2.0's default, and it keeps the slimmer build Soul 2.0 follows better than Cinema.
  A good middle between Soul 2.0's accuracy and Cinema's drama. Expect small swooshes/crests on the chest.
- **No poster composites (Lorenzo, 2026-11-10).** A giant floating portrait above a small full figure, double
  exposures and collage layouts are out, even when they look striking: every graphic must read as one real
  photograph taken in one place. Soul Cinema drifts into this layout by itself on symmetrical "gallery"
  briefs; reject those shots at pre-selection.
