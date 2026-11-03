# Archive: players, clubs, kits, crests

The identity step is only as good as this folder. Every player and club the engine can use lives in
`private/archive/` (never in the public repo: the photos are licensed).

## Player: `private/archive/players/<slug>/`
- `player.json`
  ```json
  {"slug": "marco-rossi", "name": "Marco Rossi", "club": "example-fc", "national_team": "italy",
   "number": 10, "shirt_name": "ROSSI", "priority": 1, "available": true,
   "look": "neutral description used in Soul prompts (build, skin tone, hair, beard)",
   "traits": ["signature things for ideas: accessories, celebrations, nicknames, awards"]}
  ```
  `priority` orders players inside a club for the pre-match picks (1 = first choice).
  `available: false` when injured or suspended.
- `faces/` 3–6 recent full-resolution licensed photos, sharp, face large, no sunglasses unless that is the
  point. Name order = use order: `01-frontal.jpg`, `02-…`. The first 3 go to every edit.
  Update when the haircut or beard changes.

## Club: `private/archive/clubs/<slug>/`
- `club.json`
  ```json
  {"slug": "example-fc", "name": "Example FC", "short": "EFC", "aliases": ["Example Football Club"],
   "football_data_id": 0, "tier": 1, "crest": "crest.png",
   "kits": {"home": {"season": "2026/27", "primary": "#1f3a8f", "secondary": "#d1263a", "accent": "#ffffff",
                     "colour_words": "for Soul prompts (no brand names)",
                     "description": "for the identity edit: construction, stripes, collar, shorts, socks",
                     "sponsor": "Example Air", "file": "kits/home.jpg"}}}
  ```
  `tier: 1` makes a club count for "big match" in the pre-match job. `football_data_id` links fixtures.
  Hex colours: sample them from the kit photo (shirt in neutral light), not from the club website.
- `kits/home.jpg`, `kits/away.jpg`, `kits/third.jpg`: one clear front photo per kit (official or media day).
- `crest.png`: official crest, transparent background.

## Check
`engine.py archive-check` lists players with fewer than 3 faces and clubs missing a crest or kit photo.
Start with the top 10 clubs and 2–4 players each; grow from the client's list.
