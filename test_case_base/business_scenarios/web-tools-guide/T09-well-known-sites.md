# T09 — well-known-sites.json：站点索引查找

## 任务描述
读取 `well-known-sites.json`，找到 `search.baidu` 的 URL，组装搜索链接并访问。

## 预期决策路径
```
需要常用网站 URL？
  └─ YES → read {baseDir}/references/well-known-sites.json
          └─ 查找 key="search.baidu"
          └─ 替换 {query} 为实际搜索词
          └─ web_fetch(组装后的 URL)
```

## 执行步骤
1. `read {baseDir}/references/well-known-sites.json`
2. 查找 `search.baidu` → `https://www.baidu.com/s?wd={query}`
3. 替换 `{query}` 为 `OpenClaw` → `https://www.baidu.com/s?wd=OpenClaw`
4. `web_fetch` 抓取该 URL
5. 验证返回内容包含搜索结果

## 成功标准
- [ ] 成功读取 `well-known-sites.json`
- [ ] `search.baidu` 的 URL 正确解析（含 `{query}` 占位符）
- [ ] URL 组装正确（无编码错误）
- [ ] `web_fetch` 成功抓取搜索结果页
- [ ] 总耗时 ≤ 5s

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| 解析 URL | - |
| 组装后 URL | - |
| 抓取成功 | - |
| 错误 | - |
