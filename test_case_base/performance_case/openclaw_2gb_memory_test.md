# OpenClaw 2GB 内存可用性测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-001 |
| 用例名称 | OpenClaw 2GB 内存可用性测试 |
| 优先级 | P0 (高) |
| 测试类型 | 性能测试 / 资源限制测试 |
| 创建日期 | 2026-06-01 |

## 测试目的

验证 OpenClaw 在内存限制为 2GB 的环境下是否能正常运行，包括：
- 基础功能可用性
- 消息处理能力
- WebSocket 连接稳定性
- 内存占用情况

## 前置条件

1. 测试环境内存限制为 2GB
2. OpenClaw 服务已部署
3. 压力测试客户端 (`automation_assets/client.js`) 已准备就绪
4. 监控工具（如 `htop` 或 `free -m`）可用

## 测试环境

| 配置项 | 要求 |
|--------|------|
| CPU | 2 核及以上 |
| 内存 | 限制为 2GB |
| 操作系统 | Linux (Ubuntu 20.04+) |
| Node.js | v18+ |
| OpenClaw | 待测版本 |

## 测试步骤

### 步骤 1：设置内存限制

```bash
# 使用 systemd 或 docker 限制内存为 2GB
# 方式一：Docker
sudo docker run -m 2g --memory-swap 2g openclaw:latest

# 方式二：systemd (在 service 文件中添加)
MemoryLimit=2G
```

### 步骤 2：启动 OpenClaw 服务

```bash
# 在受限环境中启动服务
openclaw start

# 检查服务状态
openclaw status
```

### 步骤 3：运行压力测试

```bash
cd automation_assets
node client.js
```

### 步骤 4：监控资源使用

在测试过程中，持续监控：

```bash
# 监控内存使用（每 5 秒刷新）
watch -n 5 free -m

# 监控 OpenClaw 进程内存占用
ps aux | grep openclaw
```

## 预期结果

| 检查项 | 预期结果 |
|--------|----------|
| 启动成功率 | 100% - OpenClaw 能正常启动 |
| WebSocket 连接 | 测试期间连接稳定，无断开 |
| 消息响应 | 平均延迟 < 500ms |
| 内存峰值 | 不超过 2GB 限制（建议 < 1.5GB） |
| OOM 情况 | 无 Out-Of-Memory 错误 |
| 测试完成率 | 完整的 60 秒测试能够正常结束 |

## 通过标准

- ✅ OpenClaw 在 2GB 内存下能正常启动和运行
- ✅ Websocket 压力测试成功率 ≥ 95%
- ✅ 无内存溢出或崩溃
- ✅ 平均响应时间在可接受范围内

## 失败标准

- ❌ 启动失败或启动时间 > 60 秒
- ❌ 测试过程中出现 OOM Killer 终止进程
- ❌ WebSocket 连接频繁断开
- ❌ 成功率 < 90%

## 相关脚本

- 压力测试客户端：`../../automation_assets/client.js`
- 压力测试服务端：`参考 week1_progress_report.md 中的 server.js`

## 备注

- 如果测试在 Docker 中进行，请确保容器内存限制设置为 2GB
- 建议在裸金属环境和容器环境各测试一次
- 记录内存使用峰值和服务响应时间
