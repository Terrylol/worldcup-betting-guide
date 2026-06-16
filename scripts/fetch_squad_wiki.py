#!/usr/bin/env python3
"""
fetch_squad_wiki.py — Wikipedia 2026 FIFA World Cup 国家队大名单抓取

数据源: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads
        (MediaWiki API, 无 key, 公开)
适用: 补 POWER-6 模型「阵容博弈」维度 (15%)
      配合 fetch_xg.py 用: 拿到大名单 → 每个球员反查俱乐部 xG → 加权

用法:
  python3 fetch_squad_wiki.py --list-teams
  python3 fetch_squad_wiki.py --team France
  python3 fetch_squad_wiki.py --team "Saudi Arabia" --json
  python3 fetch_squad_wiki.py --all --json
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

API_URL = "https://en.wikipedia.org/w/api.php"
PAGE_TITLE = "2026 FIFA World Cup squads"
USER_AGENT = "worldcup-betting-guide/1.0 (https://github.com/Terrylol/worldcup-betting-guide)"


def http_get(params: dict) -> dict:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        import gzip
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def fetch_wikitext() -> str:
    """Fetch the full wikitext of the squads page."""
    d = http_get({
        "action": "parse",
        "page": PAGE_TITLE,
        "format": "json",
        "prop": "wikitext",
    })
    if "error" in d:
        raise RuntimeError(f"Wikipedia error: {d['error']}")
    return d["parse"]["wikitext"]["*"]


def list_teams(wikitext: str) -> list[str]:
    """Extract all country names from section headers."""
    return re.findall(r"=== ?([A-Za-z][\w\s\-\'\.\(\)]+) ?===", wikitext)


def find_balanced_brace(text: str, start_marker: str, open_ch: str = "{", close_ch: str = "}") -> str | None:
    """Find `start_marker` in text, then return text until balanced `{{ }}` closes.
    Handles nested braces (e.g. age={{birth date and age2|...}})."""
    i = text.find(start_marker)
    if i < 0:
        return None
    j = i + len(start_marker)
    depth = 1
    while j < len(text) and depth > 0:
        # Look for next open or close
        o = text.find(open_ch + open_ch, j)
        c = text.find(close_ch + close_ch, j)
        if c < 0:
            return None
        if o < 0 or o > c:
            j = c + 2
            depth -= 1
        else:
            j = o + 2
            depth += 1
    return text[i:j]


def extract_squad(wikitext: str, team: str) -> dict:
    """Extract one team's squad from wikitext.
    Strategy: split section by '{{nat fs g player' tokens, then for each
    block extract top-level key=value pairs ignoring nested {{...}}."""
    pattern = rf"=== ?{re.escape(team)} ?===(.*?)(?==== ?[A-Z][\w\s\-\'\.\(\)]+ ?===|$)"
    m = re.search(pattern, wikitext, re.DOTALL)
    if not m:
        return {"team": team, "found": False}

    section = m.group(1)

    # Coach
    coach_match = re.search(r"Coach: ?\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", section)
    coach = coach_match.group(1) if coach_match else None

    # Strip nested {{birth date and age2|...}} first (the only nested {{...}} in player records)
    # The data is REF_YEAR|REF_MONTH|REF_DAY|BIRTH_YEAR|BIRTH_MONTH|BIRTH_DAY
    # We only need the birth date (last 3 values)
    date_pattern = re.compile(
        r"\{\{birth date and age2\|\d+\|\d+\|\d+\|(\d+)\|(\d+)\|(\d+)\}\}"
    )
    birth_dates = {}  # position in section -> ISO date string
    for dm in date_pattern.finditer(section):
        iso = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        birth_dates[dm.start()] = iso

    # Replace ALL the nested braces (not just the age= prefix) for clean regex parsing
    # We need the position info to be relative to the cleaned section though.
    # So: collect positions in original, then replace and remap.

    # Alternative: keep a copy of section with markers
    section_flat = section
    for dm in list(date_pattern.finditer(section_flat)):
        # Replace this specific occurrence
        pass  # We'll handle birth_date in the player loop instead

    # Find each {{nat fs g player|...}} block. We need to handle nested {{...}} in body
    # Use balanced braces
    players = []
    pos = 0
    while True:
        start = section.find("{{nat fs g player", pos)
        if start < 0:
            break
        # Find balanced close
        j = start + len("{{nat fs g player")
        depth = 1
        while j < len(section) and depth > 0:
            o = section.find("{{", j)
            c = section.find("}}", j)
            if c < 0:
                break
            if o < 0 or o > c:
                j = c + 2
                depth -= 1
            else:
                j = o + 2
                depth += 1
        block = section[start:j]

        # Parse body manually
        # First, find birth date in block
        bd_m = date_pattern.search(block)
        bd_iso = None
        if bd_m:
            bd_iso = f"{bd_m.group(1)}-{int(bd_m.group(2)):02d}-{int(bd_m.group(3)):02d}"
        # Now strip the nested {{birth date...}} from body for cleaner parsing
        body_clean = date_pattern.sub("age=BIRTHDATE", block[len("{{nat fs g player"):-2].strip())
        if body_clean.endswith("|"):
            body_clean = body_clean[:-1]

        # Tokenize: split on | but respect [[...]] boundaries
        attrs = {}
        parts = []
        buf = ""
        in_link = False
        for ch in body_clean:
            if ch == "[" and not in_link:
                in_link = True
                buf += ch
            elif ch == "]" and in_link:
                in_link = False
                buf += ch
            elif ch == "|" and not in_link:
                parts.append(buf)
                buf = ""
            else:
                buf += ch
        if buf:
            parts.append(buf)

        for part in parts:
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Strip wiki link [[X|Y]] -> Y (or X if no |)
            if val.startswith("[[") and val.endswith("]]"):
                link = val[2:-2]
                if "|" in link:
                    val = link.split("|", 1)[1]
                else:
                    val = link
            attrs[key] = val

        if "name" in attrs:
            players.append({
                "no": int(attrs["no"]) if attrs.get("no", "").isdigit() else None,
                "pos": attrs.get("pos"),
                "name": attrs.get("name"),
                "caps": int(attrs["caps"]) if attrs.get("caps", "").isdigit() else 0,
                "goals": int(attrs["goals"]) if attrs.get("goals", "").isdigit() else 0,
                "club": attrs.get("club"),
                "clubnat": attrs.get("clubnat"),
                "birth_date": bd_iso,
            })

        pos = j

    # Position distribution
    pos_dist = {}
    for p in players:
        pos_dist[p["pos"]] = pos_dist.get(p["pos"], 0) + 1

    # Club league distribution (use clubnat to map)
    league_dist = {}
    nat_to_league = {
        "ENG": "EPL", "ESP": "La Liga", "GER": "Bundesliga", "ITA": "Serie A",
        "FRA": "Ligue 1", "POR": "Other Europe", "NED": "Other Europe",
        "BEL": "Other Europe", "BRA": "Other", "ARG": "Other",
    }
    for p in players:
        cn = p.get("clubnat", "")
        league = nat_to_league.get(cn, "Other")
        league_dist[league] = league_dist.get(league, 0) + 1

    return {
        "team": team,
        "found": True,
        "coach": coach,
        "player_count": len(players),
        "position_distribution": pos_dist,
        "league_distribution": league_dist,
        "players": players,
    }


def main():
    ap = argparse.ArgumentParser(description="Wikipedia 2026 FIFA World Cup 大名单")
    ap.add_argument("--team", help="国家队名(精确匹配 section title)")
    ap.add_argument("--list-teams", action="store_true", help="列出所有参赛队")
    ap.add_argument("--all", action="store_true", help="抓取所有 48+ 队")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if args.list_teams:
        wt = fetch_wikitext()
        teams = list_teams(wt)
        if args.json:
            print(json.dumps(teams, ensure_ascii=False, indent=2))
        else:
            print(f"📋 2026 FIFA World Cup 参赛队 ({len(teams)} 支):")
            for i, t in enumerate(teams, 1):
                print(f"  {i:2d}. {t}")
        return

    if args.all:
        wt = fetch_wikitext()
        teams = list_teams(wt)
        all_squads = {}
        for t in teams:
            sq = extract_squad(wt, t)
            all_squads[t] = {
                "coach": sq.get("coach"),
                "player_count": sq.get("player_count"),
                "position_distribution": sq.get("position_distribution"),
                "league_distribution": sq.get("league_distribution"),
            }
        if args.json:
            print(json.dumps(all_squads, ensure_ascii=False, indent=2))
        else:
            print(f"📋 2026 FIFA World Cup 所有大名单 ({len(teams)} 支):")
            for t, sq in all_squads.items():
                if sq.get("player_count"):
                    pos = sq["position_distribution"]
                    leagues = sq["league_distribution"]
                    print(f"  {t:30s} {sq['player_count']:2d}人  GK={pos.get('GK',0):2d} DF={pos.get('DF',0):2d} MF={pos.get('MF',0):2d} FW={pos.get('FW',0):2d}  "
                          f"联赛:{', '.join(f'{k}:{v}' for k,v in leagues.items())}")
                else:
                    print(f"  {t}: ❌ squad not found")
        return

    if not args.team:
        ap.error("--team / --list-teams / --all 三选一")

    wt = fetch_wikitext()
    sq = extract_squad(wt, args.team)

    if not sq.get("found"):
        # 尝试小写
        teams = list_teams(wt)
        suggestions = [t for t in teams if args.team.lower() in t.lower()][:5]
        if args.json:
            print(json.dumps({"team": args.team, "found": False, "suggestions": suggestions}, ensure_ascii=False, indent=2))
        else:
            print(f"❌ 找不到 '{args.team}'")
            if suggestions:
                print(f"   提示(相似): {', '.join(suggestions)}")
        sys.exit(1)

    if args.json:
        print(json.dumps(sq, ensure_ascii=False, indent=2))
        return

    # Pretty print
    print(f"🏳️  {args.team}  教练: {sq.get('coach', '?')}")
    print(f"   球员数: {sq['player_count']}")
    print(f"   位置分布: {sq['position_distribution']}")
    print(f"   联赛分布: {sq['league_distribution']}")
    print()
    print(f"{'号':>3s} {'位置':5s} {'球员':30s} {'年龄':>5s} {'出场':>4s} {'进球':>4s} {'俱乐部':25s} {'联赛':3s}")
    print("-" * 95)
    for p in sq["players"]:
        no = p.get("no", "")
        pos = p.get("pos", "")
        name = (p.get("name", "") or "")[:30]
        # 计算年龄(基于 2026-06-11 世界杯开赛日)
        age = ""
        if p.get("birth_date"):
            from datetime import date
            try:
                d = date.fromisoformat(p["birth_date"])
                today = date(2026, 6, 11)
                a = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
                age = f"{a}"
            except Exception:
                pass
        caps = p.get("caps", 0)
        goals = p.get("goals", 0)
        club = (p.get("club", "") or "")[:25]
        nat = p.get("clubnat", "")
        print(f"{no:>3} {pos:5s} {name:30s} {age:>5s} {caps:>4d} {goals:>4d} {club:25s} {nat:3s}")


if __name__ == "__main__":
    main()
