# OpenClaw 心跳增加后性能稳定性测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-003 |
| 用例名称 | OpenClaw 心跳增加后性能稳定性测试 |
| 优先级 | P0 (高) |
| 测试类型 | 压力测试 / 异常检测测试 |
| 创建日期 | 2026-06-05 |

## 测试目的

验证 OpenClaw 在心跳（heartbeat）频率增加后是否引发以下异常行为：
- **CPU 飙升**：心跳处理导致 CPU 使用率异常增长
- **日志风暴**：频繁心跳产生过量日志输出
- **Retry Storm**：心跳失败触发无限重试循环
- **Gateway 不可用**：心跳压力导致 Gateway 服务崩溃或停止响应

## 前置条件

1. OpenClaw 服务已部署并可正常访问
2. 具备修改 OpenClaw 心跳配置的能力
3. 压力测试客户端 (`automation_assets/client.js`) 已准备就绪
4. 系统监控工具已配置（CPU、内存、日志、进程监控）
5. Gateway 日志路径可访问（默认：`~/.openclaw/logs/` 或 `/var/log/openclaw/`）

## 测试环境

| 配置项 | 要求 |
|--------|------|
| CPU | 4 核及以上 |
| 内存 | 8GB 及以上 |
| 磁盘空间 | 10GB+ 可用空间 |
| 操作系统 | Linux (Ubuntu 20.04+) |
| Node.js | v18+ |
| OpenClaw | 待测版本 |
| 监控工具 | `vmstat`, `iostat`, `tail`, `wc`, `grep` |

## 测试步骤

### 步骤 1：环境准备与基线采集

```bash
# 1. 创建监控目录
mkdir -p ~/heartbeat_test/monitoring

# 2. 记录测试开始时间和初始状态
echo "测试开始时间: $(date '+%Y-%m-%d %H:%M:%S')" > ~/heartbeat_test/baseline.log
echo "初始系统状态:" >> ~/heartbeat_test/baseline.log

# 3. 采集基线数据（正常心跳配置下）
echo "=== CPU 基线 ===" >> ~/heartbeat_test/baseline.log
vmstat 1 5 >> ~/heartbeat_test/baseline.log

echo "=== 内存基线 ===" >> ~/heartbeat_test/baseline.log
free -h >> ~/heartbeat_test/baseline.log

echo "=== 进程基线 ===" >> ~/heartbeat_test/baseline.log
ps aux | grep -E "openclaw|PID" | grep -v grep >> ~/heartbeat_test/baseline.log

echo "=== 日志文件大小基线 ===" >> ~/heartbeat_test/baseline.log
du -sh ~/.openclaw/logs/* 2>/dev/null || du -sh /var/log/openclaw/* 2>/dev/null || echo "日志路径未找到" >> ~/heartbeat_test/baseline.log

# 4. 记录当前心跳配置
echo "=== 原始心跳配置 ===" >> ~/heartbeat_test/baseline.log
grep -r "heartbeat" ~/.openclaw/config/ 2>/dev/null || echo "配置路径: ~/.openclaw/config/" >> ~/heartbeat_test/baseline.log
```

### 步骤 2：修改心跳配置（增加心跳频率）

```bash
# 备份原始配置
cp ~/.openclaw/config/gateway.yaml ~/.openclaw/config/gateway.yaml.bak 2>/dev/null

# 修改心跳配置 - 增加心跳频率（示例配置）
# 注意：根据实际 OpenClaw 版本调整配置路径和格式

cat > /tmp/heartbeat_patch.yaml << 'EOF'
# 高频心跳测试配置
agents:
  heartbeat:
    enabled: true
    interval: 1000        # 心跳间隔：1000ms（原默认可能为 30000ms）
    timeout: 500          # 心跳超时：500ms
    retries: 5            # 重试次数
    retryInterval: 500    # 重试间隔：500ms

# 启用更多调试日志（用于检测日志风暴）
logging:
  level: debug
  maxSize: 100MB
  maxFiles: 10
EOF

echo "已生成高频心跳配置补丁"
echo "请根据实际 OpenClaw 配置格式，将心跳间隔从默认 30s 调整为 1s"
```

### 步骤 3：重启服务并启动监控

```bash
# 1. 停止现有服务
openclaw stop 2>/dev/null
sleep 3

# 2. 清理旧日志（可选，便于观察新日志）
rm -f ~/.openclaw/logs/*.log 2>/dev/null

# 3. 启动服务
openclaw start
sleep 5

# 4. 验证服务状态
openclaw status > ~/heartbeat_test/service_start.log 2>&1

# 5. 启动后台监控脚本
cat > ~/heartbeat_test/monitor.sh << 'MONITOR_EOF'
#!/bin/bash
# 心跳压力测试监控脚本

LOG_DIR=~/heartbeat_test/monitoring
INTERVAL=2  # 每 2 秒采集一次（高频检测）
DURATION=300  # 监控 5 分钟

mkdir -p $LOG_DIR

echo "监控开始: $(date)" > $LOG_DIR/monitor.log
echo "timestamp,cpu_idle,cpu_us,cpu_sy,cpu_wa,mem_free,mem_used,openclaw_cpu,openclaw_mem,gateway_pid" > $LOG_DIR/resource.csv

# 获取 Gateway PID
get_gateway_pid() {
    pgrep -f "openclaw.*gateway" | head -1
}

for ((i=0; i<$DURATION; i+=INTERVAL)); do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # CPU 和内存统计 (vmstat)
    VMSTAT=$(vmstat 1 2 | tail -1)
    CPU_IDLE=$(echo $VMSTAT | awk '{print $15}')
    CPU_US=$(echo $VMSTAT | awk '{print $13}')
    CPU_SY=$(echo $VMSTAT | awk '{print $14}')
    CPU_WA=$(echo $VMSTAT | awk '{print $16}')
    
    # 内存信息
    MEM_INFO=$(free -m | grep "Mem:")
    MEM_FREE=$(echo $MEM_INFO | awk '{print $4}')
    MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
    
    # OpenClaw 进程信息
    GATEWAY_PID=$(get_gateway_pid)
    if [ -n "$GATEWAY_PID" ]; then
        OPENCLAW_INFO=$(ps -p $GATEWAY_PID -o %cpu,%mem --no-headers 2>/dev/null)
        OPENCLAW_CPU=$(echo $OPENCLAW_INFO | awk '{print $1}')
        OPENCLAW_MEM=$(echo $OPENCLAW_INFO | awk '{print $2}')
    else
        OPENCLAW_CPU="N/A"
        OPENCLAW_MEM="N/A"
        GATEWAY_PID="DEAD"
        echo "$TIMESTAMP: ALERT - Gateway 进程不存在！" >> $LOG_DIR/alerts.log
    fi
    
    # 写入 CSV
    echo "$TIMESTAMP,$CPU_IDLE,$CPU_US,$CPU_SY,$CPU_WA,$MEM_FREE,$MEM_USED,$OPENCLAW_CPU,$OPENCLAW_MEM,$GATEWAY_PID" >> $LOG_DIR/resource.csv
    
    # 实时检测 CPU 飙升（>80% 持续 10 秒则报警）
    if [ "$OPENCLAW_CPU" != "N/A" ] && (( $(echo "$OPENCLAW_CPU > 80" | bc -l 2>/dev/null || echo 0) )); then
        echo "$TIMESTAMP: WARNING - Gateway CPU 使用率 $OPENCLAW_CPU%" >> $LOG_DIR/alerts.log
    fi
    
    sleep $INTERVAL
done

echo "监控结束: $(date)" >> $LOG_DIR/monitor.log
MONITOR_EOF

chmod +x ~/heartbeat_test/monitor.sh
nohup ~/heartbeat_test/monitor.sh > ~/heartbeat_test/monitor_nohup.log 2>&1 &

# 6. 启动日志监控（检测日志风暴）
cat > ~/heartbeat_test/log_monitor.sh << 'LOG_EOF'
#!/bin/bash
# 日志风暴检测脚本

LOG_DIR=~/heartbeat_test/monitoring
INTERVAL=10  # 每 10 秒检测一次日志增长
DURATION=300

mkdir -p $LOG_DIR
LOG_PATHS=("~/.openclaw/logs/gateway.log" "/var/log/openclaw/gateway.log" "~/.openclaw/logs/out.log")

echo "timestamp,log_file,lines_delta,lines_total,size_delta_bytes,size_total" > $LOG_DIR/log_growth.csv

for ((i=0; i<$DURATION; i+=INTERVAL)); do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    for LOG_PATH in "${LOG_PATHS[@]}"; do
        LOG_FILE=$(eval echo $LOG_PATH)
        if [ -f "$LOG_FILE" ]; then
            CURRENT_LINES=$(wc -l < "$LOG_FILE")
            CURRENT_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
            
            # 计算增长（与上一次比较）
            if [ -f "$LOG_DIR/last_${LOG_FILE##*/}.count" ]; then
                LAST_LINES=$(cat "$LOG_DIR/last_${LOG_FILE##*/}.count")
                LAST_SIZE=$(cat "$LOG_DIR/last_${LOG_FILE##*/}.size")
                DELTA_LINES=$((CURRENT_LINES - LAST_LINES))
                DELTA_SIZE=$((CURRENT_SIZE - LAST_SIZE))
                
                # 检测日志风暴：10秒内新增超过1000行
                if [ $DELTA_LINES -gt 1000 ]; then
                    echo "$TIMESTAMP: ALERT - 日志风暴检测！$LOG_FILE 在 ${INTERVAL}秒内新增 $DELTA_LINES 行" >> $LOG_DIR/alerts.log
                fi
                
                echo "$TIMESTAMP,$LOG_FILE,$DELTA_LINES,$CURRENT_LINES,$DELTA_SIZE,$CURRENT_SIZE" >> $LOG_DIR/log_growth.csv
            fi
            
            # 保存当前值
            echo $CURRENT_LINES > "$LOG_DIR/last_${LOG_FILE##*/}.count"
            echo $CURRENT_SIZE > "$LOG_DIR/last_${LOG_FILE##*/}.size"
        fi
    done
    
    sleep $INTERVAL
done
LOG_EOF

chmod +x ~/heartbeat_test/log_monitor.sh
nohup ~/heartbeat_test/log_monitor.sh > ~/heartbeat_test/log_monitor_nohup.log 2>&1 &

echo "监控脚本已启动，PID: $(pgrep -f 'monitor.sh')"
```

### 步骤 4：运行压力测试

```bash
cd automation_assets

# 使用配置运行测试（高频心跳 + 压力测试）
node client.js --config ../test_case_base/performance_case/heartbeat-spike-config.json

# 或使用命令行参数直接运行
# node client.js \
#   --target ws://10.0.12.4:8080 \
#   --duration 300 \
#   --interval 50 \
#   --concurrent 50 \
#   --reportInterval 1000 \
#   --logFile ~/heartbeat_test/client.log
```

### 步骤 5：检测异常行为

在测试运行期间，实时监控以下指标：

```bash
# 1. 实时查看 CPU 使用率
watch -n 1 "ps aux | grep -E 'openclaw|PID' | grep -v grep"

# 2. 查看日志增长速率
watch -n 2 "wc -l ~/.openclaw/logs/*.log 2>/dev/null"

# 3. 检测重试日志（retry storm 指示器）
tail -f ~/.openclaw/logs/gateway.log 2>/dev/null | grep -i "retry\|reconnect\|heartbeat"

# 4. 检测错误日志激增
tail -f ~/.openclaw/logs/gateway.log 2>/dev/null | grep -i "error\|fail\|timeout"

# 5. 检查 Gateway 健康状态
curl -s http://localhost:8080/health 2>/dev/null || echo "Gateway 健康检查端点未响应"
```

### 步骤 6：收集结果与恢复环境

```bash
# 1. 等待测试完成
sleep 10

# 2. 停止监控脚本
pkill -f "heartbeat_test/monitor.sh"
pkill -f "heartbeat_test/log_monitor.sh"

# 3. 记录最终状态
echo "测试结束时间: $(date '+%Y-%m-%d %H:%M:%S')" > ~/heartbeat_test/final_status.log
echo "最终服务状态:" >> ~/heartbeat_test/final_status.log
openclaw status >> ~/heartbeat_test/final_status.log 2>&1

echo "=== 最终资源使用 ===" >> ~/heartbeat_test/final_status.log
ps aux | grep -E "openclaw|PID" | grep -v grep >> ~/heartbeat_test/final_status.log
free -h >> ~/heartbeat_test/final_status.log

echo "=== 最终日志统计 ===" >> ~/heartbeat_test/final_status.log
du -sh ~/.openclaw/logs/* 2>/dev/null >> ~/heartbeat_test/final_status.log
wc -l ~/.openclaw/logs/*.log 2>/dev/null >> ~/heartbeat_test/final_status.log

# 4. 恢复原始配置
mv ~/.openclaw/config/gateway.yaml.bak ~/.openclaw/config/gateway.yaml 2>/dev/null
echo "原始配置已恢复"

# 5. 重启服务恢复正常状态
openclaw restart
```

## 预期结果

| 检查项 | 预期结果（正常） | 异常指标 |
|--------|------------------|----------|
| CPU 使用率 | OpenClaw Gateway CPU < 30% 平均 | CPU > 80% 持续 30 秒 |
| 日志增长 | 正常速率，无异常激增 | 10秒内新增 >1000 行日志 |
| Retry 频率 | 偶尔重试，无连续失败 | 每秒 >10 次重试日志 |
| Gateway 可用性 | 健康检查 100% 通过 | 任何健康检查失败 |
| 内存使用 | 稳定增长，无泄漏 | 持续增长 >100MB/分钟 |
| 消息成功率 | ≥ 95% | < 90% |
| 响应延迟 | 平均 < 500ms | P99 > 2000ms |

## 通过标准

- ✅ Gateway CPU 使用率在正常范围内（平均 < 50%，峰值 < 80%）
- ✅ 无日志风暴（日志增长速率稳定，无 10 秒内 >1000 行的激增）
- ✅ 无 Retry Storm（重试日志频率正常，无无限循环迹象）
- ✅ Gateway 服务保持可用（健康检查通过率 100%）
- ✅ 消息发送成功率 ≥ 90%
- ✅ 内存使用无异常增长

## 失败标准

- ❌ **CPU 飙升**：Gateway CPU > 80% 持续超过 1 分钟
- ❌ **日志风暴**：单日志文件在 10 秒内新增超过 1000 行
- ❌ **Retry Storm**：检测到每秒超过 10 次重试日志，持续 30 秒以上
- ❌ **Gateway 不可用**：健康检查失败或服务崩溃
- ❌ **内存泄漏**：内存使用持续增长 >50MB/分钟
- ❌ **消息成功率**：< 85%

## 数据分析要点

### CPU 飙升分析
```bash
# 查看 CPU 使用趋势
cat ~/heartbeat_test/monitoring/resource.csv | tail -n +2 | awk -F',' '{print NR, 100-$2}' > cpu_usage.dat
# 绘制趋势图，检查是否存在持续高 CPU 时段

# 检测 CPU 峰值
awk -F',' 'NR>1 && $8>80 {print $1, $8"%"}' ~/heartbeat_test/monitoring/resource.csv
```

### 日志风暴分析
```bash
# 分析日志增长趋势
cat ~/heartbeat_test/monitoring/log_growth.csv | awk -F',' 'NR>1 {print $1, $3}' > log_growth.dat

# 统计错误日志数量
grep -ci "error\|fail\|exception" ~/.openclaw/logs/gateway.log 2>/dev/null

# 检测重复日志模式（可能的循环）
grep -i "heartbeat\|retry" ~/.openclaw/logs/gateway.log 2>/dev/null | sort | uniq -c | sort -rn | head -20
```

### Retry Storm 检测
```bash
# 统计重试相关日志频率
grep -i "retry\|reconnect\|attempt" ~/.openclaw/logs/gateway.log 2>/dev/null | \
  awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# 检测连续重试模式
awk '/retry|reconnect|attempt/{print NR}' ~/.openclaw/logs/gateway.log 2>/dev/null | \
  awk 'NR>1{diff=$1-prev; if(diff<5) print "连续重试，行间隔:", diff; prev=$1}'
```

### Gateway 可用性分析
```bash
# 检查服务重启次数
journalctl -u openclaw --since "5 minutes ago" 2>/dev/null | grep -c "Started\|Restarted"

# 检查进程崩溃迹象
grep -i "crash\|panic\|fatal\|killed" ~/.openclaw/logs/gateway.log 2>/dev/null
```

## 相关脚本

- 压力测试客户端：`../../automation_assets/client.js`
- 测试配置文件：`heartbeat-spike-config.json`
- 监控脚本：`~/heartbeat_test/monitor.sh`
- 日志监控脚本：`~/heartbeat_test/log_monitor.sh`

## 测试配置文件示例

创建 `heartbeat-spike-config.json`：
```json
{
  "_comment": "OpenClaw 心跳增加后性能测试 - 检测 CPU飙升/日志风暴/Retry Storm/Gateway不可用",
  "name": "openclaw-heartbeat-spike-test",
  "description": "验证高频心跳场景下的系统稳定性",
  
  "target": "ws://10.0.12.4:8080",
  "duration": 300,
  "interval": 50,
  "concurrent": 50,
  "messageType": "ping",
  
  "reportInterval": 1000,
  "verbose": true,
  "waitForWelcome": true,
  "welcomeTimeout": 5000,
  "reconnectOnDisconnect": true,
  
  "passCriteria": {
    "minSuccessRate": 90,
    "maxAvgLatency": 1000,
    "maxCpuUsage": 80,
    "maxLogGrowthRate": 100
  },
  
  "environment": {
    "heartbeatInterval": "1000ms",
    "cpu": "4 cores",
    "memory": "8GB",
    "os": "Ubuntu 20.04+"
  }
}
```

## 注意事项

1. **测试前备份配置** - 心跳配置修改前务必备份原始配置
2. **监控磁盘空间** - 高频日志可能快速填满磁盘，确保有足够空间
3. **准备快速恢复** - 如检测到严重问题，立即停止测试并恢复配置
4. **检查日志级别** - 测试时建议开启 debug 级别日志以捕获完整信息
5. **区分心跳类型** - 确认是 Gateway 心跳、Agent 心跳还是客户端心跳
6. **测试后清理** - 测试完成后删除临时监控文件和备份配置

## 快速问题诊断

| 现象 | 可能原因 | 检查命令 |
|------|----------|----------|
| CPU 持续高位 | 心跳处理逻辑阻塞 | `top -p $(pgrep -f openclaw)` |
| 日志暴增 | 心跳循环触发日志输出 | `tail -f ~/.openclaw/logs/gateway.log \| pv -l > /dev/null` |
| 连接频繁断开 | 心跳超时配置过短 | `grep -i timeout ~/.openclaw/logs/*.log` |
| Gateway 无响应 | 死锁或资源耗尽 | `curl http://localhost:8080/health` |

## 扩展测试

- **不同心跳间隔测试**：测试 500ms、1s、5s、10s、30s 不同间隔的表现
- **多 Agent 并发心跳**：同时启动多个 Agent 进行心跳测试
- **网络抖动场景**：模拟网络延迟和丢包对心跳的影响
- **长时间压力测试**：结合 24h 稳定性测试进行心跳压力验证

---

**测试记录模板：**

| 时间 | 心跳间隔 | CPU% | 日志行数/10s | Retry次数 | Gateway状态 | 备注 |
|------|----------|------|--------------|-----------|-------------|------|
| T+0 | 30s | | | | ✅ 正常 | 基线 |
| T+1m | 1s | | | | | 高频心跳开始 |
| T+5m | 1s | | | | | 测试结束 |
