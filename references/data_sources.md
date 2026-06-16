# 数据源参考手册

## 1. 500.com 竞彩主页面（核心数据源）

### 赛事列表页
- URL: `https://trade.500.com/jczq/`
- 编码: GB2312，需 `iconv -f gb2312 -t utf-8` 转码
- 关键HTML结构：`<tr class="bet-tb-tr ...">` 每行一场赛事
- 自动化脚本: `scripts/fetch_matches.py`

### 赛事行 data 属性
| 属性 | 含义 | 示例 |
|------|------|------|
| `data-fixtureid` | 赛事唯一ID（用于分析页URL） | `1359209` |
| `data-infomatchid` | 信息页ID | `164905` |
| `data-homesxname` | 主队简称 | `西班牙` |
| `data-awaysxname` | 客队简称 | `佛得角` |
| `data-matchdate` | 比赛日期 | `2026-06-16` |
| `data-matchtime` | 比赛时间 | `00:00` |
| `data-rangqiu` | 让球数（负=主让，正=主受让） | `-2` |
| `data-simpleleague` | 联赛名 | `世界杯` |
| `data-buyendtime` | 截止投注时间 | `2026-06-15 22:00:00` |
| `data-matchnum` | 竞彩编号 | `周一013` |
| `data-isend` | 是否已截止（1=是） | `1` |
| `data-homeid` | 主队ID | `12` |
| `data-awayid` | 客队ID | `152` |

### SP赔率提取

在 `<td class="td td-betbtn">` 内，分两行：

- **B1行**（`itm-rangB1`）：普通胜平负
  - `data-type="nspf"` — 非让球胜平负（Non-handicap Sheng Ping Fu）
  - `data-value="3"` → 胜（主胜） / `"1"` → 平 / `"0"` → 负（客胜）
  - `data-sp="X.XX"` → SP赔率值
  - 实力悬殊比赛此行显示"未开售"，无nspf数据

- **B2行**（`itm-rangB2`）：让球胜平负
  - `data-type="spf"` — 让球胜平负（Sheng Ping Fu，竞彩默认玩法）
  - `data-value="3"` → 让球后胜 / `"1"` → 让球后平 / `"0"` → 让球后负
  - `data-sp="X.XX"` → SP赔率值

### 映射速查

| 页面标记 | 含义 | 对应玩法 | 脚本输出字段 |
|---------|------|---------|-------------|
| `nspf` | 非让球胜平负 | 胜平负 | `胜平负SP` |
| `spf` | 让球胜平负 | 让球胜平负 | `让球胜平负SP` |

## 2. 500.com 分析子页面（curl可直接抓取）

### 数据分析页 (shuju)
- URL: `https://odds.500.com/fenxi/shuju-{fixtureid}.shtml`
- 编码: GB2312
- 可提取数据:
  - ✅ 近期战绩：主客队近10场胜平负、进球/失球数、胜率、赢盘率、大球率
  - ✅ 交锋记录：双方近N次交战，胜平负分布、进失球
  - ✅ FIFA世界排名：双方排名、排名变化、积分
  - ✅ 澳门心水推荐：近况走势(WWLDWW)、盘路赢输、推介方向、文字分析
  - ✅ 未来赛程：可推算休息天数
  - ⚠️ 预计阵容/伤停：经常为空，赛前1-2天可能更新

### 亚盘分析页 (yazhi)
- URL: `https://odds.500.com/fenxi/yazhi-{fixtureid}.shtml`
- 可提取数据:
  - ✅ 各公司亚盘初盘/即时盘口
  - ✅ 盘口变化趋势（升盘/降盘）
  - ✅ 水位变化
  - 重点看：澳门、威廉希尔、Bet365等主流公司

### 欧赔分析页 (ouzhi)
- URL: `https://odds.500.com/fenxi/ouzhi-{fixtureid}.shtml`
- 可提取数据:
  - ✅ 各公司欧赔初赔/即时赔
  - ✅ 凯利指数
  - ✅ 赔率变化趋势
  - ✅ 即时概率（换算胜平负概率）
  - 注意：公司名被星号遮掩（如"威\*\*尔"=威廉希尔，"\*\*t3\*5"=Bet365），需推断识别

## 3. 懂球帝 API（阵容与球队信息，可直接curl）

**注意**：懂球帝的 `sport-data.dongqiudi.com` API可直接访问，无需浏览器。详细文档见第8节。

本节保留浏览器方式作为备用（API不可用时降级）。

### 浏览器备用方式
- **世界杯数据页**: `https://www.dongqiudi.com/data?cid=61` — 积分榜、球员榜、赛程
- **球队详情页**: `https://www.dongqiudi.com/team/{team_id}` — 新闻动态、近期赛程

### API直接调用（推荐）
- **球队阵容**: `curl sport-data.dongqiudi.com/soccer/biz/dqd/v1/team/member_v2/{team_id}?app=dqd&version=853&platform=ios&language=zh-cn`
- **球队信息**: `curl sport-data.dongqiudi.com/soccer/biz/dqd/team/sample/{team_id}?app=dqd&version=853&platform=ios&language=zh-cn`
- 自动化脚本：`python3 scripts/fetch_squad.py --team 西班牙`

### 懂球帝适用场景
- 获取完整26人名单（按门将/后卫/中场/前锋分组）
- 获取FIFA排名和总身价
- 交叉验证500.com的近期战绩数据

## 4. 体育资讯搜索（补充+交叉验证）

### 搜索关键词模板
- `"{球队名} 世界杯 伤病"` — 伤停信息
- `"{球队名} 世界杯 大名单"` — 阵容信息
- `"{主队} vs {客队} 交锋记录"` — 历史对战
- `"{球队名} 近期战绩"` — 状态评估
- `"世界杯 {日期} 赛程"` — 赛程安排

### 可信资讯源优先级
1. 500.com 资讯频道 (`zx.500.com`)
2. 懂球帝 (`dongqiudi.com`)
3. 新浪体育 (`sports.sina.com.cn`)
4. 腾讯体育
5. 搜狐体育

## 5. 数据验证规则

- SP赔率范围：1.01 ~ 99.99（超出视为异常）
- 让球数范围：-5 ~ +5（超出视为异常）
- 交锋记录数据：只能引用有明确来源的，禁止推测
- 伤停信息：必须来自赛前24小时内的报道，过期数据需标注时效
- nspf字段为空是正常现象（实力悬殊比赛不开售普通胜平负），不是数据抓取错误

## 6. curl抓取模板

```bash
# 抓取竞彩主页面
curl -s 'https://trade.500.com/jczq/' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  | iconv -f gb2312 -t utf-8

# 抓取赛事分析页
curl -s 'https://odds.500.com/fenxi/shuju-{fixtureid}.shtml' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  | iconv -f gb2312 -t utf-8

# 抓取亚盘分析页
curl -s 'https://odds.500.com/fenxi/yazhi-{fixtureid}.shtml' \
  -H 'User-Agent: Mozilla/5.0' \
  | iconv -f gb2312 -t utf-8

# 抓取欧赔分析页
curl -s 'https://odds.500.com/fenxi/ouzhi-{fixtureid}.shtml' \
  -H 'User-Agent: Mozilla/5.0' \
  | iconv -f gb2312 -t utf-8
```

## 7. 数据提取实战技巧

### 从数据页提取近期战绩

近期战绩以HTML表格形式存在，关键字段提取方式：

```python
# 提取近10场汇总
near10 = re.findall(r'近10场，(\d+胜\d+平\d+负\s+进\d+球\s+失\d+球\s+胜率\d+%\s+赢盘率\d+%\s+大球率\d+%)', text)

# 提取走势序列（胜平负）
# 页面中用 class="win"/"draw"/"lose" 的 span 标签表示
results = re.findall(r'<span class="[^"]*win[^"]*">胜</span>|<span class="[^"]*draw[^"]*">平</span>|<span class="[^"]*lose[^"]*">负</span>', text)
trend = ''.join(['胜' if 'win' in r else '平' if 'draw' in r else '负' for r in results])
```

### 从数据页提取FIFA排名

FIFA排名在"国际足联排名"section中，结构为表格：

```python
# 提取排名数字
rankings = re.findall(r'<td[^>]*class="td_sjpm">(\d+)</td>', text)
# rankings[0] = 主队最新排名, rankings[1] = 主队上期排名
# rankings[2] = 客队最新排名, rankings[3] = 客队上期排名
```

### 从亚盘页提取盘口信息

```python
# 提取主要公司的亚盘数据（第一行通常是威尔希尔/澳门的汇总行）
tables = re.findall(r'<table[^>]*class="[^"]*pub_table[^"]*"[^>]*>(.*?)</table>', text, re.DOTALL)
# 第一张表的第一数据行包含：水位↑/↓ | 盘口 | 水位↑/↓ | 更多
# 关键信息：盘口文字（如"两球半/三球"）、水位数字、升降箭头
```

### 从欧赔页提取赔率

```python
# 欧赔表：第一张表通常为竞彩官方赔率
# 格式：序号 | 公司名称 | 即时胜 | 即时平 | 即时负 | 初盘胜 | 初盘平 | 初盘负
# 竞彩官方赔率行公司名显示为"竞*官"
```

### 心水推荐抓取说明

澳门心水推荐section在比赛已截止后内容可能被清空。如需心水内容：
1. 优先从数据页HTML中提取（比赛未截止时有效）
2. 比赛已截止时，该section可能为空，标注"数据暂缺"即可
3. 不必为此浪费过多请求次数

### 综合提取工具

**推荐方式：使用 `scripts/fetch_analysis.py`（整页纯文本，LLM直接解析）**

```bash
# 默认：输出数据页完整纯文本，LLM直接读全文提取数据
python3 scripts/fetch_analysis.py --fixtureid ${fixtureid}

# 抓全部3个页面
python3 scripts/fetch_analysis.py --fixtureid ${fixtureid} --page all

# 单独抓亚盘/欧赔页
python3 scripts/fetch_analysis.py --fixtureid ${fixtureid} --page yazhi
python3 scripts/fetch_analysis.py --fixtureid ${fixtureid} --page ouzhi
```

脚本输出整页纯文本（已去HTML标签、解码实体、去导航噪音），不做板块切分。
LLM 直接在全文中语义提取所有数据，不需要代码预先按关键词切割。

**为什么不切分板块**：关键词切分本质是硬编码，网站改措辞就会断。LLM能在全文中找到任何数据，少一层预处理=少一个故障点。

**降级方案**：若脚本不可用，可用 curl 手动抓取原始HTML：

```bash
curl -s "https://odds.500.com/fenxi/shuju-${fixtureid}.shtml" \
  -H 'User-Agent: Mozilla/5.0' | iconv -f gb2312 -t utf-8 2>/dev/null
```

## 8. 懂球帝 API（阵容与球队信息）

### API 基础地址

```
https://sport-data.dongqiudi.com   # 主API（需正确的请求头）
https://www.dongqiudi.com           # 备用（同域名下也可访问）
```

### 必要请求头

```bash
-H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
-H 'Referer: https://www.dongqiudi.com/'
-H 'Origin: https://www.dongqiudi.com'
-H 'Accept: application/json'
```

### 通用查询参数

所有API请求需附加：
```
?app=dqd&version=853&platform=ios&language=zh-cn
```

### 核心端点

| 端点 | 用途 | 返回 |
|------|------|------|
| `/soccer/biz/dqd/v1/team/member_v2/{team_id}` | 球队阵容 | 26人名单，按门将/后卫/中场/前锋/教练分组 |
| `/soccer/biz/dqd/team/sample/{team_id}` | 球队信息 | FIFA排名、总身价、成立年份、主场 |
| `/soccer/biz/data/standing?competition_id=61` | 世界杯积分榜 | 分组排名 |

### 球队ID映射

懂球帝球队ID可通过以下方式获取：

1. **SSR页面**：访问 `https://www.dongqiudi.com/data?cid=61`，从 `__NUXT__` 返回块的 `standingsGroups` 提取
2. **脚本**：`python3 scripts/fetch_squad.py --list-teams`

常见世界杯球队ID（2026）：

| 球队 | ID |
|------|-----|
| 西班牙 | 1869 |
| 法国 | 789 |
| 英格兰 | 627 |
| 德国 | 868 |
| 葡萄牙 | 1540 |
| 乌拉圭 | 2026 |
| 比利时 | 需查询 |
| 伊朗 | 986 |
| 埃及 | 511 |
| 沙特阿拉伯 | 1640 |
| 佛得角 | 304 |
| 新西兰 | 1341 |

### 注意事项

- `member_v2` 的 `nationality_name` 字段实际存储的是球员**所属俱乐部名**，非国籍
- `sample` 的 `rank` 字段格式为 `"世界排名第X  总身价Y亿欧"`，需正则解析
- API无需认证，但缺少 `Referer` 或 `Origin` 头会返回403
- 建议请求间隔≥0.3秒，避免触发限流

### curl 模板

```bash
# 获取球队阵容
curl -s 'https://sport-data.dongqiudi.com/soccer/biz/dqd/v1/team/member_v2/1869?app=dqd&version=853&platform=ios&language=zh-cn' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  -H 'Referer: https://www.dongqiudi.com/' \
  -H 'Origin: https://www.dongqiudi.com' \
  -H 'Accept: application/json'

# 获取球队信息
curl -s 'https://sport-data.dongqiudi.com/soccer/biz/dqd/team/sample/1869?app=dqd&version=853&platform=ios&language=zh-cn' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  -H 'Referer: https://www.dongqiudi.com/' \
  -H 'Origin: https://www.dongqiudi.com' \
  -H 'Accept: application/json'
```

## 9. Wikipedia MediaWiki API（2026 世界杯大名单）

### 概述
维基百科的 `2026 FIFA World Cup squads` 页面包含所有 48+ 参赛队的最终 26 人名单、教练、年龄、出场数、进球数、所属俱乐部。这是**最权威的免费大名单来源**。

### 接入
- **端点**: `https://en.wikipedia.org/w/api.php`
- **方法**: `GET`
- **必要头**: `User-Agent`（必须自定义，默认 UA 被 Wikimedia 拒）
- **无需 API key**
- **数据格式**: wikitext（MediaWiki 标记语言）

### 核心端点
| 用途 | URL |
|------|-----|
| 抓 squads 页完整 wikitext | `?action=parse&page=2026_FIFA_World_Cup_squads&format=json&prop=wikitext` |
| 搜索页面 | `?action=query&list=search&srsearch=<keyword>&format=json` |

### 字段说明
每个球员包含：
- `no` — 球衣号码
- `pos` — 位置（GK / DF / MF / FW）
- `name` — 球员名（已剥去 wiki 链接）
- `caps` — 国家队出场数
- `goals` — 国家队进球数
- `club` — 所属俱乐部（已剥去 wiki 链接）
- `clubnat` — 俱乐部所在国（ISO 3 字母代码：ENG/ESP/GER/ITA/FRA 等）
- `birth_date` — 出生日期（ISO 格式）

附加：
- `position_distribution` — 位置分布统计（GK/DF/MF/FW 各多少人）
- `league_distribution` — 球员所在联赛分布（基于 clubnat 映射到 5 大联赛）

### 自动化脚本
`scripts/fetch_squad_wiki.py`

```bash
# 列出所有 48+ 参赛队
python3 scripts/fetch_squad_wiki.py --list-teams

# 抓法国队大名单
python3 scripts/fetch_squad_wiki.py --team France

# 抓沙特阿拉伯（注意多词国家名要加引号）
python3 scripts/fetch_squad_wiki.py --team "Saudi Arabia"

# 抓所有队概况（48+ 队位置/联赛分布）
python3 scripts/fetch_squad_wiki.py --all

# JSON 输出（用于 LLM 解析）
python3 scripts/fetch_squad_wiki.py --team France --json
```

### 在 POWER-6 模型中的角色

补 POWER-6 模型的「**阵容博弈**」维度（15%）。实际工作流：

1. `fetch_squad_wiki.py --team France` → 26 人名单 + 各自俱乐部
2. 对照 `fetch_xg.py` 反查每个球员的俱乐部 xG（仅 5 大联赛球员可得）
3. 看联赛分布：法国 8 人 Ligue 1 / 7 人 EPL = 阵容结构合理
4. 看位置分布：GK=3 / DF=9 / MF=7 / FW=7 = 标准配置
5. 与 500.com 的"伤停/缺阵"信息交叉对比

### 注意事项
- **自定义 User-Agent 是必须的**（含项目名和联系方式），否则被 Wikimedia 拒
- 国家队名是维基百科的英文写法：`France`, `Saudi Arabia`, `Bosnia and Herzegovina`
- 2026 世界杯后此页面会更新为归档状态，建议同时记录 `revid` 用于追踪
- 维基百科页面可能临时无法访问（Wikimedia 偶尔有事故），脚本需要加 retry

## 10. openfootball / football.json（公开赛事赛果）

### 概述
`openfootball/football.json` 是公共领域（CC0）的足球赛事数据仓库，提供 2010 年至今的 20+ 联赛赛程和赛果。**无 API key，无 rate limit，纯 GitHub raw URL**。

适合做**离线赛事 backup** 和**冷门联赛补全**（如奥地利、比利时、苏超、土超、希超、葡超、荷甲——这些 500.com 和懂球帝不覆盖）。

### 接入
- **端点**: `https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{code}.json`
- **方法**: `GET`
- **必要头**: 标准 User-Agent
- **无需 API key**
- **数据格式**: JSON

### 联赛代码
| 代码 | 联赛 |
|------|------|
| `en.1` | English Premier League |
| `en.2` | English Championship |
| `en.3` | English League One |
| `en.4` | English League Two |
| `de.1` | Deutsche Bundesliga |
| `de.2` | 2. Bundesliga |
| `es.1` | Spanish La Liga |
| `es.2` | Spanish Segunda División |
| `it.1` | Italian Serie A |
| `it.2` | Italian Serie B |
| `fr.1` | French Ligue 1 |
| `fr.2` | French Ligue 2 |
| `at.1` | Austrian Bundesliga |
| `be.1` | Belgian Jupiler Pro League |
| `pt.1` | Portuguese Primeira Liga |
| `sco.1` | Scottish Premiership |
| `tr.1` | Turkish Süper Lig |
| `gr.1` | Greek Super League |
| `nl.1` | Dutch Eredivisie |

### 数据格式
```json
{
  "name": "English Premier League 2024/25",
  "matches": [
    {
      "round": "Matchday 1",
      "date": "2024-08-17",
      "time": "12:30",
      "team1": "Ipswich Town FC",
      "team2": "Liverpool FC",
      "score": { "ft": [0, 2] }
    }
  ]
}
```

### 自动化脚本
`scripts/fetch_openfootball.py`

```bash
# 列出已知联赛代码
python3 scripts/fetch_openfootball.py --list-leagues

# 列出仓库所有赛季
python3 scripts/fetch_openfootball.py --list-seasons

# 抓 EPL 2024/25 完整赛程
python3 scripts/fetch_openfootball.py --league en.1 --season 2024-25

# 抓 Liverpool 已完赛的比赛
python3 scripts/fetch_openfootball.py --league en.1 --season 2024-25 --team Liverpool --played-only

# JSON 输出
python3 scripts/fetch_openfootball.py --league en.1 --season 2024-25 --team Liverpool --played-only --json
```

### 在 POWER-6 模型中的角色

补 POWER-6 模型的「**历史交锋/状态趋势**」维度（10%）。当 500.com 数据不完整时（如冷门联赛），用 openfootball 作为兜底赛果来源。

### 注意事项
- URL 中联赛代码**必须包含 `.json` 后缀**，脚本里已自动加
- 赛季是**起始年格式**：`2024-25` 是 24/25 赛季，`2025-26` 是 25/26 赛季
- 已完赛的 `score` 字段是 dict（`{ft: [home, away], ht: [home, away]}`）或 list，未完赛是空 list `[]`
- 球队名是**全名带 FC**（如 `Liverpool FC`），过滤时注意子串匹配
- 仓库是 CC0 公共领域，可自由使用和分发
