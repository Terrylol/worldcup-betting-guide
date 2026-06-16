#!/usr/bin/env python3
"""
世界杯竞彩分析报告生成器

JSON数据 → HTML网页 + 文本报告，同源同构。

用法：
  python3 generate_report.py --data data.json --format both -o report
  python3 generate_report.py --demo --format html -o preview
  python3 generate_report.py --schema
  cat data.json | python3 generate_report.py --format text
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "..", "references", "report_template.html")

DATA_SCHEMA = """
{
  "date": "2026-06-16",
  "play_type": "让球胜平负",
  "parlay_num": 4,
  "match_count": 4,
  "matches": [
    {
      "id": "周一013",
      "time": "00:00",
      "home": "西班牙",
      "away": "佛得角",
      "handicap": -2,
      "handicap_display": "主让2球",
      "sp": {"胜": 1.46, "平": 4.70, "负": 4.32},
      "tag": "碾压局",
      "dims": [
        {"name": "战力鸿沟", "weight": "×20%", "desc": "...", "score": 9}
      ],
      "recommendation": "让球胜",
      "rec_sp": 1.46,
      "total_score": 67,
      "risk": ""
    }
  ],
  "parlays": [
    {
      "type": "safe",
      "icon": "🎯",
      "title": "稳妥方案",
      "sp": 22.47,
      "items": [
        {"match": "西班牙 vs 佛得角", "direction": "让球胜", "sp": 1.46}
      ],
      "logic": "...",
      "stars": "⭐⭐⭐⭐"
    }
  ]
}

必填字段：
- date, play_type, parlay_num, match_count
- matches[]: id, time, home, away, handicap, sp{胜平负}, tag, dims[]{name,weight,desc,score}, recommendation, rec_sp, total_score
- parlays[]: type(safe/value/dark), icon, title, sp, items[]{match,direction,sp}, logic, stars

可选字段：
- matches[].handicap_display — 自动生成，也可手动指定
- matches[].risk — 风险提示，为空则不显示
"""


# ── 工具函数 ──

def score_class(score):
    return "score-high" if score >= 8 else ("score-mid" if score >= 5 else "score-low")

def tag_class(tag):
    return {"碾压局": "tag-crush", "压制局": "tag-suppress",
            "优势局": "tag-advantage", "胶着局": "tag-close",
            "均势局": "tag-even"}.get(tag, "tag-close")

def handicap_display(hc):
    if hc < 0: return f"主让{abs(hc)}球"
    elif hc > 0: return f"客让{hc}球"
    else: return "平手"

def hc_html_class(hc):
    return "negative" if hc < 0 else "positive"


def validate_data(data):
    errors = []
    for key in ["date", "play_type", "parlay_num", "match_count", "matches", "parlays"]:
        if key not in data:
            errors.append(f"missing top-level field: {key}")
    if errors:
        return errors
    for i, m in enumerate(data["matches"]):
        prefix = f"matches[{i}]"
        for key in ["id", "time", "home", "away", "handicap", "sp", "tag", "dims", "recommendation", "rec_sp", "total_score"]:
            if key not in m:
                errors.append(f"{prefix} missing: {key}")
        if "sp" in m:
            for k in ["\u80dc", "\u5e73", "\u8d1f"]:
                if k not in m["sp"]:
                    errors.append(f"{prefix}.sp missing: {k}")
        if "dims" in m:
            for j, d in enumerate(m["dims"]):
                for key in ["name", "weight", "desc", "score"]:
                    if key not in d:
                        errors.append(f"{prefix}.dims[{j}] missing: {key}")
    for i, p in enumerate(data["parlays"]):
        prefix = f"parlays[{i}]"
        for key in ["type", "icon", "title", "sp", "items", "logic", "stars"]:
            if key not in p:
                errors.append(f"{prefix} missing: {key}")
        if p.get("type") not in ("safe", "value", "dark"):
            errors.append(f"{prefix}.type must be safe/value/dark")
        if "items" in p:
            for j, it in enumerate(p["items"]):
                for key in ["match", "direction", "sp"]:
                    if key not in it:
                        errors.append(f"{prefix}.items[{j}] missing: {key}")
    return errors


# ── HTML 渲染 ──

def render_match_table(matches):
    rows = []
    for m in matches:
        hc = m.get("handicap", 0)
        hc_text = m.get("handicap_display") or handicap_display(hc)
        sp = m["sp"]
        sp_str = f'{sp["胜"]:.2f} / {sp["平"]:.2f} / {sp["负"]:.2f}'
        rows.append(
            f'<tr>\n'
            f'  <td>{m["id"]}</td>\n'
            f'  <td>{m["time"]}</td>\n'
            f'  <td><span class="team-name">{m["home"]}</span> '
            f'<span class="vs">vs</span> '
            f'<span class="team-name">{m["away"]}</span></td>\n'
            f'  <td><span class="handicap {hc_html_class(hc)}">{hc_text}</span></td>\n'
            f'  <td><span class="sp-value">{sp_str}</span></td>\n'
            f'</tr>')
    return "\n".join(rows)

def _render_handicap_dim(d):
    """盘口密码维度：独立渲染，带子块高亮"""
    desc = d["desc"]
    # Parse 【凯利】【概率】【亚盘】【返还率】 blocks
    blocks = ""
    sections = desc.split("【")
    for s in sections[1:]:  # skip before first 【
        if "】" not in s:
            continue
        title_end = s.index("】")
        title = s[:title_end]
        body = s[title_end+1:].strip()
        # Clean up trailing space before next 【
        if body.endswith(" "):
            body = body.rstrip()
        # Highlight signals in body
        body = body.replace("✅", '<span class="signal-up">✅</span>')
        body = body.replace("⚠️", '<span class="signal-down">⚠️</span>')
        body = body.replace("→", '<span class="signal-warn">→</span>')
        blocks += f'<div class="hc-block"><div class="hc-block-title">{title}</div>{body}</div>\n'
    
    # Any text before first 【
    preamble = sections[0].strip() if sections[0].strip() else ""
    
    return (f'<div class="dim-row is-handicap">\n'
            f'  <div class="dim-header">\n'
            f'    <span class="dim-label">{d["name"]}<span class="weight">{d["weight"]}</span></span>\n'
            f'    <span class="dim-score {score_class(d["score"])}">{d["score"]}/10</span>\n'
            f'  </div>\n'
            f'  <div class="dim-content">{preamble}</div>\n'
            f'  {blocks}'
            f'</div>\n')


def render_match_cards(matches):
    cards = []
    for m in matches:
        dims = ""
        for d in m["dims"]:
            if d["name"] == "盘口密码":
                dims += _render_handicap_dim(d)
            else:
                dims += (f'<div class="dim-row">\n'
                         f'  <div class="dim-header">\n'
                         f'    <span class="dim-label">{d["name"]}<span class="weight">{d["weight"]}</span></span>\n'
                         f'    <span class="dim-score {score_class(d["score"])}">{d["score"]}/10</span>\n'
                         f'  </div>\n'
                         f'  <div class="dim-content">{d["desc"]}</div>\n'
                         f'</div>\n')
        risk = f'<div class="risk-note">{m["risk"]}</div>' if m.get("risk") else ""
        cards.append(
            f'<div class="match-card">\n'
            f'  <div class="match-card-header">\n'
            f'    <span class="match-label">{m["id"]} {m["home"]} vs {m["away"]}</span>\n'
            f'    <span class="match-tag {tag_class(m["tag"])}">{m["tag"]}</span>\n'
            f'  </div>\n'
            f'  <div class="match-card-body">\n{dims}  </div>\n'
            f'  <div class="match-card-footer">\n'
            f'    <div>\n'
            f'      {risk}\n'
            f'    </div>\n'
            f'    <div class="total-score">\n'
            f'      <span class="score-num">{m["total_score"]}</span><span class="score-max">/100</span>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'</div>')
    return "\n\n".join(cards)

def render_parlay_cards(parlays):
    cards = []
    for p in parlays:
        items = ""
        for it in p["items"]:
            items += (f'<div class="parlay-item">\n'
                      f'  <span class="item-match">{it["match"]}</span>\n'
                      f'  <span class="item-dir">{it["direction"]}</span>\n'
                      f'  <span class="item-sp">{it["sp"]:.2f}</span>\n'
                      f'</div>\n')
        cards.append(
            f'<div class="parlay-card parlay-{p["type"]}">\n'
            f'  <div class="parlay-header">\n'
            f'    <span class="parlay-title">{p["icon"]} {p["title"]}</span>\n'
            f'    <span class="parlay-sp">{p["sp"]:.2f} <small>串关SP</small></span>\n'
            f'  </div>\n'
            f'  <div class="parlay-items">\n{items}  </div>\n'
            f'  <div class="parlay-logic">{p["logic"]}</div>\n'
            f'  <div class="confidence">置信度：<span class="stars">{p["stars"]}</span></div>\n'
            f'</div>')
    return "\n\n".join(cards)

def generate_html(data, template_path=TEMPLATE_PATH):
    errors = validate_data(data)
    if errors:
        print("Data validation failed:")
        for e in errors: print(f"  - {e}")
        sys.exit(1)
    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    tpl = tpl.replace("{{date}}", data["date"])
    tpl = tpl.replace("{{handicap_header}}", "让球" if data["play_type"] == "让球胜平负" else "实力差")
    tpl = tpl.replace("{{play_type}}", data["play_type"])
    tpl = tpl.replace("{{parlay_num}}", str(data["parlay_num"]))
    tpl = tpl.replace("{{match_count}}", str(data["match_count"]))
    tpl = tpl.replace("{{match_table_rows}}", render_match_table(data["matches"]))
    tpl = tpl.replace("{{match_cards}}", render_match_cards(data["matches"]))
    tpl = tpl.replace("{{parlay_cards}}", render_parlay_cards(data["parlays"]))
    return tpl


# ── 文本渲染 ──

def generate_text(data):
    errors = validate_data(data)
    if errors:
        print("Data validation failed:")
        for e in errors: print(f"  - {e}")
        sys.exit(1)
    lines = []
    bar = "═" * 55
    lines.append(bar)
    lines.append(f"  ⚽ 世界杯竞彩【{data['play_type']}】{data['parlay_num']}串1分析报告")
    lines.append(f"  📅 {data['date']} | 玩法：{data['play_type']} | 赛事数：{data['match_count']}场")
    lines.append(bar)

    lines.append("\n【赛事一览】")
    for m in data["matches"]:
        hc = m.get("handicap", 0)
        hc_text = m.get("handicap_display") or handicap_display(hc)
        sp = m["sp"]
        sp_str = f'{sp["胜"]:.2f}/{sp["平"]:.2f}/{sp["负"]:.2f}'
        lines.append(f"  {m['id']} {m['time']} {m['home']} vs {m['away']} | {hc_text} | SP {sp_str}")

    lines.append("\n【POWER-6 六维分析】")
    for m in data["matches"]:
        hc = m.get("handicap", 0)
        hc_text = m.get("handicap_display") or handicap_display(hc)
        lines.append(f"\n▶ {m['id']} {m['home']} vs {m['away']} — {m['tag']}")
        lines.append(f"  让球：{hc_text}")
        for d in m["dims"]:
            lines.append(f"  ◆ {d['name']}（{d['weight']}）[评分: {d['score']}/10]")
            lines.append(f"    {d['desc']}")
        lines.append(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"  加权总分：{m['total_score']}/100 → 推荐方向：{m['recommendation']}（SP: {m['rec_sp']:.2f}）")
        if m.get("risk"):
            lines.append(f"  {m['risk']}")

    lines.append(f"\n{bar}")
    lines.append(f"【{data['parlay_num']}串1方案推荐】")
    for p in data["parlays"]:
        lines.append(f"\n{p['icon']} {p['title']}")
        items_str = " × ".join(f"{it['match']} {it['direction']}" for it in p["items"])
        lines.append(f"  {items_str}")
        lines.append(f"  串关SP：{p['sp']:.2f}")
        lines.append(f"  置信度：{p['stars']}")
        lines.append(f"  逻辑：{p['logic']}")

    lines.append(f"\n{bar}")
    lines.append("📊 数据来源：500.com竞彩 | 懂球帝API | 欧赔/亚盘分析页")
    lines.append("📋 分析框架：POWER-6六维模型")
    lines.append("⚠️  以上分析仅供参考，不构成投注建议")
    return "\n".join(lines)


# ── 主入口 ──

def main():
    parser = argparse.ArgumentParser(description="世界杯竞彩分析报告生成器")
    parser.add_argument("--data", help="JSON数据文件路径")
    parser.add_argument("--output", "-o", help="输出路径（不含扩展名，自动加.html/.txt）",
                        default="worldcup_report")
    parser.add_argument("--format", "-f", choices=["html", "text", "both"], default="both",
                        help="输出格式（默认both）")
    parser.add_argument("--demo", action="store_true", help="内置示例数据")
    parser.add_argument("--schema", action="store_true", help="打印JSON数据格式")
    args = parser.parse_args()

    if args.schema:
        print(DATA_SCHEMA)
        return

    if args.demo:
        data = _demo_data()
    elif args.data:
        with open(args.data, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    base = args.output
    if base.endswith(".html") or base.endswith(".txt"):
        base = os.path.splitext(base)[0]

    if args.format in ("html", "both"):
        html = generate_html(data)
        path = base + ".html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ HTML报告: {os.path.abspath(path)}")

    if args.format in ("text", "both"):
        text = generate_text(data)
        path = base + ".txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✅ 文本报告: {os.path.abspath(path)}")


def _demo_data():
    return {
        "date": "2026-06-16", "play_type": "让球胜平负", "parlay_num": 4, "match_count": 4,
        "matches": [
            {"id": "周一013", "time": "00:00", "home": "西班牙", "away": "佛得角",
             "handicap": -2, "sp": {"胜": 1.46, "平": 4.70, "负": 4.32}, "tag": "碾压局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×20%", "desc": "FIFA排名2 vs 67，S级碾压", "score": 9},
                 {"name": "状态引擎", "weight": "×20%", "desc": "西班牙⚡上升态；佛得角📉下滑态", "score": 9},
                 {"name": "盘口密码", "weight": "×25%", "desc": "亚盘升盘低水偏上盘，⚠️赢盘率仅30%", "score": 6},
                 {"name": "交锋心结", "weight": "×10%", "desc": "无历史包袱", "score": 7},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "西班牙⭐⭐⭐⭐⭐ vs 佛得角⭐⭐", "score": 9},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球胜", "rec_sp": 1.46, "total_score": 67,
             "risk": "⚠️ 西班牙友谊赛两度让2球走盘，世界杯首轮可能收力"},
            {"id": "周一014", "time": "03:00", "home": "比利时", "away": "埃及",
             "handicap": -1, "sp": {"胜": 2.35, "平": 3.42, "负": 2.43}, "tag": "压制局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×20%", "desc": "FIFA排名9 vs 29，A级压制", "score": 7},
                 {"name": "状态引擎", "weight": "×20%", "desc": "比利时🔄波动态；埃及⚡上升态", "score": 6},
                 {"name": "盘口密码", "weight": "×25%", "desc": "一球升盘高水，SP分布均匀分歧大", "score": 6},
                 {"name": "交锋心结", "weight": "×10%", "desc": "无历史包袱", "score": 6},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "比利时⭐⭐⭐⭐ vs 埃及⭐⭐⭐", "score": 6},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球负", "rec_sp": 2.43, "total_score": 65,
             "risk": "⚠️ 比利时让1球下埃及有韧性，赢1球仅走盘"},
            {"id": "周一015", "time": "06:00", "home": "沙特阿拉伯", "away": "乌拉圭",
             "handicap": 1, "sp": {"胜": 2.83, "平": 3.10, "负": 2.21}, "tag": "优势局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×20%", "desc": "FIFA排名61 vs 16，乌拉圭A级压制", "score": 8},
                 {"name": "状态引擎", "weight": "×20%", "desc": "沙特📉下滑态；乌拉圭稳健", "score": 8},
                 {"name": "盘口密码", "weight": "×25%", "desc": "受一球降盘水位下行，方向未变", "score": 7},
                 {"name": "交锋心结", "weight": "×10%", "desc": "沙特对南美球队心理劣势", "score": 8},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "沙特⭐⭐ vs 乌拉圭⭐⭐⭐⭐", "score": 8},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球负", "rec_sp": 2.21, "total_score": 72, "risk": ""},
            {"id": "周一016", "time": "09:00", "home": "伊朗", "away": "新西兰",
             "handicap": -1, "sp": {"胜": 2.87, "平": 3.30, "负": 2.09}, "tag": "碾压局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×20%", "desc": "FIFA排名20 vs 85，S级碾压", "score": 9},
                 {"name": "状态引擎", "weight": "×20%", "desc": "伊朗⚡上升态；新西兰🥶冰封态", "score": 9},
                 {"name": "盘口密码", "weight": "×25%", "desc": "半球/一球，让球胜2.87有吸引力", "score": 7},
                 {"name": "交锋心结", "weight": "×10%", "desc": "伊朗对大洋洲球队绝对心理优势", "score": 8},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "伊朗⭐⭐⭐ vs 新西兰⭐", "score": 8},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球胜", "rec_sp": 2.87, "total_score": 75, "risk": ""},
        ],
        "parlays": [
            {"type": "safe", "icon": "🎯", "title": "稳妥方案", "sp": 22.47,
             "items": [
                 {"match": "西班牙 vs 佛得角", "direction": "让球胜", "sp": 1.46},
                 {"match": "比利时 vs 埃及", "direction": "让球负", "sp": 2.43},
                 {"match": "沙特 vs 乌拉圭", "direction": "让球负", "sp": 2.21},
                 {"match": "伊朗 vs 新西兰", "direction": "让球胜", "sp": 2.87},
             ],
             "logic": "西班牙碾压；比利时让1球下埃及韧性足；乌拉圭打低迷沙特；伊朗打鱼腩新西兰",
             "stars": "⭐⭐⭐⭐"},
            {"type": "value", "icon": "🔥", "title": "价值方案", "sp": 72.34,
             "items": [
                 {"match": "西班牙 vs 佛得角", "direction": "让球平", "sp": 4.70},
                 {"match": "比利时 vs 埃及", "direction": "让球负", "sp": 2.43},
                 {"match": "沙特 vs 乌拉圭", "direction": "让球负", "sp": 2.21},
                 {"match": "伊朗 vs 新西兰", "direction": "让球胜", "sp": 2.87},
             ],
             "logic": "西班牙让2球赢盘率30%，让球平4.70价值高；其余3场维持稳妥选择",
             "stars": "⭐⭐⭐"},
            {"type": "dark", "icon": "💎", "title": "冷门方案", "sp": 103.53,
             "items": [
                 {"match": "西班牙 vs 佛得角", "direction": "让球平", "sp": 4.70},
                 {"match": "比利时 vs 埃及", "direction": "让球胜", "sp": 2.35},
                 {"match": "沙特 vs 乌拉圭", "direction": "让球胜", "sp": 2.83},
                 {"match": "伊朗 vs 新西兰", "direction": "让球平", "sp": 3.30},
             ],
             "logic": "西班牙让2球平；比利时让1球赢；沙特爆冷；伊朗让1球平",
             "stars": "⭐⭐"},
        ]
    }


if __name__ == "__main__":
    main()
