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
