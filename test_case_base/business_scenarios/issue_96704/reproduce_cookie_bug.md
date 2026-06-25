# OpenClaw Browser Cookie Persistence Bug 复现文档

## Bug 信息

- **Bug ID**: #96704
- **标题**: Managed browser cookies never persist to disk (in-memory only) — login sessions lost on every browser/gateway restart
- **环境**: OpenClaw 2026.6.10, Chrome 147.0.7727.15
- **复现日期**: 2026-06-25

## Bug 描述

OpenClaw 托管的浏览器通过 Chrome DevTools Protocol (CDP) 控制时，产生的 cookie 只存在于内存中，不会持久化到磁盘的 SQLite 数据库。这导致：

1. 每次浏览器重启后，所有登录会话丢失
2. 每次网关重启（配置更新、SIGUSR1 等）会杀掉浏览器子进程，导致会话完全丢失
3. 依赖浏览器 SSO 的自动化任务无法无人值守运行

## 复现步骤

### 方法一：自动化脚本（推荐）

使用 `reproduce_cookie_bug_simple.sh` 脚本：

```bash
chmod +x reproduce_cookie_bug_simple.sh
./reproduce_cookie_bug_simple.sh
```

脚本会自动：
1. 检查浏览器状态
2. 启动浏览器（如果未运行）
3. 访问测试网站以产生 cookie
4. 检查 Cookie 数据库是否更新
5. **自动关闭浏览器**释放资源
6. 输出复现结果

### 方法二：手动验证

1. **记录初始状态**：
   ```bash
   ls -lh ~/.openclaw/browser-existing-session/Default/Cookies
   stat ~/.openclaw/browser-existing-session/Default/Cookies
   ```

2. **在浏览器中访问网站**：
   - 打开任意网站（如 https://www.baidu.com）
   - 等待页面加载完成

3. **检查数据库是否更新**：
   ```bash
   # 再次检查文件
   ls -lh ~/.openclaw/browser-existing-session/Default/Cookies
   stat ~/.openclaw/browser-existing-session/Default/Cookies
   ```

4. **对比结果**：
   - 如果文件大小和修改时间没有变化 → **Bug 已复现**
   - 如果文件已更新 → 可能未复现（但 CDP 设置的 cookie 仍有问题）

5. **验证重启后丢失**（可选）：
   ```bash
   openclaw browser stop
   sleep 2
   openclaw browser start
   # 检查登录状态是否保持
   ```

## 预期结果

### Bug 存在时：
- ❌ Cookie 数据库文件大小不变
- ❌ Cookie 数据库修改时间不更新
- ❌ 重启浏览器后登录状态丢失

### 正常情况应该是：
- ✓ Cookie 数据库文件大小增加
- ✓ Cookie 数据库修改时间更新为当前时间
- ✓ 重启浏览器后登录状态保持

## 根因分析

根据 bug 报告 #96704 和 chromedp/chromedp#818：

- Chrome 通过 CDP 控制时，不会将 cookie 刷新到磁盘的 SQLite 存储
- `Network.getAllCookies` 可以获取内存中的 cookie
- 但 `user-data/Default/Cookies` 保持为空或旧数据
- `Default/Network/Cookies` 从未创建

这是 Chrome CDP 行为的已知限制。

## 影响范围

- **自动化任务**: 每次都需要重新登录，无法无人值守
- **SSO/MFA**: 每次重启都会触发二次验证
- **用户体验**: 登录状态无法保持
- **开发调试**: 需要反复登录测试

## 建议修复方案

根据 #96704 的建议：

1. **实现 cookie 保存/恢复机制**：
   - 浏览器关闭时：通过 `Network.getAllCookies` 获取所有 cookie
   - 保存到侧面文件（per-profile sidecar）
   - 浏览器启动时：通过 `Network.setCookies` 恢复

2. **定期刷新机制**：
   - 定期保存 cookie 状态
   - 避免意外崩溃导致丢失

3. **敏感信息处理**：
   - Cookie 侧面文件应视为敏感数据
   - 需要适当的权限保护

## 相关文件

- `reproduce_cookie_bug_simple.sh` - 自动化复现脚本
- `reproduce_cookie_bug.py` - Python 版本复现脚本
- `check_cookie_status.sh` - 快速检查脚本
- `reproduce_result.md` - 复现结果记录

## 参考资料

- [Bug #96704](https://github.com/openclaw/openclaw/issues/96704)
- [原始 Bug #15645](https://github.com/openclaw/openclaw/issues/15645)
- [chromedp Issue #818](https://github.com/chromedp/chromedp/issues/818)

## 测试环境

```
Browser: Chrome/147.0.7727.15
Protocol-Version: 1.3
OpenClaw: 2026.6.10
OS: Linux 6.8.0-101-generic (x64)
Node: v22.22.2
```
