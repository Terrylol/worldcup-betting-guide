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


def extract_odds_tables(html):
    """按公司提取赔率表（pl_table_data）+ 所属公司名。

    500.com 把每家公司的盘口/赔率装在 <table class="pl_table_data"> 里，
    公司名在其前方的 <p> 标签中（同属一个公司单元格）。只取这部分可砍掉
    导航噪音，且公司名与数据成对，便于 LLM 按公司分析（如"澳门凯利/立博
    返还率"）。

    注意：不能按 <tr> 切分再找表——pl_table_data 表内部本身含 <tr> 行，
    切分会把表撕碎。这里改为直接定位每个表，再回看其前方最近的公司名 <p>。

    返回 None 表示锚点未命中（网站改版），调用方应回退到全页纯文本。
    """
    # 单遍前向扫描：按文档顺序同时匹配 <p> 与赔率表，记住最近见过的公司名 <p>。
    # 每家公司有「即时盘+初盘」两张表，公司 <p> 在第一张表前；前向扫描让两张表
    # 都带上同一公司名（两张表之间无 <p>，last_company 不变）。
    token_re = re.compile(
        r'<p[^>]*>(.*?)</p>|<table[^>]*class="pl_table_data"[^>]*>(.*?)</table>',
        re.DOTALL)
    blocks = []
    last_company = ''
    for m in token_re.finditer(html):
        p_inner, tbl_inner = m.group(1), m.group(2)
        if p_inner is not None:
            company = re.sub(r'<[^>]+>', '', p_inner).strip()
            if company:
                last_company = company
        elif tbl_inner is not None:
            txt = unescape(
                re.sub(r'[ \t]+', ' ', re.sub(r'<[^>]+>', ' ', tbl_inner))
            ).strip()
            if txt:
                blocks.append(f"[{last_company}] {txt}")
    if not blocks:
        return None, 0
    # 每家公司通常含「即时盘+初盘」两张表，公司数 ≈ 表数 / 2
    n_companies = len({b.split(']')[0] for b in blocks if b.startswith('[')}) or len(blocks)
    return '\n'.join(blocks), n_companies


def build_data_health(full_texts, pages_fetched, companies=None):
    """生成数据可用性自检清单。

    把"某维度是否抓到真实数据"做成结构化信号（✓/✗ + 命中依据），供 LLM
    判定该维度能否填入真实数据。标 ✗ 的维度 LLM 必须写"数据暂缺"并按权重
    重分配，禁止用方法论的示例数字硬编。
    """
    companies = companies or {}
    shuju = full_texts.get("shuju", "")
    health = []

    # 数据页可探测的维度
    if "shuju" in pages_fetched:
        dim_checks = [
            ("战力鸿沟/FIFA排名", [r"赛前排名", r"世界排名", r"国际足联"]),
            ("状态引擎/近期战绩", [r"近10场", r"近6场", r"胜率"]),
            ("交锋心结/交锋记录", [r"交战", r"交锋", r"历史交锋"]),
            ("阵容博弈/伤停报道", [r"伤停", r"停赛", r"缺阵", r"伤员"]),
        ]
        for dim, kws in dim_checks:
            hit = next((k for k in kws if re.search(k, shuju)), None)
            health.append((dim, "✓" if hit else "✗", hit or "未检测到"))

    # 盘口密码维度：由亚盘/欧赔页的公司表数量判定
    if "yazhi" in pages_fetched:
        n = companies.get("yazhi", 0)
        health.append(("盘口密码/亚盘", "✓" if n > 0 else "✗",
                       f"{n}家公司" if n else "未抓到亚盘表"))
    if "ouzhi" in pages_fetched:
        n = companies.get("ouzhi", 0)
        health.append(("盘口密码/欧赔", "✓" if n > 0 else "✗",
                       f"{n}家公司" if n else "未抓到欧赔表"))
    return health


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
    full_texts = {}  # 截断前的完整文本，供自检探测（输出用截断后的）
    companies = {}   # 各页抓到的公司表数量，供盘口密码维度自检

    for page_type in pages_to_fetch:
        print(f"正在抓取{page_names[page_type]}...", file=sys.stderr)
        html = fetch_html({
            "shuju": f"https://odds.500.com/fenxi/shuju-{args.fixtureid}.shtml",
            "yazhi": f"https://odds.500.com/fenxi/yazhi-{args.fixtureid}.shtml",
            "ouzhi": f"https://odds.500.com/fenxi/ouzhi-{args.fixtureid}.shtml",
        }[page_type])

        if html.startswith("[ERROR]"):
            text = html
            n_companies = 0
        elif not args.raw and page_type in ("yazhi", "ouzhi"):
            # 优先按 pl_table_data 锚点定向提取：砍掉导航噪音、保留公司名
            extracted, n_companies = extract_odds_tables(html)
            text = extracted if extracted else trim_noise(html_to_text(html))
            if not extracted:
                n_companies = 0
        else:
            text = html_to_text(html)
            n_companies = 0
            if not args.raw:
                text = trim_noise(text)

        result[f"{page_type}_length"] = len(text)
        result[f"{page_type}_text"] = text[:args.max_chars]
        result[f"{page_type}_companies"] = n_companies
        # 自检必须在截断前的完整文本上探测，否则后段关键词漏检导致误报 ✗
        full_texts[page_type] = text
        companies[page_type] = n_companies

    # 数据可用性自检：把"某维度有没有真实数据"做成明确的结构化信号，
    # 避免LLM在空缺维度用方法论的示例数字"合理填补"（硬编）。
    result["data_health"] = build_data_health(full_texts, pages_to_fetch, companies)

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

        # 数据可用性自检：标 ✗ 的维度禁止填入示例数字
        if result.get("data_health"):
            print(f"\n{'='*60}")
            print("【数据可用性自检】（✗ 维度须写'数据暂缺'并重分配权重，禁止填示例数字）")
            print(f"{'='*60}")
            for dim, flag, detail in result["data_health"]:
                print(f"  {flag} {dim}：{detail}")


if __name__ == "__main__":
    main()
