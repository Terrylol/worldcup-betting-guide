# 报告 JSON Schema 与生成流程

## 输出报告

**核心原则：JSON是唯一数据源，HTML和文本都是JSON的渲染结果。**

#### 执行流程：

1. **分析过程中**，将每场赛事的数据按JSON Schema写入文件 `report_data.json`
2. **分析完成后**，调用 `scripts/generate_report.py` 生成报告
3. **告知用户**文件路径

```bash
# 查看JSON数据格式要求
python3 scripts/generate_report.py --schema

# 生成HTML+文本（默认）
python3 scripts/generate_report.py --data report_data.json -o worldcup_report_20260616

# 只生成HTML
python3 scripts/generate_report.py --data report_data.json -f html -o worldcup_report

# 只生成文本
python3 scripts/generate_report.py --data report_data.json -f text -o worldcup_report

# 管道输入
cat report_data.json | python3 scripts/generate_report.py -f html -o report
```

#### JSON Schema（必须严格遵循）：

```json
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
        {"name": "战力鸿沟", "weight": "×15%", "desc": "FIFA排名2 vs 67，S级碾压", "score": 9},
        {"name": "盘口密码", "weight": "×35%", "desc": "【凯利】...【概率】...【亚盘】...【返还率】...", "score": 8}
      ],
      "dims_summary": "六维证据链的中立总结，用于三专家决策层参考",
      "recommendation": "让球胜",
      "rec_sp": 1.46,
      "total_score": 67,
      "risk": "⚠️ 风险提示（为空则不显示）"
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
      "logic": "组合逻辑",
      "stars": "⭐⭐⭐⭐"
    }
  ]
}
```

**必填字段校验**：
- 顶层：`date`, `play_type`, `parlay_num`, `match_count`
- matches[]：`id`, `time`, `home`, `away`, `handicap`, `sp{胜平负}`, `tag`, `dims[]{name,weight,desc,score}`, `recommendation`, `rec_sp`, `total_score`
- parlays[]：`type`(safe/value/dark), `icon`, `title`, `sp`, `items[]{match,direction,sp}`, `logic`, `stars`

**可选字段**：
- `matches[].handicap_display` — 自动生成，也可手动指定覆盖
- `matches[].dims_summary` — POWER-6 六维证据链的中立总结，供三专家决策层引用
- `matches[].risk` — 风险提示，为空则不显示
- `parlays[].expert/persona/quote/focus` — 三专家方案展示字段；缺省时生成器按 `type` 自动填充

**tag 可选值**：碾压局 / 压制局 / 优势局 / 胶着局 / 均势局
**parlays type 可选值**：safe(稳妥) / value(价值) / dark(冷门)

#### 输出格式判断：

- 用户说"生成网页"/"输出HTML"/"做个页面" → `-f html`
- 用户说"输出文本"/"直接输出" → `-f text`
- 用户未指定 → **默认 `-f both`**，同时生成HTML和文本

#### 文本输出（备用，当无法运行脚本时）：
严格按以下模板输出，不得省略任何部分。

---
