#!/usr/bin/env python3
"""
世界杯阵容数据抓取脚本

数据源：
1. 懂球帝 API（主数据源）— 球员阵容、球队信息、身价、排名
2. 500.com（补充）— 竞彩赔率关联的球队ID映射

用法：
  python3 fetch_squad.py                           # 抓取所有世界杯参赛队阵容
  python3 fetch_squad.py --team 西班牙              # 抓取指定球队阵容
  python3 fetch_squad.py --team-id 1869             # 按懂球帝球队ID抓取
  python3 fetch_squad.py --list-teams               # 列出所有世界杯参赛队及ID
  python3 fetch_squad.py --group H                  # 抓取H组所有球队阵容
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# ── 懂球帝 API 配置 ──
DQD_BASE = "https://www.dongqiudi.com"
DQD_SPORT_BASE = "https://sport-data.dongqiudi.com"
DQD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.dongqiudi.com/",
    "Origin": "https://www.dongqiudi.com",
    "Accept": "application/json",
}
DQD_PARAMS = "app=dqd&version=853&platform=ios&language=zh-cn"

# ── 世界杯 competition_id (懂球帝) ──
WORLD_CUP_CID = 61

# ── 补充球队ID：通过standings API动态获取 ──
_extra_teams_cache = None

def get_teams_from_standings_api():
    """从懂球帝standings API获取所有世界杯球队（含长格式ID）"""
    global _extra_teams_cache
    if _extra_teams_cache is not None:
        return _extra_teams_cache
    
    _extra_teams_cache = {}
    url = f"{DQD_SPORT_BASE}/soccer/biz/data/standing?competition_id={WORLD_CUP_CID}&{DQD_PARAMS}"
    raw = http_get(url)
    try:
        data = json.loads(raw)
        # Recursively find all team entries
        raw_str = json.dumps(data, ensure_ascii=False)
        import re as _re
        teams = _re.findall(r'"team_id":\s*"(\d+)"[^}]*"team_name":\s*"([^"]+)"', raw_str)
        for tid, tname in teams:
            # Convert long ID (50001869) to short ID (1869)
            short_id = str(int(tid.replace("5000", ""))) if tid.startswith("5000") else tid
            _extra_teams_cache[tname] = short_id
    except:
        pass
    return _extra_teams_cache


def http_get(url, timeout=15):
    """简单的 HTTP GET，带重试"""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=DQD_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                return json.dumps({"error": str(e)})


def get_world_cup_teams():
    """从懂球帝获取世界杯所有参赛队及分组"""
    url = f"{DQD_SPORT_BASE}/soccer/biz/data/standing?competition_id={WORLD_CUP_CID}&{DQD_PARAMS}"
    raw = http_get(url)
    data = json.loads(raw)

    teams = []
    content = data.get("content", {})

    # 解析分组数据
    rounds = content.get("rounds", [])
    for round_item in rounds:
        round_content = round_item.get("content", {})
        round_name = round_content.get("name", "")

        # 小组赛阶段有 groups
        groups = round_content.get("groups", [])
        if groups:
            for group in groups:
                group_name = group.get("name", round_name)
                for team in group.get("data", []):
                    # 从 standings 表格解析
                    pass

    # 备用方案：从 SSR 页面获取
    if not teams:
        teams = get_world_cup_teams_from_ssr()

    return teams


def get_world_cup_teams_from_ssr():
    """从懂球帝世界杯数据页的 SSR 数据获取球队列表"""
    url = f"{DQD_BASE}/data?cid={WORLD_CUP_CID}"
    raw = http_get(url)

    teams = []
    # 提取 __NUXT__ return block
    match = re.search(r'return\s*\{(.+?)\}\s*\}\s*\(', raw, re.DOTALL)
    if not match:
        return teams

    block = match.group(1)

    # 方法1：找到 standingsGroups 区域，逐组提取
    # 格式：name:"X组",teams:[{id:"xxx",rank:...,name:"队名"...},...]
    sg_idx = block.find("standingsGroups")
    if sg_idx >= 0:
        # 从 standingsGroups 开始截取足够长的内容
        sg_block = block[sg_idx:sg_idx + 50000]

        # 用非贪婪方式找每个组的 teams 数组
        # 先找所有组名
        group_pattern = r'name:"([A-Z]组)"'
        group_positions = [(m.start(), m.group(1)) for m in re.finditer(group_pattern, sg_block)]

        for i, (pos, gname) in enumerate(group_positions):
            # 找到 teams:[ 的位置
            teams_start = sg_block.find("teams:[", pos)
            if teams_start < 0 or (i + 1 < len(group_positions) and teams_start > group_positions[i+1][0]):
                continue

            # 找到匹配的 ] 结束位置
            bracket_count = 0
            teams_end = -1
            for j in range(teams_start + len("teams:"), min(teams_start + 3000, len(sg_block))):
                if sg_block[j] == "[":
                    bracket_count += 1
                elif sg_block[j] == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        teams_end = j + 1
                        break

            if teams_end > 0:
                teams_str = sg_block[teams_start:teams_end]
                team_list = re.findall(r'id:"(\d+)",rank:[^,]*,name:"([^"]+)"', teams_str)
                for tid, tname in team_list:
                    teams.append({
                        "team_id": tid,
                        "team_name": tname.strip(),
                        "group": gname,
                    })

    # 方法2 备用：在整个 block 中搜索所有 id/name 对（如果方法1结果太少）
    if len(teams) < 48:  # 2026世界杯有48队
        # 直接在 standingsGroups 附近搜索所有球队
        if sg_idx >= 0:
            sg_block = block[sg_idx:sg_idx + 50000]
            all_team_ids = re.findall(r'id:"(\d+)",rank:[^,]*,name:"([^"]+)"', sg_block)
            existing_ids = {t["team_id"] for t in teams}
            for tid, tname in all_team_ids:
                if tid not in existing_ids:
                    teams.append({
                        "team_id": tid,
                        "team_name": tname.strip(),
                        "group": "未知",
                    })

    return teams


def get_team_info(team_id):
    """获取球队基本信息（含排名、身价）"""
    url = f"{DQD_SPORT_BASE}/soccer/biz/dqd/team/sample/{team_id}?{DQD_PARAMS}"
    raw = http_get(url)
    data = json.loads(raw)

    if "error" in data:
        return None

    # 提取关键信息
    result = {
        "team_id": data.get("team_id", ""),
        "team_name": data.get("team_name", ""),
        "english_name": data.get("team_en_name", ""),
        "country": data.get("country", ""),
        "founded": data.get("founded", ""),
        "venue": data.get("venue_name", ""),
        "capacity": data.get("venue_capacity", ""),
        "rank_info": data.get("rank", ""),  # 如 "世界排名第2  总身价12.2亿欧"
    }

    # 解析排名和身价
    rank_str = data.get("rank", "")
    rank_match = re.search(r"世界排名第(\d+)", rank_str)
    value_match = re.search(r"总身价([\d.]+亿欧|[\d.]+万欧)", rank_str)
    if rank_match:
        result["fifa_rank"] = int(rank_match.group(1))
    if value_match:
        result["market_value"] = value_match.group(1)

    return result


def get_team_squad(team_id):
    """获取球队完整阵容"""
    url = f"{DQD_SPORT_BASE}/soccer/biz/dqd/v1/team/member_v2/{team_id}?{DQD_PARAMS}"
    raw = http_get(url)
    data = json.loads(raw)

    if "error" in data:
        return None

    squad = {
        "team_id": team_id,
        "players": [],
        "summary": {
            "goalkeeper": 0,
            "defender": 0,
            "midfielder": 0,
            "attacker": 0,
            "total": 0,
            "top5_league_players": 0,
            "top5_leagues": ["英超", "西甲", "德甲", "意甲", "法甲",
                             "阿森纳", "曼城", "利物浦", "切尔西", "曼联", "热刺",
                             "巴塞罗那", "皇家马德里", "马德里竞技",
                             "拜仁", "多特蒙德", "勒沃库森",
                             "国际米兰", "尤文图斯", "AC米兰", "那不勒斯",
                             "巴黎圣日耳曼"],
        },
    }

    # 五大联赛关键词（用于识别球员是否效力于五大联赛）
    top5_keywords = squad["summary"]["top5_leagues"]

    for group in data.get("data", {}).get("list", []):
        position = group.get("type", "unknown")
        position_cn = {
            "goalkeeper": "门将",
            "defender": "后卫",
            "midfielder": "中场",
            "attacker": "前锋",
            "coach": "教练组",
        }.get(position, position)

        for p in group.get("data", []):
            if position == "coach":
                continue  # 跳过教练组

            club = p.get("nationality_name", "")  # 实际是所属俱乐部
            # 注意：懂球帝 member_v2 的 nationality_name 实际存的是俱乐部名

            is_top5 = any(kw in club for kw in top5_keywords)

            player = {
                "name": p.get("person_name", ""),
                "age": p.get("age", "").replace("岁", ""),
                "club": club,
                "position": position_cn,
                "position_en": position,
                "is_top5_league": is_top5,
            }
            squad["players"].append(player)
            squad["summary"][position] = squad["summary"].get(position, 0) + 1
            squad["summary"]["total"] += 1
            if is_top5:
                squad["summary"]["top5_league_players"] += 1

    return squad


def format_squad_output(team_name, info, squad):
    """格式化输出阵容信息"""
    lines = []
    lines.append(f"{'='*50}")
    lines.append(f"  ⚽ {team_name} 阵容信息")
    lines.append(f"{'='*50}")

    if info:
        lines.append(f"FIFA排名: 第{info.get('fifa_rank', '?')}位")
        lines.append(f"总身价: {info.get('market_value', '未知')}")
        lines.append(f"成立: {info.get('founded', '?')}年")
        lines.append(f"主场: {info.get('venue', '?')}")

    if squad:
        summary = squad["summary"]
        lines.append(f"\n阵容人数: {summary['total']}人")
        lines.append(f"  门将: {summary.get('goalkeeper', 0)}人")
        lines.append(f"  后卫: {summary.get('defender', 0)}人")
        lines.append(f"  中场: {summary.get('midfielder', 0)}人")
        lines.append(f"  前锋: {summary.get('attacker', 0)}人")
        lines.append(f"  五大联赛球员: {summary.get('top5_league_players', 0)}人")

        lines.append(f"\n详细名单:")
        for pos in ["门将", "后卫", "中场", "前锋"]:
            pos_players = [p for p in squad["players"] if p["position"] == pos]
            if pos_players:
                lines.append(f"\n  【{pos}】({len(pos_players)}人)")
                for p in pos_players:
                    top5_mark = "★" if p["is_top5_league"] else ""
                    lines.append(f"    {p['name']} ({p['age']}岁) {p['club']} {top5_mark}")

    lines.append(f"{'='*50}")
    return "\n".join(lines)



def get_team_id_by_name(team_name):
    """通过球队名称模糊匹配懂球帝球队ID（SSR → standings API → 失败）"""
    # 1. 从SSR获取
    all_teams = get_world_cup_teams_from_ssr()
    for t in all_teams:
        if team_name in t["team_name"] or t["team_name"] in team_name:
            return t["team_id"], t["team_name"], t["group"]
    # 2. 从standings API获取（覆盖SSR未收录的球队）
    extra = get_teams_from_standings_api()
    for name, tid in extra.items():
        if team_name in name or name in team_name:
            return tid, name, "?"
    return None, team_name, "?"

def batch_fetch_by_names(team_names, output_json=False):
    """根据球队名称列表批量获取阵容"""
    results = []
    for name in team_names:
        tid, full_name, group = get_team_id_by_name(name)
        if tid:
            info = get_team_info(tid)
            squad = get_team_squad(tid)
            results.append({
                "team_id": tid,
                "team_name": full_name,
                "group": group,
                "info": info,
                "squad": squad,
            })
            time.sleep(0.3)
        else:
            results.append({
                "team_id": None,
                "team_name": name,
                "group": "?",
                "info": None,
                "squad": None,
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="世界杯阵容数据抓取")
    parser.add_argument("--team", help="球队名称（如：西班牙）")
    parser.add_argument("--team-id", help="懂球帝球队ID（如：1869）")
    parser.add_argument("--list-teams", action="store_true", help="列出所有世界杯参赛队")
    parser.add_argument("--group", help="抓取指定小组所有球队阵容（如：H）")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--names", nargs="+", help="按球队名称批量查询（模糊匹配，如: --names 西班牙 佛得角）")
    args = parser.parse_args()

    # 列出所有参赛队
    if args.list_teams:
        teams = get_world_cup_teams_from_ssr()
        if args.json:
            print(json.dumps(teams, ensure_ascii=False, indent=2))
        else:
            current_group = ""
            for t in teams:
                if t["group"] != current_group:
                    current_group = t["group"]
                    print(f"\n=== {current_group} ===")
                print(f"  {t['team_name']} (ID: {t['team_id']})")
        return

    # 确定要查询的球队
    team_ids = []

    if args.team_id:
        team_ids = [(args.team_id, "")]
    elif args.team:
        # 搜索球队ID
        all_teams = get_world_cup_teams_from_ssr()
        for t in all_teams:
            if args.team in t["team_name"]:
                team_ids.append((t["team_id"], t["team_name"]))
        if not team_ids:
            print(f"未找到球队：{args.team}")
            print("可用球队列表：")
            for t in all_teams:
                print(f"  {t['team_name']} (ID: {t['team_id']})")
            return
    elif args.group:
        all_teams = get_world_cup_teams_from_ssr()
        for t in all_teams:
            if t["group"] == f"{args.group}组":
                team_ids.append((t["team_id"], t["team_name"]))
        if not team_ids:
            print(f"未找到小组：{args.group}组")
            return
    elif args.names:
        results = batch_fetch_by_names(args.names)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for r in results:
                info = r.get("info")
                squad = r.get("squad")
                name = r.get("team_name", "?")
                print(format_squad_output(name, info, squad))
        return
    else:
        # 默认：列出所有参赛队
        teams = get_world_cup_teams_from_ssr()
        print("请指定 --team、--team-id 或 --group 参数")
        print(f"当前世界杯共 {len(teams)} 支参赛队，使用 --list-teams 查看完整列表")
        return

    # 获取阵容数据
    results = []
    for tid, tname in team_ids:
        info = get_team_info(tid)
        squad = get_team_squad(tid)
        name = tname or (info.get("team_name", "") if info else f"ID:{tid}")

        if args.json:
            results.append({
                "team_id": tid,
                "team_name": name,
                "info": info,
                "squad": squad,
            })
        else:
            print(format_squad_output(name, info, squad))

        # 避免请求过快
        if len(team_ids) > 1:
            time.sleep(0.3)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
