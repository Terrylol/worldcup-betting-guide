#!/usr/bin/env python3
"""
抓取500.com竞彩足球赛事数据
仅筛选"世界杯"赛事，输出JSON格式

Usage:
    python3 fetch_matches.py [--date YYYY-MM-DD] [--all] [--raw-text]
    
    --date      指定日期筛选（默认返回所有可售赛事）
    --all       包含已截止赛事（默认仅未截止）
    --raw-text  额外输出整页HTML转纯文本（供LLM解析兜底）
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from html import unescape


def fetch_html(url="https://trade.500.com/jczq/"):
    """用curl抓取页面并转码为UTF-8"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", url, "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"],
            capture_output=True,
            timeout=30,
        )
        raw = result.stdout
        try:
            text = raw.decode("gb2312", errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
        return text
    except Exception as e:
        print(f"[ERROR] 抓取失败: {e}", file=sys.stderr)
        return ""


def html_to_text(html):
    """HTML → 干净文本：去标签、解码实体、压缩空白"""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()


def extract_attr(html, attr_name):
    """从HTML片段中提取指定data属性的值"""
    pattern = re.compile(rf'{attr_name}="([^"]*)"')
    m = pattern.search(html)
    return m.group(1) if m else ""


def parse_matches(html):
    """解析HTML中的赛事数据"""
    matches = []
    
    row_splits = re.split(r'<tr\s+class="bet-tb-tr', html)
    
    # SP赔率提取
    # nspf = 非让球胜平负（普通胜平负）, spf = 让球胜平负
    sp_pattern = re.compile(
        r'data-type="(nspf|spf)"\s+data-value="([0123])"\s+data-sp="([\d.]+)"'
    )
    
    for chunk in row_splits[1:]:
        fixtureid = extract_attr(chunk, "data-fixtureid")
        if not fixtureid:
            continue
        
        homesxname = extract_attr(chunk, "data-homesxname")
        awaysxname = extract_attr(chunk, "data-awaysxname")
        matchdate = extract_attr(chunk, "data-matchdate")
        matchtime = extract_attr(chunk, "data-matchtime")
        rangqiu = extract_attr(chunk, "data-rangqiu")
        simpleleague = extract_attr(chunk, "data-simpleleague")
        buyendtime = extract_attr(chunk, "data-buyendtime")
        matchnum = extract_attr(chunk, "data-matchnum")
        isend = extract_attr(chunk, "data-isend")
        
        if simpleleague != "世界杯":
            continue
        
        tr_end = chunk.find("</tr>")
        row_html = chunk[:tr_end] if tr_end > 0 else chunk[:3000]
        
        odds = {"nspf": {}, "spf": {}}
        for sp_match in sp_pattern.finditer(row_html):
            bet_type = sp_match.group(1)
            value = sp_match.group(2)
            sp_val = sp_match.group(3)
            value_map = {"3": "胜", "1": "平", "0": "负"}
            odds[bet_type][value_map[value]] = float(sp_val)
        
        match_data = {
            "赛事编号": matchnum,
            "联赛": simpleleague,
            "主队": homesxname,
            "客队": awaysxname,
            "比赛日期": matchdate,
            "比赛时间": matchtime,
            "让球": int(rangqiu) if rangqiu else 0,
            "截止投注": buyendtime,
            "已截止": isend == "1",
            "胜平负SP": odds["nspf"],   # nspf = 非让球/普通胜平负
            "让球胜平负SP": odds["spf"],  # spf = 让球胜平负
            "fixtureid": fixtureid,
            "分析页_数据": f"https://odds.500.com/fenxi/shuju-{fixtureid}.shtml",
            "分析页_亚盘": f"https://odds.500.com/fenxi/yazhi-{fixtureid}.shtml",
            "分析页_欧赔": f"https://odds.500.com/fenxi/ouzhi-{fixtureid}.shtml",
        }
        matches.append(match_data)
    
    return matches


def parse_date_arg():
    """解析 --date 参数，返回日期字符串或None"""
    for i, arg in enumerate(sys.argv):
        if arg == "--date" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--date="):
            return arg.split("=", 1)[1]
    return None


def main():
    include_ended = "--all" in sys.argv
    raw_text_mode = "--raw-text" in sys.argv
    target_date = parse_date_arg()
    
    print("正在抓取500.com竞彩赛事数据...", file=sys.stderr)
    html = fetch_html()
    if not html:
        print(json.dumps({"error": "抓取失败，无法访问500.com"}, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # --raw-text 模式：输出整页纯文本供 LLM 解析
    if raw_text_mode:
        clean = html_to_text(html)
        # 截取赛事区域（跳过头部导航垃圾）
        idx = clean.find("竞彩足球")
        if idx > 0:
            clean = clean[idx:]
        print(json.dumps({
            "raw_text_length": len(clean),
            "raw_text": clean[:20000],
        }, ensure_ascii=False, indent=2))
        return
    
    matches = parse_matches(html)
    
    if not include_ended:
        matches = [m for m in matches if not m["已截止"]]
    
    # 按日期筛选（如果指定了 --date）
    if target_date:
        matches = [m for m in matches if m["比赛日期"] == target_date]
    
    if not matches:
        msg = f"未找到{target_date + '的' if target_date else ''}世界杯可售赛事" if not include_ended else f"未找到{target_date + '的' if target_date else ''}世界杯赛事（含已截止）"
        print(json.dumps({
            "提示": msg,
            "建议": "可尝试使用 --all 参数包含已截止赛事，或更换日期",
            "世界杯赛事数": 0,
            "赛事列表": []
        }, ensure_ascii=False, indent=2))
        return
    
    result = {
        "抓取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "筛选日期": target_date or "全部",
        "世界杯赛事数": len(matches),
        "赛事列表": matches,
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
