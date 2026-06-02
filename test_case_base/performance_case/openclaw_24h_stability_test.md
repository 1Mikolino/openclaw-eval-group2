# OpenClaw 24小时长时间运行稳定性测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-002 |
| 用例名称 | OpenClaw 24小时长时间运行稳定性测试 |
| 优先级 | P0 (高) |
| 测试类型 | 稳定性测试 / 耐久性测试 |
| 创建日期 | 2026-06-02 |

## 测试目的

验证 OpenClaw 在连续运行24小时的高负载场景下是否能保持稳定的性能和可用性，包括：
- 长时间运行下的内存泄漏检测
- WebSocket 连接稳定性（长时间保持连接）
- CPU 和内存资源占用趋势
- 消息处理能力随时间的变化
- 偶发的连接断开和重连能力
- 日志文件增长和磁盘使用情况

## 前置条件

1. 测试环境稳定，能连续运行24小时以上
2. OpenClaw 服务已部署并可正常访问
3. 压力测试客户端 (`automation_assets/client.js`) 已准备就绪，支持长时间运行模式
4. 监控工具已配置（内存、CPU、磁盘、网络）
5. 日志收集和轮转机制已配置

## 测试环境

| 配置项 | 要求 |
|--------|------|
| CPU | 4 核及以上 |
| 内存 | 8GB 及以上 |
| 磁盘空间 | 20GB+ 可用空间（用于日志） |
| 操作系统 | Linux (Ubuntu 20.04+) |
| Node.js | v18+ |
| OpenClaw | 待测版本 |
| 网络 | 稳定的内网连接 |

## 测试步骤

### 步骤 1：环境准备

```bash
# 1. 检查系统资源
free -h
df -h
cat /proc/cpuinfo | grep "processor" | wc -l

# 2. 配置日志轮转（避免磁盘占满）
# 编辑 /etc/logrotate.d/openclaw 或配置 PM2 日志轮转
cat > /etc/logrotate.d/openclaw << 'EOF'
/var/log/openclaw/*.log {
    hourly
    rotate 48
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

# 3. 清理历史日志
rm -rf /var/log/openclaw/*.log >/dev/null 2>&1

# 4. 启动系统监控（后台运行）
mkdir -p ~/monitoring
nohup vmstat 60 > ~/monitoring/vmstat.log 2>&1 &
nohup iostat -x 60 > ~/monitoring/iostat.log 2>&1 &
```

### 步骤 2：启动 OpenClaw 服务

```bash
# 清除缓存，确保干净启动
openclaw stop 2>/dev/null
sleep 2

# 记录启动时间和初始状态
echo "OpenClaw 启动时间: $(date '+%Y-%m-%d %H:%M:%S')" > ~/monitoring/test_start.log

# 启动服务
openclaw start

# 等待服务完全启动
sleep 10

# 验证服务状态
openclaw status

# 记录初始资源占用
ps aux | grep openclaw | grep -v grep >> ~/monitoring/test_start.log
echo "初始内存使用:" >> ~/monitoring/test_start.log
free -h >> ~/monitoring/test_start.log
```

### 步骤 3：启动24小时压力测试

```bash
cd automation_assets

# 使用配置文件运行长时间测试
node client.js --config ../test_case_base/performance_case/24h-stability-config.json

# 或使用命令行参数
# node client.js \
#   --target ws://10.0.12.4:8080 \
#   --duration 86400 \
#   --interval 500 \
#   --reportInterval 1000 \
#   --reconnectOnDisconnect \
#   --logFile ~/monitoring/client.log
```

### 步骤 4：持续监控（测试期间执行）

创建监控脚本 `~/monitoring/monitor.sh`：

```bash
#!/bin/bash
# 24小时监控脚本

LOG_DIR=~/monitoring
INTERVAL=300  # 每5分钟记录一次
DURATION=86400  # 24小时

mkdir -p $LOG_DIR

echo "开始监控: $(date)" > $LOG_DIR/monitor.log

for ((i=0; i<$DURATION; i+=$INTERVAL)); do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    ELAPSED_HOURS=$((i / 3600))
    
    echo "=== $TIMESTAMP (运行 ${ELAPSED_HOURS} 小时) ===" >> $LOG_DIR/monitor.log
    
    # OpenClaw 进程信息
    echo "[OpenClaw 进程]" >> $LOG_DIR/monitor.log
    ps aux | grep -E "openclaw|PID" | grep -v grep >> $LOG_DIR/monitor.log
    
    # 内存使用
    echo "[内存使用]" >> $LOG_DIR/monitor.log
    free -h >> $LOG_DIR/monitor.log
    
    # 系统负载
    echo "[系统负载]" >> $LOG_DIR/monitor.log
    uptime >> $LOG_DIR/monitor.log
    
    # 磁盘使用
    echo "[磁盘使用]" >> $LOG_DIR/monitor.log
    df -h >> $LOG_DIR/monitor.log
    
    # 文件描述符
    echo "[文件描述符]" >> $LOG_DIR/monitor.log
    ls /proc/$(pgrep -f "openclaw.*gateway" | head -1)/fd 2>/dev/null | wc -l >> $LOG_DIR/monitor.log 2>&1 || echo "N/A" >> $LOG_DIR/monitor.log
    
    echo "" >> $LOG_DIR/monitor.log
    
    # 每小时输出一次摘要到控制台
    if [ $((i % 3600)) -eq 0 ]; then
        echo "[$TIMESTAMP] 已运行 ${ELAPSED_HOURS} 小时，监控正常" | tee -a $LOG_DIR/hourly_summary.log
    fi
    
    sleep $INTERVAL
done

echo "监控结束: $(date)" >> $LOG_DIR/monitor.log
```

执行监控脚本：
```bash
chmod +x ~/monitoring/monitor.sh
nohup ~/monitoring/monitor.sh > ~/monitoring/monitor_nohup.log 2>&1 &
```

### 步骤 5：优雅结束测试

24小时后，记录停止时间并收集结果：

```bash
# 等待测试自动结束，或手动停止

# 记录停止信息
echo "OpenClaw 停止时间: $(date '+%Y-%m-%d %H:%M:%S')" > ~/monitoring/test_end.log
echo "最终状态:" >> ~/monitoring/test_end.log
openclaw status >> ~/monitoring/test_end.log 2>&1

# 最终资源占用
ps aux | grep openclaw | grep -v grep >> ~/monitoring/test_end.log
echo "最终内存使用:" >> ~/monitoring/test_end.log
free -h >> ~/monitoring/test_end.log

# 停止监控脚本
pkill -f "monitor.sh"
```

## 预期结果

| 检查项 | 预期结果 |
|--------|----------|
| 24小时完成率 | 测试能完整运行24小时不中断 |
| 服务可用性 | 服务在24小时内保持可用，无崩溃 |
| WebSocket 连接 | 连接稳定，自动重连成功率 ≥ 99% |
| 消息成功率 | 消息发送成功率 ≥ 95% |
| 内存增长 | 内存使用无持续增长趋势（泄漏检测） |
| 内存峰值 | 不超过环境限制的 80% |
| 平均延迟 | 保持在 < 500ms（后期不劣化） |
| P99 延迟 | 不超过平均延迟的 3 倍 |
| CPU 使用 | 平均 < 50%，峰值 < 80% |
| 日志增长 | 日志文件正常轮转，无磁盘占满 |

## 通过标准

- ✅ 完整运行24小时，无服务崩溃
- ✅ 消息成功率 ≥ 95%
- ✅ 内存使用无明显增长趋势（斜率 < 10MB/小时）
- ✅ 平均响应时间 < 500ms 且趋势稳定或下降
- ✅ 无 Out-Of-Memory 错误
- ✅ WebSocket 连接大部分时间保持成功

## 失败标准

- ❌ 服务在测试期间崩溃或停止响应
- ❌ 内存持续增长，疑似内存泄漏
- ❌ 响应时间随测试进行显著劣化（增长 > 200%）
- ❌ CPU 使用率持续高位（>80% 超过30分钟）
- ❌ 消息成功率 < 90%
- ❌ 磁盘空间被日志占满导致服务异常

## 数据分析要点

### 内存泄漏检测
```bash
# 分析内存使用趋势
grep "Mem:" ~/monitoring/monitor.log | awk '{print NR, $3}' > mem_usage.dat
# 使用工具绘制趋势图或计算增长率
```

### 性能趋势分析
```bash
# 提取各时间点的延迟数据
# 检查平均延迟、P95、P99 是否随时间增加
```

### 连接稳定性分析
```bash
# 统计断开和重连次数
grep -c "disconnected\|reconnect" ~/monitoring/client.log
grep -c "connected" ~/monitoring/client.log
```

## 相关脚本

- 压力测试客户端：`../../automation_assets/client.js`
- 测试配置文件：`24h-stability-config.json`
- 监控脚本：参考上文 `monitor.sh`

## 注意事项

1. **测试期间请勿重启服务** - 这会破坏测试的连续性
2. **提前配置日志轮转** - 24小时日志可能非常大
3. **确保网络稳定** - 测试环境网络中断会影响结果
4. **预留足够磁盘空间** - 建议预留 20GB+
5. **建议使用 screen/tmux** - 防止 SSH 断连导致测试中断
6. **定时检查** - 建议每 6 小时人工检查一次状态
7. **准备应急预案** - 如发现严重问题可提前停止测试

## 扩展测试（可选）

- **48小时测试**：验证更长周期稳定性
- **内存泄漏专项**：结合 heap dump 分析
- **逐步加压测试**：24小时内分阶段增加负载

---

**测试记录模板：**

| 时间点 | 内存使用 | CPU% | 平均延迟 | 成功率 | 备注 |
|--------|----------|------|----------|--------|------|
| 0h | | | | | 初始状态 |
| 6h | | | | | |
| 12h | | | | | 中间状态 |
| 18h | | | | | |
| 24h | | | | | 最终状态 |
