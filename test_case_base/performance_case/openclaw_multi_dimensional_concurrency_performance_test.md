# OpenClaw 多维度并发性能曲线测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-006 |
| 用例名称 | OpenClaw 多维度并发性能曲线测试 |
| 优先级 | P0 (高) |
| 测试类型 | 性能测试 / 可扩展性测试 / 容量规划测试 |
| 创建日期 | 2026-06-07 |

## 测试目的

验证 OpenClaw 在多维度并发压力下的**可解释性能曲线**，具体包括：
- **多用户并发**：验证系统在不同用户数下的响应能力和资源消耗模式
- **多会话并发**：验证系统维持大量活跃会话的稳定性
- **多插件并发**：验证插件系统在高并发调用下的性能表现
- **多消息并发**：验证消息吞吐量和延迟随负载变化的趋势

**核心目标**：绘制系统性能随负载递增的变化曲线，识别性能拐点、饱和点和崩溃阈值，为容量规划提供数据支撑。

## 前置条件

1. OpenClaw 服务已部署并可正常访问
2. 压力测试客户端 (`automation_assets/client.js`) 已准备就绪
3. 系统监控工具已配置（CPU、内存、网络、磁盘 I/O）
4. 至少 3 个测试插件已安装并可用
5. 日志收集系统已配置
6. Grafana/Prometheus 监控（如有）已就绪

## 测试环境

| 配置项 | 基础配置 | 推荐配置 |
|--------|----------|----------|
| CPU | 4 核 | 8 核及以上 |
| 内存 | 8GB | 16GB 及以上 |
| 磁盘 | SSD 20GB+ 可用 | NVMe SSD 50GB+ |
| 网络 | 100Mbps | 1Gbps |
| 操作系统 | Linux (Ubuntu 20.04+) | Ubuntu 22.04 LTS |
| Node.js | v18+ | v20 LTS |
| OpenClaw | 待测版本 | 最新稳定版 |

## 测试维度与指标

### 测试维度矩阵

| 维度 | 起始值 | 递增步长 | 最大值 | 监控重点 |
|------|--------|----------|--------|----------|
| 并发用户数 | 10 | ×2 | 640 | 认证瓶颈、连接限制 |
| 活跃会话数 | 50 | ×2 | 1600 | 内存占用、会话管理 |
| 并发插件调用 | 5 | ×2 | 160 | 插件隔离、资源竞争 |
| 消息发送速率 | 100 msg/s | ×2 | 3200 msg/s | 吞吐量、延迟增长 |

### 核心性能指标

| 指标类别 | 指标名称 | 采集方式 | 可接受阈值 |
|----------|----------|----------|------------|
| **延迟** | P50/P95/P99 响应时间 | 客户端采样 | P95 < 500ms |
| **吞吐量** | 消息/秒 (TPS) | 服务端统计 | 目标值 ± 10% |
| **成功率** | 请求成功率 | 客户端统计 | ≥ 99.5% |
| **资源** | CPU 使用率 | vmstat/top | < 80% |
| **资源** | 内存使用 | free/ps | < 85% |
| **资源** | 网络 I/O | ifstat | 带宽 < 80% |
| **稳定性** | 错误率 | 日志分析 | < 0.1% |
| **可解释性** | 性能曲线线性度 | R² 拟合度 | R² > 0.9 |

## 测试步骤

### 步骤 1：环境初始化与基线采集

```bash
#!/bin/bash
# 初始化测试环境

TEST_DIR=~/multi_dim_test
mkdir -p $TEST_DIR/{results,monitoring,scripts,plugins}

# 记录测试元数据
cat > $TEST_DIR/metadata.json << 'EOF'
{
  "test_id": "PERF-006-$(date +%Y%m%d-%H%M%S)",
  "test_name": "multi-dimensional-concurrency",
  "start_time": "$(date -Iseconds)",
  "environment": {
    "cpu_cores": $(nproc),
    "total_memory_gb": $(free -g | awk '/^Mem:/{print $2}'),
    "os_version": "$(lsb_release -d | cut -f2)",
    "openclaw_version": "$(openclaw version 2>/dev/null || echo 'unknown')"
  }
}
EOF

# 采集系统基线
echo "=== 系统基线采集 ==="
echo "CPU 信息:"
lscpu | grep -E "Model name|CPU\(s\)|Thread|Core"

echo -e "\n内存信息:"
free -h

echo -e "\n磁盘信息:"
df -h / ~/.openclaw

echo -e "\n网络信息:"
ip addr show | grep -E "inet |UP|DOWN"

# 启动系统级监控
cat > $TEST_DIR/scripts/system_monitor.sh << 'MONITOR_EOF'
#!/bin/bash
LOG_DIR=$1
INTERVAL=${2:-5}
mkdir -p $LOG_DIR

echo "timestamp,cpu_user,cpu_system,cpu_idle,mem_used_mb,mem_free_mb,mem_available_mb,load_1m,load_5m,load_15m,openclaw_cpu,openclaw_mem,openclaw_threads,net_rx_kb,net_tx_kb,disk_read_kb,disk_write_kb" > $LOG_DIR/system_metrics.csv

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # CPU 统计
    CPU_STATS=$(cat /proc/stat | head -1)
    CPU_IDLE=$(echo $CPU_STATS | awk '{print $5}')
    CPU_TOTAL=$(echo $CPU_STATS | awk '{sum=$2+$3+$4+$5+$6+$7+$8} END {print sum}')
    
    # 内存
    MEM_INFO=$(free -m | grep "Mem:")
    MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
    MEM_FREE=$(echo $MEM_INFO | awk '{print $4}')
    MEM_AVAIL=$(echo $MEM_INFO | awk '{print $7}')
    
    # 负载
    LOAD=$(cat /proc/loadavg)
    LOAD_1M=$(echo $LOAD | awk '{print $1}')
    LOAD_5M=$(echo $LOAD | awk '{print $2}')
    LOAD_15M=$(echo $LOAD | awk '{print $3}')
    
    # OpenClaw 进程
    OPENCLAW_PID=$(pgrep -f "openclaw.*gateway" | head -1)
    if [ -n "$OPENCLAW_PID" ]; then
        OPENCLAW_STATS=$(ps -p $OPENCLAW_PID -o %cpu,%mem,nlwp --no-headers 2>/dev/null)
        OPENCLAW_CPU=$(echo $OPENCLAW_STATS | awk '{print $1}')
        OPENCLAW_MEM=$(echo $OPENCLAW_STATS | awk '{print $2}')
        OPENCLAW_THREADS=$(echo $OPENCLAW_STATS | awk '{print $3}')
    else
        OPENCLAW_CPU="N/A"
        OPENCLAW_MEM="N/A"
        OPENCLAW_THREADS="N/A"
    fi
    
    # 网络 I/O
    NET_RX="N/A"
    NET_TX="N/A"
    
    # 磁盘 I/O
    DISK_STATS=$(cat /proc/diskstats | grep -E "\bsd[a-z]|nvme" | head -1)
    DISK_READ=$(echo $DISK_STATS | awk '{print $6}')
    DISK_WRITE=$(echo $DISK_STATS | awk '{print $10}')
    
    echo "$TIMESTAMP,$CPU_USER,$CPU_SYS,$CPU_IDLE,$MEM_USED,$MEM_FREE,$MEM_AVAIL,$LOAD_1M,$LOAD_5M,$LOAD_15M,$OPENCLAW_CPU,$OPENCLAW_MEM,$OPENCLAW_THREADS,$NET_RX,$NET_TX,$DISK_READ,$DISK_WRITE" >> $LOG_DIR/system_metrics.csv
    
    sleep $INTERVAL
done
MONITOR_EOF

chmod +x $TEST_DIR/scripts/system_monitor.sh

# 启动监控
nohup $TEST_DIR/scripts/system_monitor.sh $TEST_DIR/monitoring 5 > $TEST_DIR/monitoring/monitor.log 2>&1 &
echo "系统监控已启动，PID: $!"
```

### 步骤 2：单维度递增测试（绘制基础曲线）

#### 2.1 用户并发递增测试

```bash
#!/bin/bash
# 测试不同并发用户数下的性能

TEST_DIR=~/multi_dim_test
RESULTS_DIR=$TEST_DIR/results
mkdir -p $RESULTS_DIR

# 用户并发数序列
USER_COUNTS=(10 20 40 80 160 320 640)
DURATION=180  # 每个负载点运行 3 分钟

echo "timestamp,concurrent_users,duration,total_messages,success_count,failure_count,success_rate,avg_latency_ms,p50_latency_ms,p95_latency_ms,p99_latency_ms,max_latency_ms,tps,cpu_avg,mem_avg" > $RESULTS_DIR/user_concurrency_results.csv

for USERS in "${USER_COUNTS[@]}"; do
    echo "========================================"
    echo "开始测试: $USERS 并发用户"
    echo "时间: $(date)"
    echo "========================================"
    
    # 运行测试
    START_TIME=$(date +%s)
    
    node automation_assets/client.js \
        --config test_case_base/performance_case/multi-dim-concurrency-config.json \
        --override concurrent=$USERS \
        --override duration=$DURATION \
        --output $RESULTS_DIR/user_test_${USERS}.json
    
    END_TIME=$(date +%s)
    ACTUAL_DURATION=$((END_TIME - START_TIME))
    
    # 解析结果并记录
    if [ -f "$RESULTS_DIR/user_test_${USERS}.json" ]; then
        RESULT=$(cat $RESULTS_DIR/user_test_${USERS}.json)
        TOTAL_MSG=$(echo $RESULT | jq -r '.totalMessages // 0')
        SUCCESS=$(echo $RESULT | jq -r '.successCount // 0')
        FAILURE=$(echo $RESULT | jq -r '.failureCount // 0')
        SUCCESS_RATE=$(echo $RESULT | jq -r '.successRate // 0')
        AVG_LAT=$(echo $RESULT | jq -r '.avgLatency // 0')
        P50_LAT=$(echo $RESULT | jq -r '.p50Latency // 0')
        P95_LAT=$(echo $RESULT | jq -r '.p95Latency // 0')
        P99_LAT=$(echo $RESULT | jq -r '.p99Latency // 0')
        MAX_LAT=$(echo $RESULT | jq -r '.maxLatency // 0')
        TPS=$(echo $RESULT | jq -r '.tps // 0')
        
        # 获取系统指标平均值
        CPU_AVG=$(tail -n $((DURATION/5)) $TEST_DIR/monitoring/system_metrics.csv | awk -F',' '{sum+=$2; count++} END {printf "%.2f", sum/count}')
        MEM_AVG=$(tail -n $((DURATION/5)) $TEST_DIR/monitoring/system_metrics.csv | awk -F',' '{sum+=$5; count++} END {printf "%.2f", sum/count}')
        
        echo "$(date '+%Y-%m-%d %H:%M:%S'),$USERS,$ACTUAL_DURATION,$TOTAL_MSG,$SUCCESS,$FAILURE,$SUCCESS_RATE,$AVG_LAT,$P50_LAT,$P95_LAT,$P99_LAT,$MAX_LAT,$TPS,$CPU_AVG,$MEM_AVG" >> $RESULTS_DIR/user_concurrency_results.csv
    fi
    
    # 间隔 30 秒让系统恢复
    echo "等待系统恢复..."
    sleep 30
done

echo "用户并发测试完成！"
```

#### 2.2 会话数递增测试

```bash
#!/bin/bash
# 测试系统维持大量活跃会话的能力

TEST_DIR=~/multi_dim_test
RESULTS_DIR=$TEST_DIR/results

# 会话数序列
SESSION_COUNTS=(50 100 200 400 800 1600)
DURATION=180

echo "timestamp,target_sessions,active_sessions,duration,memory_mb,session_memory_kb,cpu_avg,response_ms" > $RESULTS_DIR/session_capacity_results.csv

for TARGET_SESSIONS in "${SESSION_COUNTS[@]}"; do
    echo "========================================"
    echo "开始测试: $TARGET_SESSIONS 活跃会话"
    echo "时间: $(date)"
    echo "========================================"
    
    # 启动会话保持测试
    node automation_assets/client.js \
        --config test_case_base/performance_case/multi-dim-concurrency-config.json \
        --mode session-hold \
        --sessions $TARGET_SESSIONS \
        --duration $DURATION \
        --heartbeat-interval 30000 \
        --output $RESULTS_DIR/session_test_${TARGET_SESSIONS}.json &
    
    CLIENT_PID=$!
    
    # 监控会话建立过程
    for i in {1..12}; do
        sleep 15
        
        # 获取当前活跃会话数
        ACTIVE_SESSIONS=$(curl -s http://localhost:8080/metrics/sessions 2>/dev/null | jq -r '.active // 0' || echo "N/A")
        
        # 获取内存使用
        MEM_USAGE=$(free -m | awk '/^Mem:/{print $3}')
        
        # 计算单会话内存占用
        if [ "$ACTIVE_SESSIONS" != "N/A" ] && [ "$ACTIVE_SESSIONS" -gt 0 ]; then
            SESSION_MEM=$(echo "scale=2; $MEM_USAGE * 1024 / $ACTIVE_SESSIONS" | bc)
        else
            SESSION_MEM="N/A"
        fi
        
        echo "$(date '+%Y-%m-%d %H:%M:%S'),$TARGET_SESSIONS,$ACTIVE_SESSIONS,$((i*15)),$MEM_USAGE,$SESSION_MEM,N/A,N/A" >> $RESULTS_DIR/session_capacity_results.csv
    done
    
    wait $CLIENT_PID
    
    # 记录最终结果
    if [ -f "$RESULTS_DIR/session_test_${TARGET_SESSIONS}.json" ]; then
        FINAL_SESSIONS=$(cat $RESULTS_DIR/session_test_${TARGET_SESSIONS}.json | jq -r '.activeSessions // 0')
        echo "测试完成，最终活跃会话: $FINAL_SESSIONS"
    fi
    
    sleep 30
done
```

#### 2.3 插件并发调用测试

```bash
#!/bin/bash
# 测试多插件并发调用性能

TEST_DIR=~/multi_dim_test
RESULTS_DIR=$TEST_DIR/results

# 插件并发数序列
PLUGIN_CONCURRENCY=(5 10 20 40 80 160)
PLUGINS=("web-search" "weather" "github" "memory" "tts")
DURATION=180

echo "timestamp,plugin_concurrency,active_plugins,total_calls,success_rate,avg_latency,plugin_cpu_impact,error_count" > $RESULTS_DIR/plugin_concurrency_results.csv

for CONC in "${PLUGIN_CONCURRENCY[@]}"; do
    echo "========================================"
    echo "开始测试: $CONC 并发插件调用"
    echo "时间: $(date)"
    echo "========================================"
    
    # 记录测试前 CPU
    CPU_BEFORE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    
    # 运行多插件并发测试
    node automation_assets/client.js \
        --config test_case_base/performance_case/multi-dim-concurrency-config.json \
        --mode plugin-stress \
        --plugins "${PLUGINS[@]}" \
        --plugin-concurrency $CONC \
        --duration $DURATION \
        --output $RESULTS_DIR/plugin_test_${CONC}.json
    
    # 记录测试后 CPU
    CPU_AFTER=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    CPU_IMPACT=$(echo "$CPU_AFTER - $CPU_BEFORE" | bc)
    
    if [ -f "$RESULTS_DIR/plugin_test_${CONC}.json" ]; then
        RESULT=$(cat $RESULTS_DIR/plugin_test_${CONC}.json)
        TOTAL_CALLS=$(echo $RESULT | jq -r '.totalCalls // 0')
        SUCCESS_RATE=$(echo $RESULT | jq -r '.successRate // 0')
        AVG_LAT=$(echo $RESULT | jq -r '.avgLatency // 0')
        ERROR_COUNT=$(echo $RESULT | jq -r '.errorCount // 0')
        
        echo "$(date '+%Y-%m-%d %H:%M:%S'),$CONC,${#PLUGINS[@]},$TOTAL_CALLS,$SUCCESS_RATE,$AVG_LAT,$CPU_IMPACT,$ERROR_COUNT" >> $RESULTS_DIR/plugin_concurrency_results.csv
    fi
    
    sleep 30
done
```

#### 2.4 消息速率递增测试

```bash
#!/bin/bash
# 测试消息吞吐量极限

TEST_DIR=~/multi_dim_test
RESULTS_DIR=$TEST_DIR/results

# 消息速率序列 (msg/s)
MESSAGE_RATES=(100 200 400 800 1600 3200)
DURATION=180
CONCURRENT_USERS=50

echo "timestamp,target_rate,actual_rate,duration,success_rate,avg_latency,p95_latency,p99_latency,dropped_messages,cpu_peak,mem_peak" > $RESULTS_DIR/message_throughput_results.csv

for RATE in "${MESSAGE_RATES[@]}"; do
    echo "========================================"
    echo "开始测试: $RATE msg/s 消息速率"
    echo "时间: $(date)"
    echo "========================================"
    
    # 计算每个用户的发送间隔
    INTERVAL=$((1000 * CONCURRENT_USERS / RATE))  # ms
    
    node automation_assets/client.js \
        --config test_case_base/performance_case/multi-dim-concurrency-config.json \
        --concurrent $CONCURRENT_USERS \
        --interval $INTERVAL \
        --duration $DURATION \
        --output $RESULTS_DIR/rate_test_${RATE}.json
    
    if [ -f "$RESULTS_DIR/rate_test_${RATE}.json" ]; then
        RESULT=$(cat $RESULTS_DIR/rate_test_${RATE}.json)
        ACTUAL_RATE=$(echo $RESULT | jq -r '.actualRate // 0')
        SUCCESS_RATE=$(echo $RESULT | jq -r '.successRate // 0')
        AVG_LAT=$(echo $RESULT | jq -r '.avgLatency // 0')
        P95_LAT=$(echo $RESULT | jq -r '.p95Latency // 0')
        P99_LAT=$(echo $RESULT | jq -r '.p99Latency // 0')
        DROPPED=$(echo $RESULT | jq -r '.droppedMessages // 0')
        
        # 峰值资源使用
        CPU_PEAK=$(grep -v timestamp $TEST_DIR/monitoring/system_metrics.csv | tail -n 36 | awk -F',' 'BEGIN{max=0} {if($2>max) max=$2} END{print max}')
        MEM_PEAK=$(grep -v timestamp $TEST_DIR/monitoring/system_metrics.csv | tail -n 36 | awk -F',' 'BEGIN{max=0} {if($5>max) max=$5} END{print max}')
        
        echo "$(date '+%Y-%m-%d %H:%M:%S'),$RATE,$ACTUAL_RATE,$DURATION,$SUCCESS_RATE,$AVG_LAT,$P95_LAT,$P99_LAT,$DROPPED,$CPU_PEAK,$MEM_PEAK" >> $RESULTS_DIR/message_throughput_results.csv
    fi
    
    sleep 30
done
```

### 步骤 3：多维度组合测试

```bash
#!/bin/bash
# 组合测试：同时变化多个维度

TEST_DIR=~/multi_dim_test
RESULTS_DIR=$TEST_DIR/results

echo "timestamp,users,sessions,plugins,msg_rate,duration,success_rate,avg_lat,p95_lat,p99_lat,tps,cpu_avg,mem_gb,notes" > $RESULTS_DIR/combined_load_results.csv

# 定义组合测试场景
declare -a SCENARIOS=(
    "10,50,5,100"
    "20,100,10,200"
    "40,200,20,400"
    "80,400,40,800"
    "160,800,80,1600"
    "320,1600,160,3200"
)

for SCENARIO in "${SCENARIOS[@]}"; do
    IFS=',' read -r USERS SESSIONS PLUGINS MSG_RATE <<< "$SCENARIO"
    
    echo "========================================"
    echo "组合测试场景:"
    echo "  用户数: $USERS"
    echo "  会话数: $SESSIONS"
    echo "  插件数: $PLUGINS"
    echo "  消息率: $MSG_RATE msg/s"
    echo "时间: $(date)"
    echo "========================================"
    
    DURATION=300  # 5 分钟
    
    node automation_assets/client.js \
        --config test_case_base/performance_case/multi-dim-concurrency-config.json \
        --mode combined \
        --users $USERS \
        --sessions $SESSIONS \
        --plugins $PLUGINS \
        --message-rate $MSG_RATE \
        --duration $DURATION \
        --output $RESULTS_DIR/combined_${USERS}_${SESSIONS}_${PLUGINS}_${MSG_RATE}.json
    
    if [ -f "$RESULTS_DIR/combined_${USERS}_${SESSIONS}_${PLUGINS}_${MSG_RATE}.json" ]; then
        RESULT=$(cat $RESULTS_DIR/combined_${USERS}_${SESSIONS}_${PLUGINS}_${MSG_RATE}.json)
        SUCCESS_RATE=$(echo $RESULT | jq -r '.successRate // 0')
        AVG_LAT=$(echo $RESULT | jq -r '.avgLatency // 0')
        P95_LAT=$(echo $RESULT | jq -r '.p95Latency // 0')
        P99_LAT=$(echo $RESULT | jq -r '.p99Latency // 0')
        TPS=$(echo $RESULT | jq -r '.tps // 0')
        
        # 系统指标
        CPU_AVG=$(tail -n 60 $TEST_DIR/monitoring/system_metrics.csv | awk -F',' '{sum+=$2} END {printf "%.2f", sum/NR}')
        MEM_GB=$(tail -n 1 $TEST_DIR/monitoring/system_metrics.csv | awk -F',' '{printf "%.2f", $5/1024}')
        
        # 判断是否通过
        NOTES="OK"
        if (( $(echo "$SUCCESS_RATE < 95" | bc -l) )); then
            NOTES="LOW_SUCCESS_RATE"
        elif (( $(echo "$P95_LAT > 1000" | bc -l) )); then
            NOTES="HIGH_LATENCY"
        fi
        
        echo "$(date '+%Y-%m-%d %H:%M:%S'),$USERS,$SESSIONS,$PLUGINS,$MSG_RATE,$DURATION,$SUCCESS_RATE,$AVG_LAT,$P95_LAT,$P99_LAT,$TPS,$CPU_AVG,$MEM_GB,$NOTES" >> $RESULTS_DIR/combined_load_results.csv
    fi
    
    # 组合测试后需要更长恢复时间
    sleep 60
done
```

### 步骤 4：性能曲线分析与拐点识别

```bash
#!/bin/bash
# 分析性能曲线并识别拐点

TEST_DIR=~/multi_dim_test
RESULTS_DIR=$TEST_DIR/results
ANALYSIS_DIR=$TEST_DIR/analysis
mkdir -p $ANALYSIS_DIR

cat > $ANALYSIS_DIR/analyze_curves.py << 'PYTHON_EOF'
#!/usr/bin/env python3
import pandas as pd
import numpy as np
from scipy import stats
import json
import sys

def calculate_r_squared(x, y):
    """计算 R² 决定系数，评估曲线线性度"""
    if len(x) < 2:
        return 0
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return r_value ** 2

def find_inflection_point(x, y):
    """通过二阶导数寻找拐点"""
    if len(x) < 3:
        return None
    
    # 计算一阶和二阶差分
    dy = np.diff(y)
    d2y = np.diff(dy)
    
    # 寻找二阶差分最大的点（变化最剧烈的地方）
    if len(d2y) > 0:
        inflection_idx = np.argmax(np.abs(d2y)) + 1
        return x[inflection_idx] if inflection_idx < len(x) else None
    return None

def find_saturation_point(x, y, threshold=0.1):
    """寻找饱和点：增长率低于阈值的位置"""
    if len(x) < 2:
        return None
    
    for i in range(1, len(x)):
        if x[i-1] > 0 and y[i-1] > 0:
            growth_rate = (y[i] - y[i-1]) / y[i-1]
            if growth_rate < threshold:
                return x[i]
    return None

def analyze_curve(file_path, x_col, y_cols):
    """分析性能曲线"""
    df = pd.read_csv(file_path)
    results = {}
    
    for y_col in y_cols:
        if y_col not in df.columns:
            continue
            
        x = df[x_col].values
        y = df[y_col].values
        
        # 过滤掉无效值
        mask = ~(np.isnan(x) | np.isnan(y) | np.isinf(x) | np.isinf(y))
        x_clean = x[mask]
        y_clean = y[mask]
        
        if len(x_clean) < 2:
            continue
        
        analysis = {
            'r_squared': calculate_r_squared(x_clean, y_clean),
            'inflection_point': find_inflection_point(x_clean, y_clean),
            'saturation_point': find_saturation_point(x_clean, y_clean),
            'max_value': float(np.max(y_clean)),
            'min_value': float(np.min(y_clean)),
            'avg_value': float(np.mean(y_clean)),
            'trend': 'increasing' if y_clean[-1] > y_clean[0] else 'decreasing'
        }
        
        results[y_col] = analysis
    
    return results

# 分析各个维度的曲线
print("=== OpenClaw 多维度并发性能曲线分析 ===\n")

# 1. 用户并发曲线
if __import__('os').path.exists('results/user_concurrency_results.csv'):
    print("【用户并发维度】")
    user_results = analyze_curve(
        'results/user_concurrency_results.csv',
        'concurrent_users',
        ['success_rate', 'p95_latency_ms', 'tps', 'cpu_avg']
    )
    print(json.dumps(user_results, indent=2))
    print()

# 2. 会话容量曲线
if __import__('os').path.exists('results/session_capacity_results.csv'):
    print("【会话容量维度】")
    session_results = analyze_curve(
        'results/session_capacity_results.csv',
        'target_sessions',
        ['memory_mb', 'session_memory_kb']
    )
    print(json.dumps(session_results, indent=2))
    print()

# 3. 插件并发曲线
if __import__('os').path.exists('results/plugin_concurrency_results.csv'):
    print("【插件并发维度】")
    plugin_results = analyze_curve(
        'results/plugin_concurrency_results.csv',
        'plugin_concurrency',
        ['success_rate', 'avg_latency', 'plugin_cpu_impact']
    )
    print(json.dumps(plugin_results, indent=2))
    print()

# 4. 消息吞吐曲线
if __import__('os').path.exists('results/message_throughput_results.csv'):
    print("【消息吞吐维度】")
    throughput_results = analyze_curve(
        'results/message_throughput_results.csv',
        'target_rate',
        ['actual_rate', 'success_rate', 'p95_latency']
    )
    print(json.dumps(throughput_results, indent=2))
    print()

# 5. 综合评估
print("\n=== 性能曲线可解释性评估 ===")
interpretability_score = 0
checks = []

# 检查各个维度是否呈现可预期的曲线
if 'user_results' in dir() or 'user_results' in vars():
    if user_results.get('p95_latency_ms', {}).get('r_squared', 0) > 0.8:
        checks.append("✅ 用户并发-P95延迟曲线线性度良好 (R²>0.8)")
        interpretability_score += 20
    else:
        checks.append("⚠️ 用户并发-P95延迟曲线非线性，可能存在突发瓶颈")

if 'throughput_results' in dir() or 'throughput_results' in vars():
    saturation = throughput_results.get('actual_rate', {}).get('saturation_point')
    if saturation:
        checks.append(f"✅ 消息吞吐在 {saturation} msg/s 处发现饱和点")
        interpretability_score += 20
    else:
        checks.append("ℹ️ 消息吞吐未检测到明显饱和点（可能未达到极限）")

for check in checks:
    print(check)

print(f"\n综合可解释性评分: {interpretability_score}/100")
if interpretability_score >= 80:
    print("评级: A - 性能曲线高度可解释，系统行为符合预期")
elif interpretability_score >= 60:
    print("评级: B - 性能曲线基本可解释，存在少量异常")
elif interpretability_score >= 40:
    print("评级: C - 性能曲线部分可解释，需要深入分析")
else:
    print("评级: D - 性能曲线难以解释，系统存在严重问题")
PYTHON_EOF

chmod +x $ANALYSIS_DIR/analyze_curves.py

echo "性能曲线分析脚本已生成"
echo "运行分析: cd $TEST_DIR && python3 $ANALYSIS_DIR/analyze_curves.py"
```

## 预期结果

### 性能曲线预期特征

| 曲线类型 | 预期形状 | 可解释性标准 |
|----------|----------|--------------|
| **延迟-负载曲线** | 初始平缓，拐点后线性/指数增长 | 应呈现清晰的拐点，而非突变 |
| **吞吐-负载曲线** | 初始线性增长，饱和后 plateau | TPS 应在饱和点前与负载成正比 |
| **资源-负载曲线** | 近似线性增长 | CPU/内存 应与负载呈正相关 |
| **成功率-负载曲线** | 保持水平后陡降 | 在达到容量前应保持 99%+ |

### 可解释性能曲线特征

1. **单调性**：核心指标（延迟、资源使用）应随负载单调递增
2. **连续性**：曲线应平滑，无突发跳变
3. **可预测性**：通过低负载点应能推断高负载行为
4. **拐点明确**：性能拐点应清晰可识别，而非模糊区域

## 通过标准

- ✅ 所有单维度测试通过率 ≥ 95%
- ✅ 性能曲线 R² 线性度 ≥ 0.85（低负载区域）
- ✅ 组合负载成功率 ≥ 90%
- ✅ 系统在所有测试负载下保持可用
- ✅ 性能拐点清晰可识别
- ✅ 资源使用与负载呈正相关

## 失败标准

- ❌ 任何测试负载点成功率 < 85%
- ❌ 性能曲线出现不可解释的突变或回退
- ❌ 高负载下出现死锁或阻塞
- ❌ 资源使用与负载无正相关关系
- ❌ 系统崩溃或无法恢复

## 数据分析脚本

### 性能曲线可视化

```python
#!/usr/bin/env python3
# 生成性能曲线可视化图表
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def plot_performance_curves():
    # 用户并发曲线
    user_df = pd.read_csv('results/user_concurrency_results.csv')
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 延迟曲线
    ax1 = axes[0, 0]
    ax1.plot(user_df['concurrent_users'], user_df['p95_latency_ms'], 'b-o', label='P95 Latency')
    ax1.plot(user_df['concurrent_users'], user_df['p99_latency_ms'], 'r-s', label='P99 Latency')
    ax1.set_xlabel('Concurrent Users')
    ax1.set_ylabel('Latency (ms)')
    ax1.set_title('Latency vs Concurrent Users')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 吞吐曲线
    ax2 = axes[0, 1]
    ax2.plot(user_df['concurrent_users'], user_df['tps'], 'g-^', label='Throughput')
    ax2.set_xlabel('Concurrent Users')
    ax2.set_ylabel('TPS')
    ax2.set_title('Throughput vs Concurrent Users')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 资源曲线
    ax3 = axes[1, 0]
    ax3.plot(user_df['concurrent_users'], user_df['cpu_avg'], 'y-D', label='CPU %')
    ax3_twin = ax3.twinx()
    ax3_twin.plot(user_df['concurrent_users'], user_df['mem_avg'], 'm-s', label='Memory MB')
    ax3.set_xlabel('Concurrent Users')
    ax3.set_ylabel('CPU %', color='y')
    ax3_twin.set_ylabel('Memory MB', color='m')
    ax3.set_title('Resource Usage vs Concurrent Users')
    ax3.legend(loc='upper left')
    ax3_twin.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    
    # 成功率曲线
    ax4 = axes[1, 1]
    ax4.plot(user_df['concurrent_users'], user_df['success_rate'] * 100, 'c-o', label='Success Rate')
    ax4.axhline(y=95, color='r', linestyle='--', label='95% Threshold')
    ax4.set_xlabel('Concurrent Users')
    ax4.set_ylabel('Success Rate (%)')
    ax4.set_title('Success Rate vs Concurrent Users')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('performance_curves.png', dpi=150, bbox_inches='tight')
    print("性能曲线图已保存: performance_curves.png")

if __name__ == '__main__':
    plot_performance_curves()
```

## 注意事项

1. **测试顺序**：建议按单维度→组合维度的顺序执行，避免相互干扰
2. **系统恢复**：每个测试负载点后应等待系统完全恢复再进行下一次测试
3. **数据备份**：测试前备份重要配置和数据
4. **监控粒度**：系统监控建议 5 秒采集一次，确保证捕捉到突变
5. **日志管理**：高频测试可能产生大量日志，确保磁盘空间充足
6. **网络隔离**：建议在隔离网络环境执行，避免影响生产流量

## 扩展测试

- **长时间曲线稳定性**：保持中等负载运行 24 小时，观察曲线是否漂移
- **突发负载测试**：从低负载瞬间跳到高负载，观察恢复曲线
- **降级测试**：在部分组件故障时测试性能曲线变化
- **对比测试**：不同版本/配置下的性能曲线对比

---

**测试记录模板**：

| 时间 | 测试维度 | 负载参数 | P95延迟 | TPS | 成功率 | CPU | 内存 | 备注 |
|------|----------|----------|---------|-----|--------|-----|------|------|
| | | | | | | | | |
