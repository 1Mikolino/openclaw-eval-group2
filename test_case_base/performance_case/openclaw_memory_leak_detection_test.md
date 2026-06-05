# OpenClaw 内存泄漏检测测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-004 |
| 用例名称 | OpenClaw 内存泄漏检测测试 |
| 优先级 | P0 (高) |
| 测试类型 | 内存测试 / 泄漏检测测试 |
| 创建日期 | 2026-06-05 |

## 测试目的

验证 OpenClaw 在长时间运行和高负载场景下是否存在以下内存问题：
- **内存持续增长**: 内存使用随时间不断增长不回落
- **无法回收**: 垃圾回收后内存未释放
- **峰值异常**: 内存峰值超过合理范围
- **泄漏迹象**: 存在明显的内存泄漏模式

## 前置条件

1. OpenClaw 服务已部署并可正常访问
2. 具备内存监控工具（`top`, `free`, `pmap`, `heaptrack` 等）
3. 具备 Node.js 堆内存分析能力（`--inspect` 或 heapdump）
4. 测试环境内存充足（建议 ≥ 4GB）
5. 监控脚本权限足够读取 OpenClaw 进程内存信息

## 测试环境

| 配置项 | 要求 |
|--------|------|
| CPU | 2 核及以上 |
| 内存 | 4GB 及以上（测试需要） |
| 磁盘空间 | 5GB+ 可用空间（用于堆转储） |
| 操作系统 | Linux (Ubuntu 20.04+) |
| Node.js | v18+ |
| OpenClaw | 待测版本 |
| 工具 | `smem`, `pmap`, `heaptrack`, `llnode` (可选) |

## 测试步骤

### 步骤 1：环境准备与初始内存采集

```bash
# 1. 创建内存监控目录
mkdir -p ~/memory_test/{monitoring,heapsnapshots,reports}

# 2. 记录测试开始时间
echo "测试开始时间: $(date '+%Y-%m-%d %H:%M:%S')" > ~/memory_test/baseline.log

# 3. 检查系统内存状况
echo "=== 系统内存基线 ===" >> ~/memory_test/baseline.log
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached" >> ~/memory_test/baseline.log

echo "" >> ~/memory_test/baseline.log
echo "=== OpenClaw 进程初始状态 ===" >> ~/memory_test/baseline.log
ps aux | grep -E "openclaw|PID" | grep -v grep >> ~/memory_test/baseline.log

# 4. 获取 OpenClaw PID
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
echo "OpenClaw PID: $OPENCLAW_PID" >> ~/memory_test/baseline.log

# 5. 记录详细内存映射（基线）
if [ -n "$OPENCLAW_PID" ]; then
    echo "" >> ~/memory_test/baseline.log
    echo "=== 初始内存映射 ===" >> ~/memory_test/baseline.log
    pmap -x $OPENCLAW_PID 2>/dev/null | tail -1 >> ~/memory_test/baseline.log
    
    echo "" >> ~/memory_test/baseline.log
    echo "=== 初始STATUS内存信息 ===" >> ~/memory_test/baseline.log
    cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep -E "VmSize|VmRSS|VmData|VmStk|VmExe|VmLib" >> ~/memory_test/baseline.log
fi
```

### 步骤 2：启动内存监控脚本

创建并启动内存监控脚本 `~/memory_test/memory_monitor.sh`：

```bash
#!/bin/bash
# 内存泄漏检测监控脚本

LOG_DIR=~/memory_test/monitoring
INTERVAL=30  # 每30秒采集一次
DURATION=3600  # 默认监控1小时（3600秒）
PID_FILE="$LOG_DIR/target.pid"

mkdir -p $LOG_DIR

# 获取目标PID（支持传入或自动检测）
get_target_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        pgrep -f "openclaw.*gateway" | head -1
    fi
}

# 记录CSV头部
echo "timestamp,pid,vm_size_kb,vm_rss_kb,vm_data_kb,vm_exe_kb,percent_memory,system_free_mb,system_available_mb,growth_rate" > $LOG_DIR/memory_trend.csv

TARGET_PID=$(get_target_pid)
if [ -z "$TARGET_PID" ]; then
    echo "错误: 无法找到 OpenClaw 进程"
    exit 1
fi

echo "开始监控 PID: $TARGET_PID"
echo "$TARGET_PID" > $PID_FILE

# 初始内存值（用于计算增长率）
INITIAL_RSS=0
LAST_RSS=0

echo "监控开始: $(date)" > $LOG_DIR/monitor.log

for ((i=0; i<$DURATION; i+=$INTERVAL)); do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    ELAPSED_MIN=$((i / 60))
    
    TARGET_PID=$(get_target_pid)
    if [ -z "$TARGET_PID" ] || ! kill -0 $TARGET_PID 2>/dev/null; then
        echo "$TIMESTAMP: ALERT - 目标进程不存在！" >> $LOG_DIR/alerts.log
        break
    fi
    
    # 从 /proc/[pid]/status 读取内存信息
    STATUS_FILE="/proc/$TARGET_PID/status"
    if [ -f "$STATUS_FILE" ]; then
        VM_SIZE=$(grep VmSize $STATUS_FILE | awk '{print $2}')
        VM_RSS=$(grep VmRSS $STATUS_FILE | awk '{print $2}')
        VM_DATA=$(grep VmData $STATUS_FILE | awk '{print $2}' || echo "0")
        VM_EXE=$(grep VmExe $STATUS_FILE | awk '{print $2}' || echo "0")
        
        # 计算增长率
        if [ $INITIAL_RSS -eq 0 ]; then
            INITIAL_RSS=$VM_RSS
            GROWTH_RATE="0.00"
        else
            GROWTH_RATE=$(echo "scale=2; ($VM_RSS - $INITIAL_RSS) * 100 / $INITIAL_RSS" | bc 2>/dev/null || echo "N/A")
        fi
        
        # 获取系统内存
        MEM_INFO=$(free -m | grep Mem)
        MEM_FREE=$(echo $MEM_INFO | awk '{print $4}')
        MEM_AVAILABLE=$(echo $MEM_INFO | awk '{print $7}')
        
        # 获取进程内存占用百分比
        MEM_PERCENT=$(ps -p $TARGET_PID -o %mem --no-headers 2>/dev/null | tr -d ' ')
        
        # 写入CSV
        echo "$TIMESTAMP,$TARGET_PID,$VM_SIZE,$VM_RSS,$VM_DATA,$VM_EXE,$MEM_PERCENT,$MEM_FREE,$MEM_AVAILABLE,$GROWTH_RATE" >> $LOG_DIR/memory_trend.csv
        
        # 检测异常增长（30分钟内增长超过20%）
        if [ "$GROWTH_RATE" != "N/A" ] && (( $(echo "$GROWTH_RATE > 20" | bc -l 2>/dev/null || echo 0) )); then
            echo "$TIMESTAMP: WARNING - 内存增长 $GROWTH_RATE% (已超过20%)" >> $LOG_DIR/alerts.log
        fi
        
        # 检测内存峰值（超过系统80%）
        if [ "$MEM_PERCENT" != "" ] && (( $(echo "$MEM_PERCENT > 80" | bc -l 2>/dev/null || echo 0) )); then
            echo "$TIMESTAMP: ALERT - 内存使用过高: $MEM_PERCENT%" >> $LOG_DIR/alerts.log
        fi
        
        # 每小时输出摘要
        if [ $((i % 3600)) -eq 0 ] && [ $i -gt 0 ]; then
            echo "[$TIMESTAMP] 已监控 ${ELAPSED_MIN}分钟, RSS: ${VM_RSS}KB, 增长: ${GROWTH_RATE}%" | tee -a $LOG_DIR/hourly_summary.log
        fi
        
        LAST_RSS=$VM_RSS
    fi
    
    sleep $INTERVAL
done

echo "监控结束: $(date)" >> $LOG_DIR/monitor.log
```

启动监控：
```bash
chmod +x ~/memory_test/memory_monitor.sh
nohup ~/memory_test/memory_monitor.sh > ~/memory_test/monitor_nohup.log 2>&1 &
echo "内存监控已启动，PID: $!"
```

### 步骤 3：创建堆内存快照（可选 - 深度分析）

```bash
# 安装堆快照工具
npm install -g heapdump 2>/dev/null || echo "heapdump 安装跳过"

# 创建堆快照脚本
cat > ~/memory_test/heap_snapshot.sh << 'HEAP_EOF'
#!/bin/bash
# 堆内存快照脚本

HEAP_DIR=~/memory_test/heapsnapshots
mkdir -p $HEAP_DIR

OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
if [ -z "$OPENCLAW_PID" ]; then
    echo "错误: 无法找到 OpenClaw 进程"
    exit 1
fi

SNAPSHOT_NAME="heap_$(date +%Y%m%d_%H%M%S).heapsnapshot"
echo "创建堆快照: $SNAPSHOT_NAME"

# 使用 Node.js  inspector 协议创建堆快照
# 注意: 需要 OpenClaw 启动时添加 --inspect 参数
node -e "
const inspector = require('inspector');
const fs = require('fs');
const session = new inspector.Session();
session.connect();
session.post('HeapProfiler.enable', () => {
  session.post('HeapProfiler.takeHeapSnapshot', (err, params) => {
    if (err) {
      console.error('创建堆快照失败:', err);
    } else {
      console.log('堆快照创建成功');
    }
    session.disconnect();
  });
});
" 2>/dev/null || echo "堆快照需要调试模式支持"

# 备选方案: 使用 gcore 创建核心转储
gcore -o $HEAP_DIR/core_$OPENCLAW_PID $OPENCLAW_PID 2>/dev/null || echo "gcore 需要 sudo 权限"

HEAP_EOF
chmod +x ~/memory_test/heap_snapshot.sh
```

### 步骤 4：运行压力测试触发内存增长

```bash
cd ~/heartbeat_test

# 使用已有的 WebSocket 客户端进行压力测试
TARGET=ws://10.0.12.4:8080 DURATION=3600 CONCURRENT=50 INTERVAL=100 node websocket_client.js 2>&1 | tee ~/memory_test/pressure_test.log &
PRESSURE_PID=$!
echo "压力测试已启动，PID: $PRESSURE_PID"
```

或使用 HTTP 压力测试：
```bash
cd ~/heartbeat_test
TARGET=http://10.0.12.4:8080 DURATION=3600 CONCURRENT=30 INTERVAL=50 node simple_load_test.js 2>&1 | tee ~/memory_test/pressure_test.log &
```

### 步骤 5：监控期间检查点

在测试运行期间，定期执行以下检查：

```bash
# 每30分钟执行一次详细检查

echo "=== $(date) 检查点报告 ===" >> ~/memory_test/checkpoint_report.log

# 1. 查看内存趋势
TAIL_LINES=120  # 最近1小时 (120 * 30s = 3600s)
echo "--- 最近内存趋势 ---" >> ~/memory_test/checkpoint_report.log
tail -$TAIL_LINES ~/memory_test/monitoring/memory_trend.csv >> ~/memory_test/checkpoint_report.log

# 2. 检查是否有内存警告
echo "" >> ~/memory_test/checkpoint_report.log
echo "--- 警告/警报 ---" >> ~/memory_test/checkpoint_report.log
cat ~/memory_test/monitoring/alerts.log 2>/dev/null >> ~/memory_test/checkpoint_report.log

# 3. 强制垃圾回收检查（如果可能）
# 向 Node.js 进程发送 SIGUSR1 触发 GC 报告（某些版本支持）
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
# kill -SIGUSR1 $OPENCLAW_PID 2>/dev/null || echo "GC 信号发送失败"

# 4. 记录系统内存压力
echo "" >> ~/memory_test/checkpoint_report.log
echo "--- 系统内存压力 ---" >> ~/memory_test/checkpoint_report.log
vmstat -s | grep -E "memory|swap" >> ~/memory_test/checkpoint_report.log
```

### 步骤 6：测试结束与数据分析

```bash
# 1. 停止压力测试
pkill -f "websocket_client.js" 2>/dev/null
pkill -f "simple_load_test.js" 2>/dev/null

# 2. 停止内存监控（等待最后几次采集）
sleep 35
pkill -f "memory_monitor.sh" 2>/dev/null

# 3. 记录最终状态
echo "=== 测试结束时间 ===" > ~/memory_test/final_report.log
date '+%Y-%m-%d %H:%M:%S' >> ~/memory_test/final_report.log

echo "" >> ~/memory_test/final_report.log
echo "=== 最终内存状态 ===" >> ~/memory_test/final_report.log
OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
if [ -n "$OPENCLAW_PID" ]; then
    echo "PID: $OPENCLAW_PID" >> ~/memory_test/final_report.log
    cat /proc/$OPENCLAW_PID/status 2>/dev/null | grep -E "VmSize|VmRSS|VmData" >> ~/memory_test/final_report.log
fi

echo "" >> ~/memory_test/final_report.log
echo "=== 系统内存状态 ===" >> ~/memory_test/final_report.log
free -h >> ~/memory_test/final_report.log

# 4. 生成内存趋势分析
echo "" >> ~/memory_test/final_report.log
echo "=== 内存趋势分析 ===" >> ~/memory_test/final_report.log

# 计算内存增长
FIRST_RSS=$(tail -n +2 ~/memory_test/monitoring/memory_trend.csv | head -1 | awk -F',' '{print $4}')
LAST_RSS=$(tail -1 ~/memory_test/monitoring/memory_trend.csv | awk -F',' '{print $4}')

if [ -n "$FIRST_RSS" ] && [ -n "$LAST_RSS" ] && [ "$FIRST_RSS" -gt 0 ]; then
    GROWTH=$((LAST_RSS - FIRST_RSS))
    GROWTH_PERCENT=$(echo "scale=2; $GROWTH * 100 / $FIRST_RSS" | bc 2>/dev/null || echo "N/A")
    
    echo "初始 RSS: ${FIRST_RSS}KB" >> ~/memory_test/final_report.log
    echo "最终 RSS: ${LAST_RSS}KB" >> ~/memory_test/final_report.log
    echo "内存增长: ${GROWTH}KB (${GROWTH_PERCENT}%)" >> ~/memory_test/final_report.log
fi

# 5. 查找最大内存使用
MAX_RSS=$(tail -n +2 ~/memory_test/monitoring/memory_trend.csv | awk -F',' '{print $4}' | sort -n | tail -1)
echo "峰值 RSS: ${MAX_RSS}KB" >> ~/memory_test/final_report.log
```

### 步骤 7：内存泄漏判定

```bash
cat > ~/memory_test/analyze_leak.sh << 'ANALYZE_EOF'
#!/bin/bash
# 内存泄漏分析脚本

CSV_FILE=~/memory_test/monitoring/memory_trend.csv
REPORT_FILE=~/memory_test/leak_analysis_report.txt

echo "===================================" > $REPORT_FILE
echo "OpenClaw 内存泄漏分析报告" >> $REPORT_FILE
echo "生成时间: $(date)" >> $REPORT_FILE
echo "===================================" >> $REPORT_FILE
echo "" >> $REPORT_FILE

if [ ! -f "$CSV_FILE" ]; then
    echo "错误: 未找到内存监控数据" >> $REPORT_FILE
    exit 1
fi

# 提取RSS数据（跳过标题行）
RSS_VALUES=$(tail -n +2 $CSV_FILE | awk -F',' '{print $4}')
TOTAL_SAMPLES=$(echo "$RSS_VALUES" | wc -l)

echo "监控样本数: $TOTAL_SAMPLES" >> $REPORT_FILE

# 计算统计信息
FIRST_RSS=$(echo "$RSS_VALUES" | head -1)
LAST_RSS=$(echo "$RSS_VALUES" | tail -1)
MIN_RSS=$(echo "$RSS_VALUES" | sort -n | head -1)
MAX_RSS=$(echo "$RSS_VALUES" | sort -n | tail -1)
AVG_RSS=$(echo "$RSS_VALUES" | awk '{sum+=$1; count++} END {printf "%.0f", sum/count}')

echo "" >> $REPORT_FILE
echo "--- 内存使用统计 ---" >> $REPORT_FILE
echo "初始 RSS: ${FIRST_RSS}KB ($(echo "scale=2; $FIRST_RSS/1024" | bc)MB)" >> $REPORT_FILE
echo "最终 RSS: ${LAST_RSS}KB ($(echo "scale=2; $LAST_RSS/1024" | bc)MB)" >> $REPORT_FILE
echo "最小 RSS: ${MIN_RSS}KB ($(echo "scale=2; $MIN_RSS/1024" | bc)MB)" >> $REPORT_FILE
echo "最大 RSS: ${MAX_RSS}KB ($(echo "scale=2; $MAX_RSS/1024" | bc)MB)" >> $REPORT_FILE
echo "平均 RSS: ${AVG_RSS}KB ($(echo "scale=2; $AVG_RSS/1024" | bc)MB)" >> $REPORT_FILE

# 计算增长趋势
if [ "$FIRST_RSS" -gt 0 ]; then
    GROWTH=$((LAST_RSS - FIRST_RSS))
    GROWTH_MB=$(echo "scale=2; $GROWTH/1024" | bc)
    GROWTH_PERCENT=$(echo "scale=2; $GROWTH * 100 / $FIRST_RSS" | bc)
    
    echo "" >> $REPORT_FILE
    echo "--- 增长分析 ---" >> $REPORT_FILE
    echo "绝对增长: ${GROWTH}KB (${GROWTH_MB}MB)" >> $REPORT_FILE
    echo "增长比例: ${GROWTH_PERCENT}%" >> $REPORT_FILE
    
    # 泄漏判定
    echo "" >> $REPORT_FILE
    echo "--- 泄漏判定 ---" >> $REPORT_FILE
    
    # 判定标准1: 增长超过50%
    if (( $(echo "$GROWTH_PERCENT > 50" | bc -l) )); then
        echo "❌ 严重内存泄漏: 内存增长超过50%" >> $REPORT_FILE
        LEAK_DETECTED=1
    elif (( $(echo "$GROWTH_PERCENT > 20" | bc -l) )); then
        echo "⚠️  疑似内存泄漏: 内存增长20-50%，建议进一步分析" >> $REPORT_FILE
        LEAK_DETECTED=1
    else
        echo "✅ 无明显泄漏: 内存增长在合理范围内(<20%)" >> $REPORT_FILE
        LEAK_DETECTED=0
    fi
    
    # 判定标准2: 峰值异常
    PEAK_RATIO=$(echo "scale=2; $MAX_RSS / $FIRST_RSS" | bc)
    if (( $(echo "$PEAK_RATIO > 2" | bc -l) )); then
        echo "⚠️  峰值异常: 峰值是初始值的 ${PEAK_RATIO} 倍" >> $REPORT_FILE
    fi
    
    # 判定标准3: 无法回收检查（最后10%的数据点是否持续高位）
    LAST_10_PCT=$((TOTAL_SAMPLES / 10))
    if [ $LAST_10_PCT -lt 5 ]; then
        LAST_10_PCT=5
    fi
    
    LAST_AVG=$(tail -n $LAST_10_PCT $CSV_FILE | tail -n +2 | awk -F',' '{sum+=$4; count++} END {printf "%.0f", sum/count}')
    
    if [ "$LAST_AVG" -gt "$FIRST_RSS" ]; then
        RECOVERY=$(( (LAST_AVG - FIRST_RSS) * 100 / FIRST_RSS ))
        echo "回收情况: 最后阶段比初始高 ${RECOVERY}%" >> $REPORT_FILE
        if [ $RECOVERY -gt 30 ]; then
            echo "⚠️  可能存在内存无法回收问题" >> $REPORT_FILE
        fi
    fi
fi

echo "" >> $REPORT_FILE
echo "===================================" >> $REPORT_FILE
if [ "$LEAK_DETECTED" = "1" ]; then
    echo "结论: 检测到潜在的内存问题" >> $REPORT_FILE
else
    echo "结论: 无明显的内存泄漏迹象" >> $REPORT_FILE
fi
echo "===================================" >> $REPORT_FILE

cat $REPORT_FILE
ANALYZE_EOF

chmod +x ~/memory_test/analyze_leak.sh

# 执行分析
~/memory_test/analyze_leak.sh
```

## 预期结果

| 检查项 | 预期结果（正常） | 异常指标 |
|--------|------------------|----------|
| 内存增长 | 增长 < 20%（测试期间） | 增长 > 50% |
| 内存峰值 | 不超过系统80% | 超过系统90% |
| 内存回收 | GC后内存回落 | GC后内存不回落 |
| 稳定性 | 无OOM崩溃 | 发生OOM |

## 通过标准

- ✅ 内存增长在测试期间 < 20%
- ✅ 峰值内存使用 < 系统80%
- ✅ 无 Out-Of-Memory 错误
- ✅ 压力停止后内存回落到基线附近

## 失败标准

- ❌ **内存泄漏**: 内存增长 > 50%
- ❌ **无法回收**: 压力停止后内存不回落
- ❌ **峰值异常**: 内存峰值 > 系统80%
- ❌ **OOM**: 发生 Out-Of-Memory 崩溃

## 数据分析要点

### 内存趋势图生成
```bash
# 使用 gnuplot 或 Excel 绘制内存趋势图
# X轴: 时间, Y轴: RSS (KB)

# 简单文本趋势
tail -n +2 ~/memory_test/monitoring/memory_trend.csv | \
  awk -F',' '{printf "%.0f min: RSS=%sKB (%.1f%%)\n", NR*0.5, $4, $10}' | \
  head -20
```

### 泄漏模式识别
```bash
# 检查内存是否单调递增（泄漏特征）
awk -F',' 'NR>1 {print $4}' ~/memory_test/monitoring/memory_trend.csv | \
  awk 'BEGIN{increasing=0; prev=0} 
       NR>1 && $1>prev{increasing++} 
       {prev=$1} 
       END{printf "递增样本比例: %.1f%%\n", increasing/NR*100}'
```

### 与系统内存对比
```bash
# 查看 OpenClaw 内存与系统可用内存的关系
awk -F',' 'NR>1 {printf "时间: %s, OpenClaw: %sKB, 系统可用: %sMB\n", $1, $4, $9}' \
  ~/memory_test/monitoring/memory_trend.csv | tail -20
```

## 相关脚本

- 内存监控脚本: `~/memory_test/memory_monitor.sh`
- 堆快照脚本: `~/memory_test/heap_snapshot.sh`
- 泄漏分析脚本: `~/memory_test/analyze_leak.sh`
- 压力测试: `~/heartbeat_test/websocket_client.js` 或 `simple_load_test.js`

## 测试配置文件

使用 `memory-leak-config.json` 配合压力测试客户端

## 注意事项

1. **长时间测试**: 建议至少测试 1 小时以上以观察长期趋势
2. **堆快照时机**: 在内存使用高峰时创建堆快照有助于定位泄漏源
3. **系统影响**: 监控脚本本身也会占用资源，建议在独立终端运行
4. **GC干扰**: Node.js GC 行为会影响瞬时内存读数，关注长期趋势
5. **多次测试**: 建议至少运行 3 次测试以确认结果一致性

## 扩展测试

- **24小时耐久测试**: 长时间监控内存趋势
- **不同负载对比**: 低/中/高负载下的内存表现对比
- **GC参数调优**: 测试不同 GC 策略对内存的影响

---

**测试记录模板：**

| 时间 | RSS(MB) | VmData(MB) | 系统可用(MB) | 增长率 | 备注 |
|------|---------|------------|--------------|--------|------|
| 0min | | | | 0% | 初始 |
| 15min | | | | | |
| 30min | | | | | 中间 |
| 45min | | | | | |
| 60min | | | | | 结束 |
