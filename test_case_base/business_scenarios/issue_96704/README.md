# Issue #96704: Browser Cookie Persistence Bug

## 📋 目录说明

本目录包含 OpenClaw Bug #96704 的复现脚本、文档和结果。

## 🐛 Bug 信息

- **Bug ID**: #96704
- **标题**: Managed browser cookies never persist to disk (in-memory only) — login sessions lost on every browser/gateway restart
- **严重程度**: 高
- **影响**: 浏览器登录会话无法保持，每次重启后丢失

## 📁 文件列表

| 文件名 | 说明 |
|--------|------|
| `reproduce_cookie_bug_simple.sh` | 自动化复现脚本（bash） |
| `reproduce_cookie_bug.md` | 详细复现文档 |
| `reproduce_result.md` | 复现结果报告 |

## 🚀 快速开始

### 运行复现脚本

```bash
chmod +x reproduce_cookie_bug_simple.sh
./reproduce_cookie_bug_simple.sh
```

脚本会自动：
1. ✅ 检查浏览器状态
2. ✅ 访问测试网站产生 cookie
3. ✅ 检查 Cookie 数据库是否更新
4. ✅ **自动关闭浏览器**释放资源
5. ✅ 输出复现结果

### 查看文档

- **复现步骤**: 查看 `reproduce_cookie_bug.md`
- **复现结果**: 查看 `reproduce_result.md`

## 🔍 Bug 描述

OpenClaw 托管的浏览器通过 CDP 控制时，产生的 cookie 只存在于内存中，不会持久化到磁盘的 SQLite 数据库。

**导致问题**：
- ❌ 每次浏览器重启后，所有登录会话丢失
- ❌ 每次网关重启会杀掉浏览器子进程，导致会话完全丢失
- ❌ 依赖浏览器 SSO 的自动化任务无法无人值守运行

## ✅ 复现结果

已成功复现 Bug：
- ❌ Cookie 数据库文件大小无变化
- ❌ Cookie 数据库修改时间无更新
- ❌ 访问网站产生的 cookie 未持久化到磁盘

详细结果请查看 `reproduce_result.md`。

## 🔗 相关链接

- [Bug Report #96704](https://github.com/openclaw/openclaw/issues/96704)
- [Original Issue #15645](https://github.com/openclaw/openclaw/issues/15645)
- [chromedp Issue #818](https://github.com/chromedp/chromedp/issues/818)

## 🛠️ 建议修复

参考 Bug 报告的建议：
1. 实现 cookie 保存/恢复机制（浏览器启动时恢复，关闭时保存）
2. 添加定期刷新机制
3. 处理敏感信息保护

## 📝 测试环境

```
Browser: Chrome/147.0.7727.15
OpenClaw: 2026.6.10
OS: Linux 6.8.0-101-generic (x64)
Node: v22.22.2
```

---

**创建日期**: 2026-06-25  
**复现人**: 小机 (AI Assistant)
