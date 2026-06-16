#!/usr/bin/env python3
"""
fetch_openfootball.py — openfootball/football.json 公开赛事数据抓取

数据源: https://github.com/openfootball/football.json  (公共领域, GitHub raw)
适用: 离线赛事 backup,补冷门联赛(奥/比/葡/苏/土/希/荷)
      数据是已完成比赛的赛果, 不是赔率/xG

格式: {name, matches: [{round, date, time, team1, team2, score}]}

用法:
  python3 fetch_openfootball.py --list-leagues
  python3 fetch_openfootball.py --league en.1 --season 2025-26
  python3 fetch_openfootball.py --league en.1 --team Liverpool
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"

# League code mapping. Code format is {country}.{tier}
LEAGUES = {
    "en.1": "English Premier League",
    "en.2": "English Championship",
    "en.3": "English League One",
    "en.4": "English League Two",
    "de.1": "Deutsche Bundesliga",
    "de.2": "2. Bundesliga",
    "es.1": "Spanish Primera División (La Liga)",
    "es.2": "Spanish Segunda División",
    "it.1": "Italian Serie A",
    "it.2": "Italian Serie B",
    "fr.1": "French Ligue 1",
    "fr.2": "French Ligue 2",
    "at.1": "Austrian Bundesliga",
    "be.1": "Belgian Jupiler Pro League",
    "pt.1": "Portuguese Primeira Liga",
    "sco.1": "Scottish Premiership",
    "tr.1": "Turkish Süper Lig",
    "gr.1": "Greek Super League",
    "nl.1": "Dutch Eredivisie",
}


def http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "worldcup-betting-guide/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def list_seasons() -> list[str]:
    """List all season directories via GitHub API."""
    api_url = "https://api.github.com/repos/openfootball/football.json/contents/"
    req = urllib.request.Request(api_url, headers={"User-Agent": "worldcup-betting-guide/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = json.loads(resp.read())
    # Only season directories (start with digit)
    return sorted([it["name"] for it in items if it["type"] == "dir" and it["name"][0].isdigit()])


def list_leagues_for_season(season: str) -> list[str]:
    api_url = f"https://api.github.com/repos/openfootball/football.json/contents/{season}"
    req = urllib.request.Request(api_url, headers={"User-Agent": "worldcup-betting-guide/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = json.loads(resp.read())
    return sorted([it["name"] for it in items if it["name"].endswith(".json")])


def fetch_season_league(season: str, league: str) -> dict:
    # Auto-append .json if missing
    if not league.endswith(".json"):
        league = league + ".json"
    url = f"{BASE_URL}/{season}/{league}"
    return http_get(url)


def filter_matches(data: dict, *, team: str | None = None,
                   round_name: str | None = None, played_only: bool = False) -> list[dict]:
    matches = data.get("matches", [])
    if team:
        needle = team.lower()
        matches = [m for m in matches if needle in m.get("team1", "").lower()
                   or needle in m.get("team2", "").lower()]
    if round_name:
        matches = [m for m in matches if round_name.lower() in m.get("round", "").lower()]
    if played_only:
        # A match is played if score is non-empty (not [])
        matches = [m for m in matches if m.get("score") and m["score"] != []]
    return matches


def main():
    ap = argparse.ArgumentParser(description="openfootball 公开赛事 JSON")
    ap.add_argument("--list-leagues", action="store_true", help="列出已知 league 代码")
    ap.add_argument("--list-seasons", action="store_true", help="列出仓库所有赛季")
    ap.add_argument("--league", help="联赛代码(例如 en.1, es.1)")
    ap.add_argument("--season", default="2025-26", help="赛季(默认 2025-26)")
    ap.add_argument("--team", help="按球队过滤(子串匹配)")
    ap.add_argument("--round", help="按 round 过滤(例如 'Matchday 1')")
    ap.add_argument("--played-only", action="store_true", help="只显示已完赛")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if args.list_leagues:
        if args.json:
            print(json.dumps(LEAGUES, ensure_ascii=False, indent=2))
        else:
            print("📋 openfootball 已知联赛代码:")
            for code, name in LEAGUES.items():
                print(f"  {code:8s} → {name}")
        return

    if args.list_seasons:
        seasons = list_seasons()
        if args.json:
            print(json.dumps(seasons, indent=2))
        else:
            print(f"📅 openfootball 仓库赛季({len(seasons)} 个):")
            for s in seasons:
                print(f"  {s}")
        return

    if not args.league:
        ap.error("--league / --list-leagues / --list-seasons 三选一")

    try:
        data = fetch_season_league(args.season, args.league)
    except Exception as e:
        print(f"❌ 抓取失败: {e}", file=sys.stderr)
        print(f"   试 --list-seasons 看仓库有什么, --list-leagues 看代码", file=sys.stderr)
        sys.exit(1)

    matches = filter_matches(data, team=args.team, round_name=args.round, played_only=args.played_only)

    if args.json:
        print(json.dumps({
            "name": data.get("name"),
            "season": args.season,
            "league": args.league,
            "match_count": len(matches),
            "matches": matches,
        }, ensure_ascii=False, indent=2))
        return

    league_name = LEAGUES.get(args.league, args.league)
    print(f"📅 {data.get('name', league_name)} (赛季 {args.season})")
    if args.team:
        print(f"   过滤: team 包含 '{args.team}'")
    if args.round:
        print(f"   过滤: round 包含 '{args.round}'")
    if args.played_only:
        print(f"   过滤: 仅已完赛")
    print(f"   比赛数: {len(matches)}")
    print()
    print(f"{'轮次':20s} {'日期':10s} {'时间':5s} {'主队':30s} {'比分':>5s} {'客队':30s}")
    print("-" * 110)
    for m in matches:
        round_ = m.get("round", "")[:20]
        date = m.get("date", "")
        time = m.get("time", "")
        team1 = m.get("team1", "")[:30]
        team2 = m.get("team2", "")[:30]
        score = m.get("score", [])
        if score and score != []:
            if isinstance(score, dict) and "ft" in score:
                s = f"{score['ft'][0]}-{score['ft'][1]}"
            elif isinstance(score, list):
                s = f"{score[0]}-{score[1]}"
            else:
                s = "?"
        else:
            s = "v"
        print(f"{round_:20s} {date:10s} {time:5s} {team1:30s} {s:>5s} {team2:30s}")


if __name__ == "__main__":
    main()
