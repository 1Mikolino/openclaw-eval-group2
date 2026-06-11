# T07 — browser 多步操作

## 任务描述
使用 `browser` 打开 GitHub 首页，点击 "Trending" 链接，截图当前页面。

## 预期决策路径
```
browser open github.com
  → snapshot（找到 Trending 链接）
  → act:click（点击 Trending）
  → 等待页面加载
  → screenshot（截图）
```

## 执行步骤
1. `browser action=open url=https://github.com`
2. `browser action=snapshot` 获取页面结构
3. 找到 Trending 链接（ref 或 CSS 选择器）
4. `browser action=act kind=click ref=...`
5. 等待页面加载完成
6. `browser action=screenshot` 截图

## 成功标准
- [ ] GitHub 首页成功打开
- [ ] Trending 链接被找到（snapshot 中有对应元素）
- [ ] 点击后页面跳转到 Trending
- [ ] 截图成功保存
- [ ] 总耗时 ≤ 45s

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| 打开成功 | - |
| 元素找到 | - |
| 点击成功 | - |
| 截图路径 | - |
| 错误 | - |
