#!/usr/bin/env python3
"""Football graphics engine. Claude Code does the creative work (ideas, prompts, picking, bboxes,
eye checks); this CLI does everything that is mechanical: folders, API calls, crops, QC numbers, delivery.

  engine.py status
  engine.py new <slug> --text "gol di X..." --player <slug>[:home|away|third] [--player ...] [--type immediate|prematch|group]
  engine.py lint <id>                         # check prompts.json before spending credits
  engine.py shots <id> [--count 24] [--only p1,p2]   # Soul 2.0 / Soul Cinema → shots/ + contact sheet
  engine.py sheet <id> [--stage shots|edited]
  engine.py grid <id> <n>                     # gridlines on shot n, to read player boxes for selected.json
  engine.py select <id> 3 7 12                # pre-selection → selected.json (fill bboxes for multi-player)
  engine.py identity <id> [--only 3,7] [--slot A] [--no-harmonize]   # Nano Banana per player → edited/
  engine.py qc <id>                           # kit colour + face numbers → qc.json + edited contact sheet
  engine.py verdict <id> <n> pass|fail [--note "..."]
  engine.py kit <id> <slot> <home|away|third> # the one-click kit switch (then re-run identity --slot)
  engine.py deliver <id> 3 7 [--formats feed,story,x]   # final/ with AI tag + library
  engine.py archive-check [--player <slug> ...]
"""
import argparse, json, re, shutil, sys

from common import (ARCHIVE, CFG, LIBRARY, REQ, club, download, face_files, load_req, out, player,
                    protected_words, read_json, req_dir, save_req, slugify, today, write_json)
import images as im

BANNED = ["8k", "4k", "masterpiece", "best quality", "ultra detailed", "hyperrealistic", "hyper-detailed",
          "photorealistic", "stunning", "breathtaking", "award-winning", "trending on artstation",
          "cinematic lighting", "epic", "beautiful", "perfect skin", "flawless", "octane render",
          "unreal engine", "high quality", "model-like features"]
SLOTS = "ABCDEFGHI"


def stage(d):
    for name, s in (("final", "delivered"), ("qc.json", "qc"), ("edited", "edited"), ("selected.json", "selected"),
                    ("shots.json", "shots"), ("prompts.json", "prompts"), ("ideas.md", "ideas")):
        if (d / name).exists():
            return s
    return "new"


# ---------- requests ----------

def cmd_status(a):
    rows = []
    for d in sorted(REQ.glob("*/request.json")):
        r = json.loads(d.read_text())
        rows.append({"id": r["id"], "type": r["type"], "stage": stage(d.parent),
                     "players": ", ".join(f"{p['slot']}:{p['player']}({p['kit']})" for p in r["players"])})
    if not rows:
        print("no requests yet"); return
    for r in rows:
        print(f"{r['id']:40} {r['type']:9} {r['stage']:9} {r['players']}")


def cmd_new(a):
    rid = f"{today()}-{slugify(a.slug)}"
    if (REQ / rid / "request.json").exists():
        sys.exit(f"{rid} already exists")
    players = []
    for i, spec in enumerate(a.player or []):
        slug, _, kit = spec.partition(":")
        pl = player(slug)
        c = club(pl["club"])
        kit = kit or "home"
        if kit not in c.get("kits", {}):
            sys.exit(f"{c['slug']} has no {kit} kit in the archive")
        players.append({"slot": SLOTS[i], "player": slug, "club": pl["club"], "kit": kit})
    r = {"id": rid, "type": a.type, "created": today(), "text": a.text, "players": players,
         "match": json.loads(a.match) if a.match else None, "concept": None, "moodboard": None,
         "formats": a.formats.split(",") if a.formats else CFG["delivery"]["default_formats"]}
    save_req(r)
    for sub in ("prompts", "shots", "work"):
        (REQ / rid / sub).mkdir(exist_ok=True)
    out({"id": rid, "folder": str(REQ / rid), "players": players,
         "next": "write ideas.md, then prompts.json (knowledge/prompt-system.md), then engine.py lint"})


def _prompts(d):
    p = d / "prompts.json"
    if not p.exists():
        sys.exit(f"write {p} first: [{{\"id\": \"p1\", \"model\": \"both|soul|cinema\", \"text\": \"...\", \"aspect_ratio\": \"3:4\"}}]")
    return json.loads(p.read_text())


def cmd_lint(a):
    d = req_dir(a.id)
    prot = protected_words()
    problems = []
    for p in _prompts(d):
        t = p["text"]; low = t.lower(); n = len(t.split())
        for w in BANNED:
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
                problems.append(f"{p['id']}: banned word '{w}'")
        for w in prot:
            if re.search(rf"\b{re.escape(w.lower())}\b", low):
                problems.append(f"{p['id']}: real name/sponsor '{w}' (identity is added later, never in Soul)")
        if re.search(r"\bnumber \d+|\b#\d+", low):
            problems.append(f"{p['id']}: shirt number in the prompt")
        if "no crest" not in low and p.get("kit", True):
            problems.append(f"{p['id']}: missing the blank-chest sentence ('no crest, no sponsor and no number')")
        if not 150 <= n <= 380:
            problems.append(f"{p['id']}: {n} words (aim for 180–350)")
        if p.get("model", "both") not in ("both", "soul", "cinema"):
            problems.append(f"{p['id']}: model must be both, soul or cinema")
    out({"id": a.id, "ok": not problems, "problems": problems})


def cmd_shots(a):
    import higgsfield
    d = req_dir(a.id); r = load_req(a.id)
    prompts = [p for p in _prompts(d) if not a.only or p["id"] in a.only.split(",")]
    g = CFG["generation"]; bs = CFG["higgsfield"]["batch_size"]
    total = a.count or (g["shots_per_request_immediate"] if r["type"] == "immediate" else g["shots_per_request"])
    legs = []
    for p in prompts:
        models = ["soul", "cinema"] if p.get("model", "both") == "both" else [p["model"]]
        for m in models:
            legs.append((p, m))
    per_leg = max(1, round(total / len(legs) / bs))  # batches per leg
    jobs = [{"prompt_id": p["id"], "model": m, "prompt": p["text"], "style_id": p.get("style_id"),
             "aspect_ratio": p.get("aspect_ratio") or (CFG["higgsfield"]["aspect_ratio_group"] if r["type"] == "group" else None)}
            for p, m in legs for _ in range(per_leg)]
    print(f"{len(jobs)} Higgsfield jobs × {bs} images ≈ {len(jobs) * bs} shots", file=sys.stderr)
    results = higgsfield.generate(jobs)
    meta = read_json(d / "shots.json", [])
    n = len(meta)
    for res in results:
        if res["status"] != "completed":
            meta.append({"n": None, "prompt_id": res["prompt_id"], "model": res["model"], "status": res["status"],
                         "error": res.get("error")})
            continue
        for url in res["images"]:
            n += 1
            dest = d / "shots" / f"{n:02d}.jpg"
            download(url, dest)
            im.open_rgb(dest).save(dest, quality=95)  # normalise to jpeg
            meta.append({"n": n, "prompt_id": res["prompt_id"], "model": res["model"], "request_id": res["request_id"],
                         "url": url, "file": f"shots/{dest.name}"})
    write_json(d / "shots.json", meta)
    failed = [m for m in meta if m["n"] is None]
    sheet = _sheet(d, "shots")
    out({"id": a.id, "shots": n, "failed_jobs": failed, "contact_sheet": str(sheet)})


def _sheet(d, stage_name):
    r = json.loads((d / "request.json").read_text())
    if stage_name == "shots":
        items = [(f"#{m['n']} {m['model'][0].upper()}", d / m["file"]) for m in read_json(d / "shots.json", []) if m["n"]]
    else:
        items = [(f"#{int(p.stem)}", p) for p in sorted((d / "edited").glob("[0-9][0-9].png"))]
    if not items:
        sys.exit(f"nothing to show for {stage_name}")
    return im.contact_sheet(items, d / f"sheet-{stage_name}.jpg", f"{r['id']} · {stage_name} · {len(items)}")


def cmd_sheet(a):
    out({"contact_sheet": str(_sheet(req_dir(a.id), a.stage))})


def cmd_grid(a):
    d = req_dir(a.id)
    dest = d / "work" / f"{a.n:02d}-grid.jpg"
    im.grid_overlay(d / "shots" / f"{a.n:02d}.jpg", dest)
    out({"grid": str(dest), "next": "read each player's box as [x0, y0, x1, y1] fractions (head to waist at least) into selected.json"})


def cmd_select(a):
    d = req_dir(a.id); r = load_req(a.id)
    shots = {m["n"]: m for m in read_json(d / "shots.json", []) if m["n"]}
    sel = []
    for n in map(int, a.numbers):
        if n not in shots:
            sys.exit(f"no shot #{n}")
        if len(r["players"]) == 1:
            slots = [{"slot": "A", "bbox": [0, 0, 1, 1]}]
        else:
            slots = [{"slot": p["slot"], "bbox": None} for p in r["players"]]
        sel.append({"shot": n, "slots": slots})
    write_json(d / "selected.json", sel)
    todo = len(r["players"]) > 1
    out({"id": a.id, "selected": [s["shot"] for s in sel],
         "next": "fill every bbox in selected.json (engine.py grid <id> <n> helps), then identity" if todo else "engine.py identity"})


def _kit(c, kit):
    k = c["kits"][kit]
    return k, c["_dir"] / k["file"] if k.get("file") else None


def _slot_prompt(pl, c, kit, n_faces, back=False):
    k, kit_file = _kit(c, kit)
    idx = 1 + n_faces + 1
    kit_index = idx if kit_file and kit_file.exists() else None
    crest = c["_dir"] / c.get("crest", "crest.png")
    crest_index = (kit_index or idx - 1) + 1 if crest.exists() else None
    parts = [f"Image 1 is a photograph of a footballer. Replace his face and hair with the man shown in images 2 to {1 + n_faces}: "
             "same face shape, skin tone, eyes, nose, lips, hairline, hairstyle and beard. Keep his pose, body, expression direction, "
             "the light falling on him, the grain and the colours of image 1 exactly as they are."]
    kit_ref = f" in image {kit_index}" if kit_index else ""
    parts.append(f"Make his kit match the {c['name']} {kit} kit{kit_ref}: {k['description']}.")
    logos = []
    if crest_index:
        logos.append(f"the crest from image {crest_index} on the left chest")
    if k.get("sponsor"):
        logos.append(f"the sponsor {k['sponsor']} centred on the chest")
    if back and pl.get("number"):
        logos.append(f"the name {pl.get('shirt_name', '')} and number {pl['number']} on the back")
    if logos:
        parts.append("Place " + ", ".join(logos) + ". All logos follow the folds and the light of the fabric.")
    parts.append("Change nothing else in image 1.")
    refs = [kit_file] if kit_index else []
    refs += [crest] if crest_index else []
    return " ".join(parts), refs


HARMONIZE = ("Unify the lighting, colour grading, grain and skin rendering of this photograph so every part looks shot in one "
             "exposure. Do not change any face, any logo, any number, any pose or the composition.")


def cmd_identity(a):
    import fal
    d = req_dir(a.id); r = load_req(a.id)
    F = CFG["fal"]
    sel = read_json(d / "selected.json", None) or sys.exit("run engine.py select first")
    only = set(map(int, a.only.split(","))) if a.only else None
    by_slot = {p["slot"]: p for p in r["players"]}
    log = read_json(d / "edits.json", [])
    (d / "edited").mkdir(exist_ok=True); work = d / "work"; work.mkdir(exist_ok=True)
    report = []
    for s in sel:
        n = s["shot"]
        if only and n not in only:
            continue
        missing = [x["slot"] for x in s["slots"] if not x.get("bbox")]
        if missing:
            report.append({"shot": n, "skipped": f"no bbox for slots {missing}"}); continue
        base = d / "edited" / f"{n:02d}-raw.png"
        src = base if (a.slot and base.exists()) else d / "shots" / f"{n:02d}.jpg"
        img = im.open_rgb(src)
        shot_ok = True
        for x in s["slots"]:
            if a.slot and x["slot"] != a.slot:
                continue
            p = by_slot[x["slot"]]; pl = player(p["player"]); c = club(p["club"])
            faces = face_files(pl, F["max_faces"])
            if not faces:
                sys.exit(f"no face photos for {pl['slug']} in {pl['_dir'] / 'faces'}")
            crop_path = work / f"{n:02d}-{x['slot']}-crop.jpg"
            box = im.crop_for_edit(img, x["bbox"], F["crop_padding"], F["crop_min_side"], crop_path)
            prompt, extra = _slot_prompt(pl, c, p["kit"], len(faces), x.get("back", False))
            result_path = work / f"{n:02d}-{x['slot']}-edit.png"

            def accept(res, result_path=result_path, crop_path=crop_path):
                download(res["images"][0]["url"], result_path)
                diff = im.mean_abs_diff(crop_path, im.open_rgb(result_path))
                return (diff >= F["unchanged_threshold"], f"diff {diff:.1f}")

            res, model, attempts = fal.edit_with_fallback(prompt, [crop_path, *faces, *extra], accept)
            log.append({"shot": n, "slot": x["slot"], "player": p["player"], "kit": p["kit"], "model": model,
                        "attempts": attempts, "prompt": prompt, "date": today()})
            if not res:
                shot_ok = False
                report.append({"shot": n, "slot": x["slot"], "failed": attempts}); continue
            img = im.blend_back(img, result_path, box)
            report.append({"shot": n, "slot": x["slot"], "model": model})
        if not shot_ok:
            continue
        img.save(base)
        final = d / "edited" / f"{n:02d}.png"
        if F["harmonize"] and not a.no_harmonize:
            hpath = work / f"{n:02d}-harmonize.png"
            res, model, attempts = fal.edit_with_fallback(
                HARMONIZE, [base], lambda res, hpath=hpath: (download(res["images"][0]["url"], hpath) and True, "ok"))
            log.append({"shot": n, "slot": "*", "harmonize": True, "model": model, "attempts": attempts, "date": today()})
            if res:
                im.open_rgb(hpath).resize(img.size).save(final)
            else:
                img.save(final)
        else:
            img.save(final)
    write_json(d / "edits.json", log)
    sheet = _sheet(d, "edited") if list((d / "edited").glob("[0-9][0-9].png")) else None
    out({"id": a.id, "report": report, "contact_sheet": str(sheet) if sheet else None, "next": "engine.py qc"})


def cmd_qc(a):
    d = req_dir(a.id); r = load_req(a.id)
    sel = {s["shot"]: s for s in read_json(d / "selected.json", [])}
    by_slot = {p["slot"]: p for p in r["players"]}
    old = {q["n"]: q for q in read_json(d / "qc.json", [])}
    rows = []
    for f in sorted((d / "edited").glob("[0-9][0-9].png")):
        n = int(f.stem); img = im.open_rgb(f); slots = []
        for x in sel.get(n, {}).get("slots", []):
            p = by_slot[x["slot"]]; c = club(p["club"]); k = c["kits"][p["kit"]]
            cols = {kname: k[kname] for kname in ("primary", "secondary") if k.get(kname)}
            cov = im.kit_coverage(img, x["bbox"], cols) if cols else {}
            kit_ok = cov.get("primary", 0) >= CFG["qc"]["kit_min_coverage"] if cov else None
            sim = im.face_similarity(f, x["bbox"], face_files(player(p["player"])))
            face_ok = None if sim is None else sim >= CFG["qc"]["face_similarity_min"]
            slots.append({"slot": x["slot"], "player": p["player"], "kit": p["kit"], "kit_coverage": cov,
                          "kit_ok": kit_ok, "face_similarity": sim, "face_ok": face_ok})
        checks = [s[k] for s in slots for k in ("kit_ok", "face_ok")]
        auto = "fail" if False in checks else ("needs_eye" if None in checks or not slots else "pass")
        prev = old.get(n, {})
        rows.append({"n": n, "auto": auto, "slots": slots, "verdict": prev.get("verdict"), "note": prev.get("note")})
    write_json(d / "qc.json", rows)
    out({"id": a.id, "qc": [{k: q[k] for k in ("n", "auto", "verdict")} for q in rows],
         "next": "look at every edited image next to the face archive (faces, crest, sponsor, number, hands), then engine.py verdict"})


def cmd_verdict(a):
    d = req_dir(a.id)
    rows = read_json(d / "qc.json", None) or sys.exit("run engine.py qc first")
    for q in rows:
        if q["n"] == a.n:
            q["verdict"], q["note"] = a.verdict, a.note
            write_json(d / "qc.json", rows); out(q); return
    sys.exit(f"no edited image #{a.n}")


def cmd_kit(a):
    r = load_req(a.id)
    for p in r["players"]:
        if p["slot"] == a.slot:
            c = club(p["club"])
            if a.kit not in c["kits"]:
                sys.exit(f"{c['slug']} has no {a.kit} kit")
            p["kit"] = a.kit; save_req(r)
            out({"id": a.id, "slot": a.slot, "kit": a.kit, "next": f"engine.py identity {a.id} --slot {a.slot}"}); return
    sys.exit(f"no slot {a.slot}")


def cmd_deliver(a):
    d = req_dir(a.id); r = load_req(a.id)
    fmts = a.formats.split(",") if a.formats else r.get("formats") or CFG["delivery"]["default_formats"]
    qc = {q["n"]: q for q in read_json(d / "qc.json", [])}
    sel = {s["shot"]: s for s in read_json(d / "selected.json", [])}
    final = d / "final"; final.mkdir(exist_ok=True)
    lib_dir = LIBRARY / r["id"]; lib_dir.mkdir(parents=True, exist_ok=True)
    lib = read_json(LIBRARY / "library.json", [])
    delivered = []
    for n in map(int, a.numbers):
        if qc.get(n, {}).get("verdict") == "fail":
            print(f"warning: #{n} failed QC, delivering anyway because it was picked", file=sys.stderr)
        src = d / "edited" / f"{n:02d}.png"
        if not src.exists():
            sys.exit(f"#{n} has no edited image")
        img = im.open_rgb(src)
        boxes = [x["bbox"] for x in sel.get(n, {}).get("slots", []) if x.get("bbox")]
        focus = (sum((b[0] + b[2]) / 2 for b in boxes) / len(boxes), sum(b[1] + (b[3] - b[1]) * 0.3 for b in boxes) / len(boxes)) if boxes else (0.5, 0.42)
        files = []
        for f in fmts:
            size = CFG["delivery"]["formats"][f]
            outp = final / f"{n:02d}-{f}.jpg"
            im.ai_tag(im.fit_crop(img, size, focus)).save(outp, quality=93)
            shutil.copy(outp, lib_dir / outp.name); files.append(outp.name)
        entry = {"request": r["id"], "n": n, "date": today(), "type": r["type"], "concept": r.get("concept"),
                 "moodboard": r.get("moodboard"), "players": [p["player"] for p in r["players"]],
                 "files": [f"{r['id']}/{x}" for x in files], "likes": None}
        lib = [e for e in lib if not (e["request"] == r["id"] and e["n"] == n)] + [entry]
        delivered.append({"n": n, "files": [str(final / x) for x in files]})
    write_json(LIBRARY / "library.json", lib)
    out({"id": a.id, "delivered": delivered})


def cmd_archive_check(a):
    clubs_needed, report = set(), []
    pls = [player(s) for s in a.player] if a.player else [json.loads(p.read_text()) | {"_dir": p.parent} for p in sorted((ARCHIVE / "players").glob("*/player.json"))]
    for pl in pls:
        nf = len(face_files(pl))
        report.append({"player": pl["slug"], "faces": nf, "ok": nf >= 3, "club": pl["club"]})
        clubs_needed.add(pl["club"])
    for cs in sorted(clubs_needed):
        c = club(cs)
        crest = (c["_dir"] / c.get("crest", "crest.png")).exists()
        kits = {k: bool(v.get("file") and (c["_dir"] / v["file"]).exists()) for k, v in c.get("kits", {}).items()}
        report.append({"club": cs, "crest": crest, "kit_photos": kits, "ok": crest and all(kits.values())})
    out(report)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(f=cmd_status)
    s = sub.add_parser("new"); s.add_argument("slug"); s.add_argument("--text", required=True)
    s.add_argument("--player", action="append"); s.add_argument("--type", default="immediate", choices=["immediate", "prematch", "group"])
    s.add_argument("--match"); s.add_argument("--formats"); s.set_defaults(f=cmd_new)
    s = sub.add_parser("lint"); s.add_argument("id"); s.set_defaults(f=cmd_lint)
    s = sub.add_parser("shots"); s.add_argument("id"); s.add_argument("--count", type=int); s.add_argument("--only"); s.set_defaults(f=cmd_shots)
    s = sub.add_parser("sheet"); s.add_argument("id"); s.add_argument("--stage", default="shots", choices=["shots", "edited"]); s.set_defaults(f=cmd_sheet)
    s = sub.add_parser("grid"); s.add_argument("id"); s.add_argument("n", type=int); s.set_defaults(f=cmd_grid)
    s = sub.add_parser("select"); s.add_argument("id"); s.add_argument("numbers", nargs="+"); s.set_defaults(f=cmd_select)
    s = sub.add_parser("identity"); s.add_argument("id"); s.add_argument("--only"); s.add_argument("--slot"); s.add_argument("--no-harmonize", action="store_true"); s.set_defaults(f=cmd_identity)
    s = sub.add_parser("qc"); s.add_argument("id"); s.set_defaults(f=cmd_qc)
    s = sub.add_parser("verdict"); s.add_argument("id"); s.add_argument("n", type=int); s.add_argument("verdict", choices=["pass", "fail"]); s.add_argument("--note"); s.set_defaults(f=cmd_verdict)
    s = sub.add_parser("kit"); s.add_argument("id"); s.add_argument("slot"); s.add_argument("kit"); s.set_defaults(f=cmd_kit)
    s = sub.add_parser("deliver"); s.add_argument("id"); s.add_argument("numbers", nargs="+"); s.add_argument("--formats"); s.set_defaults(f=cmd_deliver)
    s = sub.add_parser("archive-check"); s.add_argument("--player", action="append"); s.set_defaults(f=cmd_archive_check)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
