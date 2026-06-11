# T03 — web_fetch：已知 URL 直取

## 任务描述
已知 URL `https://docs.openclaw.ai`，直接抓取页面内容。

## 预期决策路径
```
有明确 URL？
  └─ YES → 静态内容？
              └─ YES → web_fetch(url)
                    └─ 成功
```

## 执行步骤
1. Agent 判断：有 URL → 静态内容 → `web_fetch`
2. 传入 `https://docs.openclaw.ai`
3. 返回页面 Markdown 内容摘要

## 成功标准
- [ ] HTTP 200 成功
- [ ] 返回内容非空（≥ 100 字）
- [ ] 内容包含「OpenClaw」或「Gateway」
- [ ] 耗时 ≤ 3s

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| 耗时 | - |
| 内容长度 | - |
| 错误 | - |
