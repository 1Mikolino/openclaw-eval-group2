# T02 — web_search → web_fetch：搜索后抓取

## 任务描述
搜索「OpenClaw 文档」，对第一个结果 URL 执行 `web_fetch` 抓取页面内容。

## 预期决策路径
```
无 URL？
  └─ YES → web_search("OpenClaw 文档")
        └─ 成功 → 取 results[0].url
              └─ 静态内容？
                    └─ YES → web_fetch(url)
                          └─ 成功
```

## 执行步骤
1. `web_search("OpenClaw 文档")`
2. 取 `results[0].url`（预期 `https://docs.openclaw.ai`）
3. `web_fetch(url)` 抓取内容
4. 返回页面摘要（前 200 字）

## 成功标准
- [ ] web_search 返回 ≥ 1 条结果
- [ ] web_fetch 成功抓取（HTTP 200）
- [ ] 抓取内容包含「OpenClaw」关键词
- [ ] 总耗时 ≤ 10s

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| 搜索耗时 | - |
| 抓取耗时 | - |
| 总耗时 | - |
| 错误 | - |
