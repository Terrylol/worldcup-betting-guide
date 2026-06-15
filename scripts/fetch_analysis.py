#!/usr/bin/env python3
"""
500.com 赛事分析页抓取 → 纯文本输出

设计理念：
  代码只做「脏活」（curl + HTML→纯文本 + 去导航噪音），语义提取全部交给 LLM。
  不依赖关键词切分，不依赖 HTML 结构，整页纯文本直接丢给 LLM 解析。

  为什么不切分板块：
  - 关键词切分（如按"澳门心水推荐"定位）本质还是硬编码，
    网站改措辞就会断
  - LLM 能在全文中定位任何数据，不需要代码预先切割
  - 少一层预处理 = 少一个故障点

用法：
  # 默认：输出数据页纯文本（推荐，LLM 直接读）
  python3 fetch_analysis.py --fixtureid 1359212

  # 指定页面类型
  python3 fetch_analysis.py --fixtureid 1359212 --page shuju
  python3 fetch_analysis.py --fixtureid 1359212 --page yazhi
  python3 fetch_analysis.py --fixtureid 1359212 --page ouzhi

  # 一次抓全部3个页面
  python3 fetch_analysis.py --fixtureid 1359212 --page all

  # JSON 格式输出
  python3 fetch_analysis.py --fixtureid 1359212 --page all --json

  # 控制输出长度（避免 token 爆炸）
  python3 fetch_analysis.py --fixtureid 1359212 --max-chars 8000
"""

import argparse
import json
import re
import subprocess
import sys
from html import unescape


def fetch_html(url, timeout=30):
    """curl 抓取 + GB2312 → UTF-8"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", url,
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"],
            capture_output=True, timeout=timeout,
        )
        raw = result.stdout
        try:
            return raw.decode("gb2312", errors="replace")
        except Exception:
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERROR] 抓取失败: {e}"


def html_to_text(html):
    """
    HTML → 干净文本。唯一职责：去掉 HTML 噪音，保留语义内容。
    不做任何板块切分、关键词匹配、数据提取。
    """
    # 去 script/style（最大噪音源）
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # 换行标签保留段落结构
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|li|h[1-6]|table|thead|tbody)>', '\n', text, flags=re.IGNORECASE)
    # 去所有剩余标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 实体解码
    text = unescape(text)
    # 压缩空白（保留换行结构）
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]+\n', '\n\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def trim_noise(text):
    """
    去掉导航/广告/登录框等噪音行，保留核心数据。

    策略：逐行过滤，基于内容特征而非关键词位置。
    - 导航行特征：短、碎片化、无数字、无语义（"首页"、"登录"、"余额"等）
    - 数据行特征：包含数字、比赛信息、赔率等

    这个方法即使网站完全改版换布局，只要数据内容还在文本里，
    LLM 就能找到并解析。
    """
    # 噪音行特征模式（这些行几乎不可能包含有价值数据）
    noise_patterns = [
        # 登录/注册相关
        r'^(登录|注册|用户名|密码|验证码|换一张|免费注册|忘记密码|我的成长|我的安全|显示余额|退出|个人中心)',
        # 导航菜单
        r'^(首页|资讯|客服热线|选择彩种|扫描二维码|手机版|下载|余额|红包|消息|提醒|活动优惠|系统通知|我知道了)',
        # 彩种/玩法名称（纯导航，不可能出现在数据分析中）
        r'^(超级大乐透|竞彩足球|竞彩篮球|足彩|乐透|排列[35]|7星彩|胜负彩|任选九|半全场|进球彩|冠亚军|单关投注|混合过关|比分|进球数|大小分|胜分差|让分胜负|让球|胜负|胆拖投注|定胆杀号|基本投注|复式投注|胜平负)',
        # 通用导航
        r'^(全国开奖|数据图表|足球比分|篮球比分|网球比分|足球联赛|篮球联赛|彩票资讯|赛事预告|帮助中心|客户端下载|智能大数据|关闭)',
        # 500.com 特有噪音
        r'^(欢迎您|隐藏|红包|上一期|下一期|500彩票|竞足|足彩|上一期|图表分析|数据分析|专家情报|投注分析|百家欧赔|让球指数|亚盘对比|大小指数|比分指数|走势分析|技术统计|上赛季排名|使用手机二维码)',
        # 赛事列表中的编号行（如"1 " "2 "等，单独一行只有数字+VS）
        r'^\d+\s*$',
        # 空行
        r'^$',
    ]
    noise_re = re.compile('|'.join(noise_patterns), re.IGNORECASE)

    lines = text.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        # 跳过噪音行
        if noise_re.match(stripped):
            continue
        # 跳过极短且无信息的行（≤3字符且不含数字或中文）
        if len(stripped) <= 3 and not any(c.isdigit() or '\u4e00' <= c <= '\u9fff' for c in stripped):
            continue
        filtered.append(line)

    # 再做一轮：去掉连续空行
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(filtered))
    return result.strip()


def fetch_page(fixtureid, page_type):
    """抓取指定页面类型，返回纯文本"""
    page_urls = {
        "shuju": f"https://odds.500.com/fenxi/shuju-{fixtureid}.shtml",
        "yazhi": f"https://odds.500.com/fenxi/yazhi-{fixtureid}.shtml",
        "ouzhi": f"https://odds.500.com/fenxi/ouzhi-{fixtureid}.shtml",
    }
    if page_type not in page_urls:
        return f"[ERROR] 未知页面类型: {page_type}，可选: {', '.join(page_urls.keys())}"

    html = fetch_html(page_urls[page_type])
    if not html or html.startswith("[ERROR]"):
        return html
    text = html_to_text(html)
    return trim_noise(text)


def main():
    parser = argparse.ArgumentParser(
        description="500.com分析页抓取→纯文本（供LLM解析）",
        epilog="设计理念：代码只做curl+去HTML噪音，语义提取全部交给LLM。不依赖关键词切分。"
    )
    parser.add_argument("--fixtureid", required=True, help="赛事ID（如 1359212）")
    parser.add_argument("--page", default="shuju",
                        choices=["shuju", "yazhi", "ouzhi", "all"],
                        help="页面类型：shuju=数据页, yazhi=亚盘, ouzhi=欧赔, all=全部（默认shuju）")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    parser.add_argument("--max-chars", type=int, default=8000,
                        help="单页最大输出字符数（默认8000，避免token爆炸）")
    parser.add_argument("--raw", action="store_true",
                        help="不做任何trim，输出完整纯文本（含导航噪音）")
    args = parser.parse_args()

    pages_to_fetch = (
        ["shuju", "yazhi", "ouzhi"] if args.page == "all"
        else [args.page]
    )

    page_names = {"shuju": "数据页", "yazhi": "亚盘页", "ouzhi": "欧赔页"}
    result = {"fixtureid": args.fixtureid}

    for page_type in pages_to_fetch:
        print(f"正在抓取{page_names[page_type]}...", file=sys.stderr)
        html = fetch_html({
            "shuju": f"https://odds.500.com/fenxi/shuju-{args.fixtureid}.shtml",
            "yazhi": f"https://odds.500.com/fenxi/yazhi-{args.fixtureid}.shtml",
            "ouzhi": f"https://odds.500.com/fenxi/ouzhi-{args.fixtureid}.shtml",
        }[page_type])

        if html.startswith("[ERROR]"):
            text = html
        else:
            text = html_to_text(html)
            if not args.raw:
                text = trim_noise(text)

        result[f"{page_type}_length"] = len(text)
        result[f"{page_type}_text"] = text[:args.max_chars]

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for page_type in pages_to_fetch:
            text = result.get(f"{page_type}_text", "")
            if text:
                print(f"\n{'='*60}")
                print(f"【{page_names[page_type]}】 完整纯文本（LLM 直接解析）")
                print(f"{'='*60}")
                print(text)
                if len(text) >= args.max_chars:
                    print(f"\n... [已截断，原文{result.get(f'{page_type}_length', '?')}字符]")


if __name__ == "__main__":
    main()
