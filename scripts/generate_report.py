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
import html
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
        {"name": "战力鸿沟", "weight": "×15%", "desc": "...", "score": 9},
        {"name": "盘口密码", "weight": "×35%", "desc": "【凯利】...【概率】...【亚盘】...【返还率】...", "score": 8}
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
      "expert": "Dr. Karl Vogel",
      "persona": "量化派 · 稳妥方案",
      "quote": "赔率是唯一的真相。",
      "focus": "凯利指数、隐含概率、多公司赔率一致性",
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
- parlays[].expert/persona/quote/focus — 三专家方案展示字段；缺省时按 type 自动填充
"""


# ── 工具函数 ──

def handicap_display(hc):
    if hc < 0: return f"主让{abs(hc)}球"
    elif hc > 0: return f"主受让{hc}球"
    else: return "平手"

def esc(value):
    return html.escape(str(value), quote=True)


# 票号：稳妥/价值/冷门固定顺序
STUB_SERIAL = {"safe": "SP-01", "value": "SP-02", "dark": "SP-03"}
STUB_TYPE_LABEL = {"safe": "稳妥", "value": "价值", "dark": "冷门"}


def confidence_boxes(stars_str):
    """⭐⭐⭐⭐ → 4 个实心方块 + 1 个空心（满 5）。
    stars 字符串里数 ⭐ 个数作为置信度，满格 5。
    """
    n = stars_str.count("⭐")
    boxes = []
    for i in range(5):
        boxes.append('<span class="conf-box off"></span>' if i >= n
                     else '<span class="conf-box"></span>')
    return "".join(boxes)

EXPERT_PRESETS = {
    "safe": {
        "expert": "Dr. Karl Vogel",
        "persona": "量化派 · 稳妥方案",
        "quote": "赔率是唯一的真相。",
        "focus": "凯利指数、隐含概率、多公司赔率一致性",
    },
    "value": {
        "expert": "Johnny \"The Handicapper\" Liu",
        "persona": "盘口派 · 价值方案",
        "quote": "盘口不是数学，是心理学。",
        "focus": "升降盘、水位异动、诱盘识别、走盘空间",
    },
    "dark": {
        "expert": "Mia Carter",
        "persona": "消息派 · 冷门方案",
        "quote": "90 分钟的比赛，胜负在更衣室就决定了。",
        "focus": "伤停、轮换、战意、赛程暗线、临场变量",
    },
}

def expert_meta(parlay):
    preset = EXPERT_PRESETS.get(parlay.get("type"), {})
    return {
        "expert": parlay.get("expert") or preset.get("expert", "专家方案"),
        "persona": parlay.get("persona") or preset.get("persona", parlay.get("title", "串关方案")),
        "quote": parlay.get("quote") or preset.get("quote", ""),
        "focus": parlay.get("focus") or preset.get("focus", ""),
    }


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
        # 串关 SP 自洽校验：声明 SP 应 ≈ 各项 SP 连乘。
        # 串关 SP 是纯算术，不该靠 LLM 手算；偏差 >5% 视为填错，拦截。
        if "sp" in p and "items" in p and p["items"]:
            product = 1.0
            for it in p["items"]:
                product *= float(it["sp"])
            declared = float(p["sp"])
            if product > 0 and abs(declared - product) / product > 0.05:
                errors.append(
                    f"{prefix}.sp={declared} 与各项连乘={product:.2f} 偏差>5%，"
                    f"串关SP应为各项SP之积")
    return errors


# ── HTML 渲染 ──

def fixtures_header(play_type):
    """对阵表表头：胜平负玩法无让球列（让球无意义），让球玩法有让球列。
    表格列固定为：编号 / 对阵 / [让球] / SP，时间并入对阵信息由逐场卡承担。"""
    if play_type == "胜平负":
        return "<th>编号</th><th>对阵</th><th>SP 胜/平/负</th>"
    return "<th>编号</th><th>对阵</th><th>让球</th><th>SP 胜/平/负</th>"


def render_match_table(matches, play_type):
    is_rangqiu = play_type == "让球胜平负"
    rows = []
    for m in matches:
        sp = m["sp"]
        sp_str = f'{sp["胜"]:.2f} / {sp["平"]:.2f} / {sp["负"]:.2f}'
        teams = (f'<span class="fx-team">{esc(m["home"])}</span> '
                 f'<span class="fx-vs">vs</span> '
                 f'<span class="fx-team">{esc(m["away"])}</span>')
        if is_rangqiu:
            hc = m.get("handicap", 0)
            hc_text = m.get("handicap_display") or handicap_display(hc)
            hc_cell = (f'<td class="fx-hc{" neg" if hc < 0 else ""}">'
                       f'{esc(hc_text)}</td>')
            rows.append(
                f'<tr>\n'
                f'  <td class="fx-id">{esc(m["id"])}</td>\n'
                f'  <td>{teams}</td>\n'
                f'  {hc_cell}\n'
                f'  <td class="fx-sp">{sp_str}</td>\n'
                f'</tr>')
        else:
            rows.append(
                f'<tr>\n'
                f'  <td class="fx-id">{esc(m["id"])}</td>\n'
                f'  <td>{teams}</td>\n'
                f'  <td class="fx-sp">{sp_str}</td>\n'
                f'</tr>')
    return "\n".join(rows)


def render_dim_cell(d):
    """单个维度格子（等宽记分牌式）。盘口密码由调用方单独处理占整行。"""
    return (f'<div class="dim">\n'
            f'  <div class="d-top">\n'
            f'    <span class="d-name">{esc(d["name"])}<span class="w">{esc(d["weight"])}</span></span>\n'
            f'    <span class="d-score">{d["score"]}<span class="max">/10</span></span>\n'
            f'  </div>\n'
            f'  <div class="d-desc">{esc(d["desc"])}</div>\n'
            f'</div>\n')


def render_cipher_dim(d):
    """盘口密码维度：占整行，深一档底色，【】子块结构化高亮。"""
    desc = esc(d["desc"])
    blocks = ""
    sections = desc.split("【")
    for section in sections[1:]:
        if "】" not in section:
            continue
        title_end = section.index("】")
        title = section[:title_end]
        body = section[title_end + 1:].strip()
        body = body.replace("✅", '<span class="signal-up">✅</span>')
        body = body.replace("⚠️", '<span class="signal-down">⚠️</span>')
        body = body.replace("→", '<span class="signal-warn">→</span>')
        blocks += (f'<div class="hc-block"><span class="hc-block-title">'
                   f'{title}</span> {body}</div>\n')
    preamble = sections[0].strip()
    return (f'<div class="dim is-cipher">\n'
            f'  <div class="d-top">\n'
            f'    <span class="d-name">{esc(d["name"])}<span class="w">{esc(d["weight"])}</span></span>\n'
            f'    <span class="d-score">{d["score"]}<span class="max">/10</span></span>\n'
            f'  </div>\n'
            f'  <div class="d-desc">{preamble}</div>\n'
            f'  {blocks}'
            f'</div>\n')


def render_match_cards(matches):
    cards = []
    for m in matches:
        dims = ""
        for d in m["dims"]:
            if d["name"] == "盘口密码":
                dims += render_cipher_dim(d)
            else:
                dims += render_dim_cell(d)
        tagline = ""
        if m.get("dims_summary"):
            tagline = f'<div class="match-tagline">{esc(m["dims_summary"])}</div>\n'
        risk = f'<div class="risk">{esc(m["risk"])}</div>' if m.get("risk") else ""
        cards.append(
            f'<article class="match">\n'
            f'  <div class="match-head">\n'
            f'    <span class="m-title"><span class="mono">{esc(m["id"])}</span>{esc(m["home"])} vs {esc(m["away"])}</span>\n'
            f'    <span class="m-tag">{esc(m["tag"])}</span>\n'
            f'  </div>\n'
            f'  {tagline}'
            f'  <div class="dims">\n{dims}  </div>\n'
            f'  <div class="match-foot">\n'
            f'    <div class="rec">\n'
            f'      <span class="r-label">推荐</span>\n'
            f'      <span class="r-dir">{esc(m["recommendation"])}</span>\n'
            f'      <span class="r-sp">{m["rec_sp"]:.2f}</span>\n'
            f'    </div>\n'
            f'    <div class="total"><div class="t-num">{m["total_score"]}</div><div class="t-max">/ 100</div></div>\n'
            f'  </div>\n'
            f'  {risk}\n'
            f'</article>')
    return "\n\n".join(cards)

def render_parlay_cards(parlays):
    cards = []
    for p in parlays:
        meta = expert_meta(p)
        ptype = p["type"]
        items = ""
        for it in p["items"]:
            items += (f'<div class="stub-item">\n'
                      f'  <span class="i-match">{esc(it["match"])}</span>\n'
                      f'  <span class="i-dir">{esc(it["direction"])}</span>\n'
                      f'  <span class="i-sp">{it["sp"]:.2f}</span>\n'
                      f'</div>\n')
        quote = (f'<span class="h-quote">「{esc(meta["quote"])}」</span>'
                 if meta.get("quote") else "")
        focus = (f'<div class="stub-focus">擅长 — {esc(meta["focus"])}</div>'
                 if meta.get("focus") else "")
        serial = STUB_SERIAL.get(ptype, "SP-00")
        tlabel = STUB_TYPE_LABEL.get(ptype, "")
        cards.append(
            f'<div class="stub">\n'
            f'  <div class="stub-head">\n'
            f'    <div class="h-left">\n'
            f'      <span class="h-type">票号 {serial} · {tlabel}</span>\n'
            f'      <span class="h-expert">{esc(meta["expert"])}</span>\n'
            f'      {quote}\n'
            f'    </div>\n'
            f'    <div class="h-sp-wrap">\n'
            f'      <div class="h-sp">{p["sp"]:.2f}</div>\n'
            f'      <div class="h-sp-cap">串关 SP</div>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'  <div class="tear"></div>\n'
            f'  <div class="stub-body">\n'
            f'    {focus}\n'
            f'    <div class="stub-items">\n{items}    </div>\n'
            f'    <div class="stub-logic">{esc(p["logic"])}</div>\n'
            f'    <div class="stub-conf">置信度 {confidence_boxes(p.get("stars", ""))}</div>\n'
            f'  </div>\n'
            f'</div>')
    return "\n\n".join(cards)


def render_verdict(parlays):
    """顶部三方案摘要：方案名 / SP / 首场方向作为最简线索。"""
    cells = []
    for p in parlays:
        tlabel = STUB_TYPE_LABEL.get(p["type"], p.get("title", ""))
        first_dir = p["items"][0]["direction"] if p.get("items") else ""
        cells.append(
            f'  <div>\n'
            f'    <div class="v-label">{esc(tlabel)}</div>\n'
            f'    <div class="v-sp">{p["sp"]:.2f}</div>\n'
            f'    <div class="v-dir">{esc(first_dir)}</div>\n'
            f'  </div>')
    return "\n".join(cells)


def generate_html(data, template_path=TEMPLATE_PATH):
    errors = validate_data(data)
    if errors:
        print("Data validation failed:")
        for e in errors: print(f"  - {e}")
        sys.exit(1)
    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    play_type = data["play_type"]
    tpl = tpl.replace("{{date}}", esc(data["date"]))
    tpl = tpl.replace("{{play_type}}", esc(play_type))
    tpl = tpl.replace("{{parlay_num}}", str(data["parlay_num"]))
    tpl = tpl.replace("{{match_count}}", str(data["match_count"]))
    tpl = tpl.replace("{{fixtures_header}}", fixtures_header(play_type))
    tpl = tpl.replace("{{match_table_rows}}", render_match_table(data["matches"], play_type))
    tpl = tpl.replace("{{match_cards}}", render_match_cards(data["matches"]))
    tpl = tpl.replace("{{parlay_cards}}", render_parlay_cards(data["parlays"]))
    tpl = tpl.replace("{{verdict}}", render_verdict(data["parlays"]))
    # 刊头串关 SP：取稳妥方案（如有），作为整份报告的代表性赔率
    safe_sp = next((p["sp"] for p in data["parlays"] if p["type"] == "safe"),
                   data["parlays"][0]["sp"] if data["parlays"] else 0)
    tpl = tpl.replace("{{verdict_sp}}", f"SP {safe_sp:.2f}")
    tpl = tpl.replace("{{fetched_at}}",
                      f" · 数据截至 {esc(data['fetched_at'])}" if data.get("fetched_at") else "")
    tpl = tpl.replace("{{health_line}}",
                      f" · {esc(data['health_line'])}" if data.get("health_line") else "")
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
    lines.append(f"【三专家{data['parlay_num']}串1方案】")
    for p in data["parlays"]:
        meta = expert_meta(p)
        lines.append(f"\n{p['icon']} {meta['expert']} · {meta['persona']}")
        if meta.get("quote"):
            lines.append(f"  「{meta['quote']}」")
        if meta.get("focus"):
            lines.append(f"  擅长：{meta['focus']}")
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
                 {"name": "战力鸿沟", "weight": "×15%", "desc": "FIFA排名2 vs 67，S级碾压", "score": 9},
                 {"name": "状态引擎", "weight": "×15%", "desc": "西班牙⚡上升态；佛得角📉下滑态", "score": 9},
                 {"name": "盘口密码", "weight": "×35%", "desc": "亚盘升盘低水偏上盘，⚠️赢盘率仅30%", "score": 6},
                 {"name": "交锋心结", "weight": "×10%", "desc": "无历史包袱", "score": 7},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "西班牙⭐⭐⭐⭐⭐ vs 佛得角⭐⭐", "score": 9},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球胜", "rec_sp": 1.46, "total_score": 67,
             "risk": "⚠️ 西班牙友谊赛两度让2球走盘，世界杯首轮可能收力"},
            {"id": "周一014", "time": "03:00", "home": "比利时", "away": "埃及",
             "handicap": -1, "sp": {"胜": 2.35, "平": 3.42, "负": 2.43}, "tag": "压制局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×15%", "desc": "FIFA排名9 vs 29，A级压制", "score": 7},
                 {"name": "状态引擎", "weight": "×15%", "desc": "比利时🔄波动态；埃及⚡上升态", "score": 6},
                 {"name": "盘口密码", "weight": "×35%", "desc": "一球升盘高水，SP分布均匀分歧大", "score": 6},
                 {"name": "交锋心结", "weight": "×10%", "desc": "无历史包袱", "score": 6},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "比利时⭐⭐⭐⭐ vs 埃及⭐⭐⭐", "score": 6},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球负", "rec_sp": 2.43, "total_score": 65,
             "risk": "⚠️ 比利时让1球下埃及有韧性，赢1球仅走盘"},
            {"id": "周一015", "time": "06:00", "home": "沙特阿拉伯", "away": "乌拉圭",
             "handicap": 1, "sp": {"胜": 2.83, "平": 3.10, "负": 2.21}, "tag": "优势局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×15%", "desc": "FIFA排名61 vs 16，乌拉圭A级压制", "score": 8},
                 {"name": "状态引擎", "weight": "×15%", "desc": "沙特📉下滑态；乌拉圭稳健", "score": 8},
                 {"name": "盘口密码", "weight": "×35%", "desc": "受一球降盘水位下行，方向未变", "score": 7},
                 {"name": "交锋心结", "weight": "×10%", "desc": "沙特对南美球队心理劣势", "score": 8},
                 {"name": "阵容博弈", "weight": "×15%", "desc": "沙特⭐⭐ vs 乌拉圭⭐⭐⭐⭐", "score": 8},
                 {"name": "赛程暗线", "weight": "×10%", "desc": "首轮体能充沛", "score": 7},
             ],
             "recommendation": "让球负", "rec_sp": 2.21, "total_score": 72, "risk": ""},
            {"id": "周一016", "time": "09:00", "home": "伊朗", "away": "新西兰",
             "handicap": -1, "sp": {"胜": 2.87, "平": 3.30, "负": 2.09}, "tag": "碾压局",
             "dims": [
                 {"name": "战力鸿沟", "weight": "×15%", "desc": "FIFA排名20 vs 85，S级碾压", "score": 9},
                 {"name": "状态引擎", "weight": "×15%", "desc": "伊朗⚡上升态；新西兰🥶冰封态", "score": 9},
                 {"name": "盘口密码", "weight": "×35%", "desc": "半球/一球，让球胜2.87有吸引力", "score": 7},
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
