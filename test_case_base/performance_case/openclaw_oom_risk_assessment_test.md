# OpenClaw OOM 风险评估测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-005 |
| 用例名称 | OpenClaw OOM 风险评估测试 |
| 优先级 | P0 (阻断性) |
| 测试类型 | 风险评估 / 发布门禁测试 |
| 创建日期 | 2026-06-05 |
| 适用版本 | 待发布版本 |

## 测试目的

评估 OpenClaw 在当前版本中的 OOM（Out of Memory）风险，验证是否满足发布要求：
- **内存上限遵守**: 是否在配置内存限制内运行
- **渐进压力处理**: 面对渐进内存压力时的表现
- **边界安全**: 接近内存边界时的安全行为
- **优雅降级**: 内存不足时的优雅降级能力
- **恢复能力**: 内存释放后的恢复能力

## 发布通过标准

| 等级 | 要求 | 判定 |
|------|------|------|
| 🟢 **可发布** | 无OOM，内存可控，优雅处理压力 | 通过 |
| 🟡 **有条件发布** | 偶发OOM，但有工作规避方案 | 需评审 |
| 🔴 **阻断发布** | 频繁OOM，无法恢复，数据丢失 | 不通过 |

## 前置条件

1. 明确 OpenClaw 内存配置限制
2. 具备 cgroup 或容器内存限制环境
3. 具备 OOM 监控和日志收集能力
4. 具备服务健康检查端点
5. 准备内存填充工具（`stress`, `memtester` 或自定义脚本）

## 测试环境

| 配置项 | 要求 |
|--------|------|
| 内存限制 | 按生产配置（如 2GB / 4GB / 8GB） |
| CPU | 2 核及以上 |
| 监控工具 | `dmesg`, `journalctl`, `cgroup` 内存事件 |
| OOM Killer 配置 | 可调整 `vm.oom_kill_allocating_task` |
| 测试工具 | `stress-ng`, `memtester`, 自定义分配器 |

## 测试步骤

### 步骤 1：基线内存测试

```bash
# 1. 记录初始内存配置
echo "=== OOM 风险评估 - 基线测试 ===" > ~/oom_test/baseline.log
date >> ~/oom_test/baseline.log

# 2. 检查当前内存限制
echo "" >> ~/oom_test/baseline.log
echo "=== 系统内存配置 ===" >> ~/oom_test/baseline.log
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached" >> ~/oom_test/baseline.log

# 3. 检查 cgroup 内存限制（如果在容器中）
echo "" >> ~/oom_test/baseline.log
echo "=== Cgroup 内存限制 ===" >> ~/oom_test/baseline.log
cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo "无 cgroup 限制" >> ~/oom_test/baseline.log
cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null >> ~/oom_test/baseline.log

# 4. 记录 OpenClaw 初始状态
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
echo "" >> ~/oom_test/baseline.log
echo "=== OpenClaw 初始状态 (PID: $OPENCLAW_PID) ===" >> ~/oom_test/baseline.log
cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep -E "VmSize|VmRSS|VmData|VmPeak|VmHWM" >> ~/oom_test/baseline.log
```

### 步骤 2：渐进式内存压力测试

创建测试脚本 `~/oom_test/gradual_memory_test.sh`：

```bash
#!/bin/bash
# 渐进式内存压力测试

TEST_DURATION=1800  # 30分钟
LOG_DIR=~/oom_test/logs
mkdir -p $LOG_DIR

echo "=== 渐进式内存压力测试开始 ==="
echo "时间: $(date)"
echo "目标: 观察内存从基线到接近限制的表现"

OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
if [ -z "$OPENCLAW_PID" ]; then
    echo "错误: OpenClaw 未运行"
    exit 1
fi

# 获取内存限制（cgroup 或系统）
MEMORY_LIMIT=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null)
if [ -z "$MEMORY_LIMIT" ] || [ "$MEMORY_LIMIT" = "9223372036854771712" ]; then
    # 无限制，使用系统内存的 80% 作为软限制
    MEMORY_LIMIT=$(awk '/MemTotal/{printf "%d", $2 * 1024 * 0.8}' /proc/meminfo)
fi

MEMORY_LIMIT_MB=$((MEMORY_LIMIT / 1024 / 1024))
echo "内存限制: ${MEMORY_LIMIT_MB}MB"

# 监控循环
TARGET_PRESSURE_LEVELS=(50 60 70 80 85 90)
CURRENT_LEVEL=0

echo "timestamp,phase,pressure_percent,openclaw_rss_mb,openclaw_vmsize_mb,system_free_mb,oom_score,status" > $LOG_DIR/gradual_test.csv

for PHASE in "{TARGET_PRESSURE_LEVELS[@]}"; do
    TARGET_PRESSURE=$PHASE
    echo ""
    echo "=== 阶段 $CURRENT_LEVEL: 目标内存压力 ${TARGET_PRESSURE}% ==="
    
    # 计算需要填充的内存
    CURRENT_USAGE=$(cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null || echo 0)
    TARGET_USAGE=$((MEMORY_LIMIT * TARGET_PRESSURE / 100))
    FILL_SIZE=$((TARGET_USAGE - CURRENT_USAGE))
    FILL_SIZE_MB=$((FILL_SIZE / 1024 / 1024))
    
    if [ $FILL_SIZE_MB -gt 0 ]; then
        echo "填充 ${FILL_SIZE_MB}MB 内存..."
        # 使用 stress-ng 填充内存
        stress-ng --vm 1 --vm-bytes ${FILL_SIZE_MB}M --vm-keep --timeout 300 &
        STRESS_PID=$!
    fi
    
    # 监控 5 分钟
    for ((i=0; i<300; i+=10)); do
        TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
        
        # 检查 OpenClaw 是否存活
        if ! kill -0 $OPENCLAW_PID 2>/dev/null; then
            echo "$TIMESTAMP,PHASE_$CURRENT_LEVEL,$TARGET_PRESSURE,0,0,0,0,OOM_KILLED" >> $LOG_DIR/gradual_test.csv
            echo "ALERT: OpenClaw 进程已终止！"
            dmesg | tail -20 | grep -i "oom\|killed process" >> $LOG_DIR/oom_events.log
            exit 1
        fi
        
        # 采集数据
        RSS_KB=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmRSS | awk '{print $2}')
        VMSIZE_KB=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmSize | awk '{print $2}')
        OOM_SCORE=$(cat /proc/$OPENCLAW_PID/oom_score 2>/dev/null || echo "N/A")
        SYSTEM_FREE=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
        
        echo "$TIMESTAMP,PHASE_$CURRENT_LEVEL,$TARGET_PRESSURE,$((RSS_KB/1024)),$((VMSIZE_KB/1024)),$SYSTEM_FREE,$OOM_SCORE,RUNNING" >> $LOG_DIR/gradual_test.csv
        
        # 检查 OOM 分数
        if [ "$OOM_SCORE" != "N/A" ] && [ "$OOM_SCORE" -gt 500 ]; then
            echo "WARNING: OOM Score 过高: $OOM_SCORE"
        fi
        
        sleep 10
    done
    
    # 清理 stress 进程
    kill $STRESS_PID 2>/dev/null
    wait $STRESS_PID 2>/dev/null
    
    CURRENT_LEVEL=$((CURRENT_LEVEL + 1))
    
    # 等待内存回落
    echo "等待内存回落..."
    sleep 30
done

echo ""
echo "=== 渐进式测试完成 ==="
```

### 步骤 3：边界内存测试（接近限制）

```bash
# 测试在接近内存限制时的行为
cat > ~/oom_test/boundary_test.sh << 'BOUNDARY_EOF'
#!/bin/bash
# 边界内存测试

LOG_DIR=~/oom_test/logs
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)

echo "=== 边界内存测试 ==="
echo "时间: $(date)"
echo "PID: $OPENCLAW_PID"

# 获取内存限制
MEMORY_LIMIT=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || awk '/MemTotal/{print int($2 * 1024 * 0.9)}' /proc/meminfo)
MEMORY_LIMIT_MB=$((MEMORY_LIMIT / 1024 / 1024))

echo "内存限制: ${MEMORY_LIMIT_MB}MB"
echo "开始填充内存至 95%..."

# 计算填充量
CURRENT_USAGE=$(cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null || echo 0)
TARGET_USAGE=$((MEMORY_LIMIT * 95 / 100))
FILL_SIZE=$((TARGET_USAGE - CURRENT_USAGE))
FILL_SIZE_MB=$((FILL_SIZE / 1024 / 1024))

if [ $FILL_SIZE_MB -gt 100 ]; then
    echo "填充 ${FILL_SIZE_MB}MB 到 95% 限制..."
    
    # 后台填充
    stress-ng --vm 1 --vm-bytes ${FILL_SIZE_MB}M --vm-keep --timeout 600 &
    STRESS_PID=$!
    
    # 监控 OpenClaw 反应
    for ((i=0; i<60; i++)); do
        if ! kill -0 $OPENCLAW_PID 2>/dev/null; then
            echo "ALERT: OpenClaw 在高压力下终止！"
            dmesg | grep -i "oom\|killed process" | tail -5
            break
        fi
        
        RSS=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmRSS | awk '{print $2}')
        OOM_ADJ=$(cat /proc/$OPENCLAW_PID/oom_score_adj 2>/dev/null)
        echo "$(date '+%H:%M:%S') - RSS: $((RSS/1024))MB, OOM_ADJ: $OOM_ADJ"
        
        sleep 10
    done
    
    kill $STRESS_PID 2>/dev/null
    
    echo ""
    echo "释放内存，观察恢复..."
    sleep 60
    
    # 检查恢复
    if kill -0 $OPENCLAW_PID 2>/dev/null; then
        RSS=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmRSS | awk '{print $2}')
        echo "恢复后 RSS: $((RSS/1024))MB"
        
        # 健康检查
        curl -s http://localhost:39941/health 2>/dev/null && echo "✅ 健康检查通过" || echo "❌ 健康检查失败"
    else
        echo "❌ OpenClaw 未能恢复"
    fi
else
    echo "可用内存不足，跳过边界测试"
fi

BOUNDARY_EOF

chmod +x ~/oom_test/boundary_test.sh
```

### 步骤 4：突发内存压力测试

```bash
# 模拟突发内存需求（如大量并发连接）
cat > ~/oom_test/burst_memory_test.sh << 'BURST_EOF'
#!/bin/bash
# 突发内存压力测试

LOG_DIR=~/oom_test/logs
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)

echo "=== 突发内存压力测试 ==="
echo "模拟突发高并发场景..."

# 使用 WebSocket 客户端进行突发连接
cd ~/heartbeat_test

# 第一轮：正常负载
echo "阶段1: 正常负载 (30并发)..."
TARGET=ws://10.0.12.4:8080 DURATION=60 CONCURRENT=30 INTERVAL=100 node websocket_client.js > $LOG_DIR/burst_normal.log 2>&1 &
sleep 60

# 第二轮：突发高负载
echo "阶段2: 突发高负载 (100并发)..."
TARGET=ws://10.0.12.4:8080 DURATION=120 CONCURRENT=100 INTERVAL=50 node websocket_client.js > $LOG_DIR/burst_high.log 2>&1 &
BURST_PID=$!

# 监控内存峰值
echo "timestamp,phase,rss_kb,vmsize_kb,connections,status" > $LOG_DIR/burst_memory.csv
for ((i=0; i<120; i+=5)); do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    RSS=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmRSS | awk '{print $2}')
    VMSIZE=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmSize | awk '{print $2}')
    CONNS=$(netstat -an 2>/dev/null | grep :8080 | wc -l)
    
    if kill -0 $OPENCLAW_PID 2>/dev/null; then
        STATUS="RUNNING"
    else
        STATUS="DIED"
        echo "ALERT: OpenClaw 在突发压力下崩溃！"
        break
    fi
    
    echo "$TIMESTAMP,BURST,$RSS,$VMSIZE,$CONNS,$STATUS" >> $LOG_DIR/burst_memory.csv
    sleep 5
done

wait $BURST_PID 2>/dev/null

# 第三轮：观察恢复
echo "阶段3: 观察恢复..."
sleep 60

RSS=$(cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep VmRSS | awk '{print $2}')
echo "恢复后 RSS: $((RSS/1024))MB"

echo "=== 突发测试完成 ==="

BURST_EOF

chmod +x ~/oom_test/burst_memory_test.sh
```

### 步骤 5：OOM 事件监控

```bash
# 创建 OOM 事件监控脚本
cat > ~/oom_test/oom_monitor.sh << 'OOM_MONITOR_EOF'
#!/bin/bash
# OOM 事件监控

LOG_DIR=~/oom_test/logs
mkdir -p $LOG_DIR

echo "=== OOM 事件监控启动 ==="
echo "时间: $(date)"

# 监控 dmesg 中的 OOM 事件
dmesg -w | while read line; do
    if echo "$line" | grep -qi "oom\|out of memory\|killed process"; then
        TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
        echo "$TIMESTAMP: $line" >> $LOG_DIR/oom_events.log
        echo "🚨 OOM 事件检测: $line"
        
        # 记录系统状态
        echo "" >> $LOG_DIR/oom_events.log
        echo "=== 系统状态 ($TIMESTAMP) ===" >> $LOG_DIR/oom_events.log
        free -m >> $LOG_DIR/oom_events.log
        echo "" >> $LOG_DIR/oom_events.log
        ps aux --sort=-%mem | head -10 >> $LOG_DIR/oom_events.log
    fi
done &

OEMONITOR_PID=$!
echo $OEMONITOR_PID > $LOG_DIR/oom_monitor.pid
echo "OOM 监控 PID: $OEMONITOR_PID"

OOM_MONITOR_EOF

chmod +x ~/oom_test/oom_monitor.sh
```

### 步骤 6：发布评估报告生成

```bash
# 生成发布评估报告
cat > ~/oom_test/generate_report.sh << 'REPORT_EOF'
#!/bin/bash
# 生成 OOM 风险评估报告

LOG_DIR=~/oom_test/logs
REPORT_FILE=~/oom_test/OOM_ASSESSMENT_REPORT.md

echo "# OpenClaw OOM 风险评估报告" > $REPORT_FILE
echo "" >> $REPORT_FILE
echo "生成时间: $(date)" >> $REPORT_FILE
echo "测试版本: [待填写]" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "---" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 1. 测试摘要
echo "## 测试摘要" >> $REPORT_FILE
echo "" >> $REPORT_FILE

OOM_EVENTS=$(wc -l < $LOG_DIR/oom_events.log 2>/dev/null || echo 0)
if [ "$OOM_EVENTS" -gt 0 ]; then
    echo "⚠️ 检测到 $OOM_EVENTS 次 OOM 相关事件" >> $REPORT_FILE
else
    echo "✅ 未检测到 OOM 事件" >> $REPORT_FILE
fi
echo "" >> $REPORT_FILE

# 2. 渐进式测试结果
if [ -f "$LOG_DIR/gradual_test.csv" ]; then
    echo "## 渐进式内存压力测试" >> $REPORT_FILE
    echo "" >> $REPORT_FILE
    echo "| 阶段 | 目标压力 | 平均 RSS | 状态 |" >> $REPORT_FILE
    echo "|------|----------|----------|------|" >> $REPORT_FILE
    
    tail -n +2 $LOG_DIR/gradual_test.csv | awk -F',' '
    BEGIN{last_phase=""}
    {
        if ($2 != last_phase) {
            print "| " $2 " | " $3 "% | " $4 "MB | " $8 " |"
            last_phase=$2
        }
    }' >> $REPORT_FILE
    echo "" >> $REPORT_FILE
fi

# 3. 内存峰值分析
if [ -f "$LOG_DIR/burst_memory.csv" ]; then
    echo "## 突发压力内存峰值" >> $REPORT_FILE
    echo "" >> $REPORT_FILE
    MAX_RSS=$(tail -n +2 $LOG_DIR/burst_memory.csv | awk -F',' 'BEGIN{max=0} {if($3>max) max=$3} END{printf "%.0f", max/1024}')
    echo "- 峰值 RSS: ${MAX_RSS}MB" >> $REPORT_FILE
    echo "" >> $REPORT_FILE
fi

# 4. 发布评估
echo "## 发布评估" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 评估逻辑
RISK_LEVEL="🟢 低风险 - 可发布"
BLOCKERS=0

# 检查1: OOM 事件
if [ "$OOM_EVENTS" -gt 0 ]; then
    RISK_LEVEL="🔴 高风险 - 阻断发布"
    BLOCKERS=$((BLOCKERS + 1))
    echo "- ❌ 发现 OOM 事件: $OOM_EVENTS 次" >> $REPORT_FILE
else
    echo "- ✅ 无 OOM 事件" >> $REPORT_FILE
fi

# 检查2: 进程存活
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
if [ -n "$OPENCLAW_PID" ]; then
    echo "- ✅ OpenClaw 进程存活" >> $REPORT_FILE
else
    RISK_LEVEL="🔴 高风险 - 阻断发布"
    BLOCKERS=$((BLOCKERS + 1))
    echo "- ❌ OpenClaw 进程已终止" >> $REPORT_FILE
fi

# 检查3: 健康检查
HEALTH=$(curl -s http://localhost:39941/health 2>/dev/null | grep -c "ok")
if [ "$HEALTH" -gt 0 ]; then
    echo "- ✅ 健康检查通过" >> $REPORT_FILE
else
    echo "- ⚠️ 健康检查未通过（可能端口不同）" >> $REPORT_FILE
fi

echo "" >> $REPORT_FILE
echo "## 评估结论" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "$RISK_LEVEL" >> $REPORT_FILE
echo "" >> $REPORT_FILE

if [ $BLOCKERS -eq 0 ]; then
    echo "✅ **建议: 当前版本满足发布要求**" >> $REPORT_FILE
elif [ $BLOCKERS -lt 3 ]; then
    echo "🟡 **建议: 有条件发布 - 需评审 OOM 风险**" >> $REPORT_FILE
else
    echo "🔴 **建议: 阻断发布 - 必须修复 OOM 问题**" >> $REPORT_FILE
fi

echo "" >> $REPORT_FILE
echo "---" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "*报告由 OOM 风险评估测试自动生成*" >> $REPORT_FILE

cat $REPORT_FILE

REPORT_EOF

chmod +x ~/oom_test/generate_report.sh
```

## 测试执行流程

```bash
# 1. 准备环境
mkdir -p ~/oom_test/logs

# 2. 启动 OOM 监控
~/oom_test/oom_monitor.sh

# 3. 执行基线测试
~/oom_test/baseline_test.sh

# 4. 执行渐进式压力测试
~/oom_test/gradual_memory_test.sh

# 5. 执行边界测试
~/oom_test/boundary_test.sh

# 6. 执行突发压力测试
~/oom_test/burst_memory_test.sh

# 7. 生成评估报告
~/oom_test/generate_report.sh
```

## 预期结果

| 场景 | 预期行为 | 不通过表现 |
|------|----------|------------|
| 50% 内存压力 | 正常运行，无异常 | OOM 或明显卡顿 |
| 80% 内存压力 | 正常服务，可能触发GC | 响应超时或错误 |
| 95% 内存压力 | 优雅降级，保留核心功能 | 崩溃或死锁 |
| 突发压力 | 峰值后恢复正常 | 无法恢复 |

## 通过标准（发布要求）

### 🟢 可发布标准

- ✅ 在配置内存限制内稳定运行
- ✅ 渐进压力测试完成无 OOM
- ✅ 突发压力后能恢复正常
- ✅ 健康检查始终通过
- ✅ 无内存泄漏迹象（RSS 稳定在限制内）

### 🟡 有条件发布

- ⚠️ 偶发 OOM 但可快速恢复
- ⚠️ 需特定配置避免 OOM
- ⚠️ 已知问题但有规避方案

### 🔴 阻断发布

- ❌ 频繁 OOM 导致服务不可用
- ❌ OOM 后无法自动恢复
- ❌ 内存泄漏导致持续增长
- ❌ 数据丢失或 corruption

## 关键指标

| 指标 | 警戒线 | 危险线 |
|------|--------|--------|
| OOM Score | > 300 | > 800 |
| RSS / 限制比例 | > 70% | > 90% |
| GC 频率 | < 1次/分钟 | > 5次/分钟 |
| 恢复时间 | < 30秒 | > 2分钟 |

## 相关文件

- 基线测试: `~/oom_test/baseline_test.sh`
- 渐进测试: `~/oom_test/gradual_memory_test.sh`
- 边界测试: `~/oom_test/boundary_test.sh`
- 突发测试: `~/oom_test/burst_memory_test.sh`
- OOM 监控: `~/oom_test/oom_monitor.sh`
- 报告生成: `~/oom_test/generate_report.sh`
- 配置: `oom-risk-config.json`

## 注意事项

1. **测试环境**: 务必在与生产环境相似的内存限制下测试
2. **数据安全**: 测试可能导致服务中断，避免在生产高峰执行
3. **监控完整性**: 确保 dmesg 和系统日志可访问
4. **多次验证**: 建议至少运行 3 次测试取平均结果
5. **版本标记**: 记录测试时的确切版本号用于追溯

## 扩展测试

- **长时间压力测试**: 24小时持续压力观察
- **不同内存限制**: 2GB / 4GB / 8GB 不同限制下的表现
- **多服务竞争**: 与其他服务共享内存时的表现

---

**发布决策矩阵：**

| 测试项 | 通过 | 失败 | 权重 |
|--------|------|------|------|
| 渐进压力测试 | ✅ | ❌ | 高 |
| 边界压力测试 | ✅ | ❌ | 高 |
| 突发压力测试 | ✅ | ❌ | 中 |
| OOM 恢复测试 | ✅ | ❌ | 高 |
| 内存泄漏检查 | ✅ | ❌ | 高 |

*任何"高权重"项失败都应考虑阻断发布*
