# T06 — browser：打开页面获取标题

## 任务描述
使用 `browser` 工具打开 `https://news.ycombinator.com`，获取页面标题和前 3 条内容摘要。

## 预期决策路径
```
web_fetch 失败？
  └─ YES → browser open URL
        └─ snapshot → 提取标题和内容
```

## 执行步骤
1. `browser action=open url=https://news.ycombinator.com`
2. 等待页面加载完成
3. `browser action=snapshot` 获取页面内容
4. 提取 `<title>` 和前 3 条 HN 故事标题

## 成功标准
- [ ] 页面成功打开（无 timeout）
- [ ] 获取到页面标题（包含「Hacker News」）
- [ ] 提取到 ≥ 3 条内容摘要
- [ ] 耗时 ≤ 30s

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| 页面标题 | - |
| 内容条数 | - |
| 耗时 | - |
| 错误 | - |
