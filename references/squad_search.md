# 阵容数据获取手册

## 数据源架构

```
懂球帝 API（主）──── 稳定、结构化、实时
    │
    ├─ member_v2/{team_id}  → 完整26人阵容（按位置分组）
    └─ sample/{team_id}     → 球队信息（FIFA排名、总身价）

懂球帝 SSR（备1）─── 用于获取球队ID与分组映射
    │
    └─ /data?cid=61 的 __NUXT__ return block

tvly 搜索（备2）──── 仅当API不可用时降级使用
    │
    └─ tvly search "2026世界杯 {球队} 大名单"
```

## 主数据源：懂球帝 API

### API 端点

| 端点 | 用途 | 示例 |
|------|------|------|
| `sport-data.dongqiudi.com/soccer/biz/dqd/v1/team/member_v2/{team_id}` | 阵容 | `{team_id}=1869` |
| `sport-data.dongqiudi.com/soccer/biz/dqd/team/sample/{team_id}` | 球队信息 | 同上 |

### 必要请求头

```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36
Referer: https://www.dongqiudi.com/
Origin: https://www.dongqiudi.com
Accept: application/json
```

### 通用查询参数

```
app=dqd&version=853&platform=ios&language=zh-cn
```

### member_v2 返回结构

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "type": "goalkeeper|defender|midfielder|attacker|coach",
        "data": [
          {
            "person_name": "亚马尔",
            "age": "18岁",
            "nationality_name": "巴塞罗那",  // 实际是所属俱乐部名
            "person_id": "...",
            "person_logo": "..."
          }
        ]
      }
    ]
  }
}
```

**注意**：`nationality_name` 字段在 member_v2 中存储的是球员**所属俱乐部名**，不是国籍。

### sample 返回结构

```json
{
  "team_name": "西班牙",
  "rank": "世界排名第2  总身价12.2亿欧",
  "venue_name": "伯纳乌球场",
  "venue_capacity": "85454",
  "founded": "1913",
  "country": "西班牙"
}
```

`rank` 字段含FIFA排名和总身价，需正则解析：
- 排名：`世界排名第(\d+)` → 提取数字
- 身价：`总身价([\d.]+亿欧|[\d.]+万欧)` → 提取金额

## 自动化脚本

`scripts/fetch_squad.py` 封装了上述所有API调用：

```bash
# 列出所有参赛队
python3 scripts/fetch_squad.py --list-teams

# 单队查询
python3 scripts/fetch_squad.py --team 西班牙

# 按组查询（推荐，一次获取4队）
python3 scripts/fetch_squad.py --group H

# JSON输出（供程序解析）
python3 scripts/fetch_squad.py --group H --json
```

脚本自动完成：
1. 从SSR获取球队ID → 分组映射
2. 调用 `sample` 获取FIFA排名、身价
3. 调用 `member_v2` 获取完整阵容
4. 识别五大联赛球员（★标记）
5. 统计各位置人数和五大联赛球员数

## 备选数据源：tvly 搜索

**仅在懂球帝API不可用时使用**（如API返回错误或超时）。

```bash
tvly search "2026世界杯 {球队} 大名单 阵容" --max-results 2
```

从搜索结果中提取：
- 26人名单核心球员
- 五大联赛球员数量（人工判断）
- 全队总身价
- 关键伤停/落选

## 阵容评级标准

| 评级 | 五大联赛球员 | 总身价 | 示例 |
|------|------------|--------|------|
| ⭐⭐⭐⭐⭐ | ≥15人 | ≥8亿欧 | 法国、西班牙、英格兰 |
| ⭐⭐⭐⭐ | 10~14人 | 4~8亿欧 | 乌拉圭、比利时 |
| ⭐⭐⭐ | 5~9人 | 1~4亿欧 | 伊朗、埃及 |
| ⭐⭐ | 1~4人 | 0.3~1亿欧 | 沙特阿拉伯、佛得角 |
| ⭐ | 0人 | <0.3亿欧 | 新西兰 |

## 五大联赛识别关键词

脚本内置以下关键词匹配球员所属俱乐部：

- **英超**：阿森纳、曼城、利物浦、切尔西、曼联、热刺
- **西甲**：巴塞罗那、皇家马德里、马德里竞技
- **德甲**：拜仁、多特蒙德、勒沃库森
- **意甲**：国际米兰、尤文图斯、AC米兰、那不勒斯
- **法甲**：巴黎圣日耳曼

**注意**：此列表不完整，部分五大联赛球队（如狼队、伯恩茅斯等）未被覆盖。
对于边界情况，分析时应人工补充判断。

## 数据来源标注规范

| 来源 | 标注格式 |
|------|---------|
| 懂球帝API | `懂球帝API(member_v2/sample)` |
| 懂球帝SSR | `懂球帝SSR(cid=61)` |
| tvly搜索 | `tvly搜索("{关键词}")` |

## 注意事项

1. **时效性**：阵容在赛前1~2周公布，API数据通常实时更新
2. **伤停信息**：API不直接提供伤停，需结合新闻搜索补充
3. **不确定处理**：如无伤停报道，标注"暂无重大伤停"，不杜撰
4. **降级策略**：API失败 → 重试3次 → 降级tvly搜索 → 标注"数据暂缺"
