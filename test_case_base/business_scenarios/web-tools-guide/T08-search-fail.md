# T08 — web_search 失败处理：引导配置

## 任务描述
模拟 `web_search` 失败（无 Tavily API key 或 API 错误），验证 Agent 是否按 SKILL.md 要求引导用户配置搜索 API。

## 预期决策路径
```
web_search 失败（API 错误）？
  └─ YES → read {baseDir}/references/web-search-config.md
          └─ 原样输出配置引导表格给用户
          └─ 等待用户回复
                  └─ 用户拒绝 → 降级方案（opencli → browser）
```

## 执行步骤
1. 临时重命名 Tavily API key：`mv ~/.openclaw/.env ~/.openclaw/.env.bak`
2. 执行 `web_search("测试搜索")`
3. 验证 Agent 是否：
   - [ ] 读取 `web-search-config.md`
   - [ ] 原样输出配置引导（不改写表格）
   - [ ] 等待用户回复（不静默降级）
4. 恢复 API key：`mv ~/.openclaw/.env.bak ~/.openclaw/.env`

## 成功标准
- [ ] Agent 未静默降级到 `opencli` 或 `browser`
- [ ] 输出了配置引导内容
- [ ] 明确提示用户需要配置 API

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| 配置引导输出 | - |
| 是否静默降级 | - |
| 错误 | - |
