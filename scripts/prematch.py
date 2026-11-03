#!/usr/bin/env python3
"""Pre-match automation: read tomorrow's fixtures, keep the big matches, and open one pre-match request
per match with 1–2 players per team and the right kits. Claude then runs the normal pipeline on them.

  prematch.py fixtures [--days 1] [--date 2026-11-04] [--sample fixtures.json]   # list matches, big ones marked
  prematch.py plan     [--days 1] [--date 2026-11-04] [--sample fixtures.json]   # open requests for the big ones
"""
import argparse, contextlib, datetime as dt, io, json
from argparse import Namespace

from common import CFG, REQ, all_clubs, all_players, http_json, need_env, out, slugify, today
import images as im

P = CFG["prematch"]
GROUP_STAGES = {"LEAGUE_STAGE", "GROUP_STAGE", "REGULAR_SEASON", "PRELIMINARY_ROUND", "PLAYOFFS", None}


def fetch(date_from, date_to, sample=None):
    if sample:
        return json.loads(open(sample).read())["matches"]
    (token,) = need_env(P["env_key"])
    url = (f"{P['base_url']}/matches?competitions={','.join(P['competitions'])}"
           f"&dateFrom={date_from}&dateTo={date_to}")
    return http_json("GET", url, headers={"X-Auth-Token": token}).get("matches", [])


def match_club(team, clubs):
    """football-data team → archive club (by id, then by name/aliases)."""
    for c in clubs:
        if c.get("football_data_id") and c["football_data_id"] == team.get("id"):
            return c
    names = {slugify(team.get(k) or "") for k in ("name", "shortName", "tla")} - {""}
    for c in clubs:
        if names & {slugify(x) for x in [c["name"], c.get("short", ""), c["slug"], *c.get("aliases", [])] if x}:
            return c
    return None


def is_big(m, home, away):
    if not (home and away):
        return False, "club missing from archive"
    if home.get("tier") == 1 and away.get("tier") == 1:
        return True, "two tier-1 clubs"
    if m.get("competition", {}).get("code") == "CL" and m.get("stage") not in GROUP_STAGES:
        return True, "Champions League knockout"
    pair = {home["slug"], away["slug"]}
    if any(pair == set(d) for d in P["derbies"]):
        return True, "derby"
    return False, "not a big match"


def kits_for(home, away):
    """Home team wears home. Away team wears home unless the main colours clash, then away."""
    hk = home["kits"]["home"]["primary"]; ak = away["kits"]["home"]["primary"]
    clash = im.delta_e(hk, ak) < P["clash_delta_e"]
    away_kit = "away" if clash and "away" in away["kits"] else "home"
    return "home", away_kit, round(im.delta_e(hk, ak), 1)


def pick_players(club_slug, players):
    pool = [p for p in players if p["club"] == club_slug and p.get("available", True)]
    pool.sort(key=lambda p: p.get("priority", 99))
    return pool[:P["players_per_team"]]


def analyse(a):
    start = dt.date.fromisoformat(a.date) if a.date else dt.date.today() + dt.timedelta(days=a.days)
    matches = fetch(start.isoformat(), start.isoformat(), a.sample)
    clubs, players = all_clubs(), all_players()
    rows = []
    for m in matches:
        home, away = match_club(m["homeTeam"], clubs), match_club(m["awayTeam"], clubs)
        big, why = is_big(m, home, away)
        row = {"match_id": m.get("id"), "utc": m.get("utcDate"), "competition": m.get("competition", {}).get("name"),
               "stage": m.get("stage"), "home": m["homeTeam"].get("name"), "away": m["awayTeam"].get("name"),
               "home_club": home and home["slug"], "away_club": away and away["slug"], "big": big, "why": why}
        if big:
            hk, ak, de = kits_for(home, away)
            row.update({"kits": {"home": hk, "away": ak, "delta_e": de},
                        "players": {"home": [p["slug"] for p in pick_players(home["slug"], players)],
                                    "away": [p["slug"] for p in pick_players(away["slug"], players)]}})
        rows.append(row)
    return start, rows


def cmd_fixtures(a):
    start, rows = analyse(a)
    out({"date": start.isoformat(), "matches": rows})


def cmd_plan(a):
    import engine
    start, rows = analyse(a)
    opened, skipped = [], []
    for r in rows:
        if not r["big"]:
            continue
        slug = f"prematch-{r['home_club']}-vs-{r['away_club']}"
        rid = f"{today()}-{slug}"
        if (REQ / rid / "request.json").exists():
            skipped.append({"id": rid, "why": "already open"}); continue
        specs = [f"{p}:{r['kits']['home']}" for p in r["players"]["home"]] + [f"{p}:{r['kits']['away']}" for p in r["players"]["away"]]
        if len(r["players"]["home"]) == 0 or len(r["players"]["away"]) == 0:
            skipped.append({"id": rid, "why": "no available players in the archive for one of the clubs"}); continue
        text = f"Pre-match {r['home']} vs {r['away']} ({r['competition']}, {r['utc']}). Who wins? Poll graphic."
        with contextlib.redirect_stdout(io.StringIO()):  # keep plan's output a single JSON document
            engine.cmd_new(Namespace(slug=slug, text=text, player=specs, type="prematch", formats=None,
                                     match=json.dumps({k: r[k] for k in ("match_id", "utc", "competition", "stage", "home", "away", "kits")})))
        opened.append(rid)
    out({"date": start.isoformat(), "opened": opened, "skipped": skipped,
         "next": "for each opened request: ideas.md → prompts.json → lint → shots → select (+ bboxes) → identity → qc"})


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for name, f in (("fixtures", cmd_fixtures), ("plan", cmd_plan)):
        s = sub.add_parser(name); s.add_argument("--days", type=int, default=P["days_ahead"])
        s.add_argument("--date"); s.add_argument("--sample"); s.set_defaults(f=f)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
