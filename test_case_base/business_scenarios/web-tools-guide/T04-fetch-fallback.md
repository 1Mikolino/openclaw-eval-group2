# T04 — web_fetch 失败 → opencli fallback

## 任务描述
尝试抓取 `https://news.ycombinator.com`，预期 `web_fetch` 可能因反爬/403 失败，触发 `opencli` 兜底。

## 预期决策路径
```
有明确 URL？
  └─ YES → web_fetch(url)
        └─ 失败（403/CAPTCHA）？
              └─ YES → opencli news.ycombinator.com
                    └─ 成功/失败记录
```

## 执行步骤
1. `web_fetch("https://news.ycombinator.com")`
2. 若返回 403/失败 → 执行 `opencli hn --help` 或对应命令
3. 记录两个工具的结果

## 成功标准
- [ ] web_fetch 明确失败（记录失败原因）
- [ ] Agent 主动切换到 opencli（或告知用户）
- [ ] 总耗时 ≤ 15s

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| web_fetch 结果 | - |
| opencli 可用 | - |
| 错误 | - |
