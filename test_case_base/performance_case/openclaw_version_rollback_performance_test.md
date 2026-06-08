# OpenClaw 版本升级/降级/回滚性能回退测试用例

## 基本信息

| 项目 | 内容 |
|------|------|
| 用例编号 | PERF-007 |
| 用例名称 | OpenClaw 版本升级/降级/回滚性能回退测试 |
| 优先级 | P0 (高) |
| 测试类型 | 版本兼容性测试 / 性能回归测试 |
| 创建日期 | 2026-06-08 |

## 测试目的

验证 OpenClaw 在进行版本升级、降级和回滚操作前后，系统性能是否出现回退或资源使用异常，包括：
- 版本升级前后的性能对比（基线版本 → 新版本）
- 版本降级前后的性能对比（新版本 → 旧版本）
- 紧急回滚操作后的性能恢复验证
- 内存、CPU、延迟、吞吐量等关键指标的变化检测
- 资源泄漏或异常占用检测
- 配置兼容性和数据持久性验证

## 前置条件

1. 测试环境已准备至少三个可切换的 OpenClaw 版本（旧版、基准版、新版）
2. 每个版本已预编译/打包，可快速部署
3. 版本切换脚本已准备就绪
4. 性能基准数据已收集（至少运行3次取平均值）
5. 数据库/配置备份机制已就位
6. 监控和日志收集工具已配置

## 测试环境

| 配置项 | 要求 |
|--------|------|
| CPU | 4 核及以上 |
| 内存 | 8GB 及以上 |
| 磁盘空间 | 10GB+ 可用空间 |
| 操作系统 | Linux (Ubuntu 20.04+) |
| Node.js | v18+ |
| OpenClaw 版本 | 旧版(v1.x)、基准版(v2.x)、新版(v3.x) |
| 网络 | 稳定的内网连接 |

## 版本定义

| 版本角色 | 版本号示例 | 用途 |
|----------|------------|------|
| 旧版本 (OLD) | v1.2.0 | 降级目标版本 |
| 基准版本 (BASE) | v2.0.0 | 当前生产/参考版本 |
| 新版本 (NEW) | v3.0.0 | 升级目标版本 |

## 测试步骤

### 阶段 1: 基线数据收集（基准版本）

#### 步骤 1.1: 部署基准版本

```bash
# 1. 清理环境
openclaw stop 2>/dev/null
sleep 2
pkill -f openclaw 2>/dev/null

# 2. 备份现有数据（如有）
mkdir -p /backup/openclaw-$(date +%Y%m%d)
cp -r ~/.openclaw/data /backup/openclaw-$(date +%Y%m%d)/ 2>/dev/null || true

# 3. 部署基准版本
echo "部署基准版本 v2.0.0..."
cd /opt/openclaw
./deploy.sh v2.0.0

# 4. 验证版本
openclaw version
echo "基准版本部署完成: $(date '+%Y-%m-%d %H:%M:%S')"
```

#### 步骤 1.2: 运行基准性能测试

```bash
cd automation_assets

# 运行5分钟基线测试
node client.js --config ../test_case_base/performance_case/version-rollback-base-config.json

# 记录基准结果
echo "=== 基准版本性能数据 ===" > ~/version_test/baseline_results.log
cat ~/monitoring/metrics.json >> ~/version_test/baseline_results.log
echo "基准测试完成: $(date '+%Y-%m-%d %H:%M:%S')" >> ~/version_test/baseline_results.log
```

收集以下基线指标：
- 平均响应时间 (Avg Latency)
- P95/P99 延迟
- 消息成功率
- 内存占用 (初始/峰值)
- CPU 平均使用率
- 吞吐量 (messages/sec)

---

### 阶段 2: 升级测试（基准版 → 新版本）

#### 步骤 2.1: 执行版本升级

```bash
# 1. 记录升级前状态
echo "=== 升级前状态 ===" > ~/version_test/upgrade_test.log
openclaw status >> ~/version_test/upgrade_test.log
free -h >> ~/version_test/upgrade_test.log

# 2. 优雅停止服务
openclaw stop
sleep 5

# 3. 执行升级（保留数据）
echo "开始升级到 v3.0.0..."
cd /opt/openclaw
./deploy.sh v3.0.0 --preserve-data

# 4. 启动新版本
openclaw start
sleep 10

# 5. 验证升级成功
echo "=== 升级后状态 ===" >> ~/version_test/upgrade_test.log
openclaw version >> ~/version_test/upgrade_test.log
openclaw status >> ~/version_test/upgrade_test.log
```

#### 步骤 2.2: 升级后性能验证

```bash
cd automation_assets

# 运行相同配置的性能测试
node client.js --config ../test_case_base/performance_case/version-rollback-base-config.json

# 记录升级后结果
echo "=== 升级后性能数据 ===" >> ~/version_test/upgrade_test.log
cat ~/monitoring/metrics.json >> ~/version_test/upgrade_test.log
echo "升级后测试完成: $(date '+%Y-%m-%d %H:%M:%S')" >> ~/version_test/upgrade_test.log
```

#### 步骤 2.3: 升级性能对比分析

对比以下指标变化：

| 指标 | 基准版本 | 升级后 | 变化率 | 阈值 | 结果 |
|------|----------|--------|--------|------|------|
| 平均延迟 | | | ≤ 20% | | |
| P95 延迟 | | | ≤ 30% | | |
| 成功率 | | | ≥ -5% | | |
| 内存占用 | | | ≤ 15% | | |
| CPU 使用率 | | | ≤ 20% | | |
| 吞吐量 | | | ≥ -10% | | |

---

### 阶段 3: 降级测试（新版本 → 旧版本）

#### 步骤 3.1: 执行版本降级

```bash
# 1. 记录降级前状态
echo "=== 降级前状态 ===" > ~/version_test/downgrade_test.log
openclaw status >> ~/version_test/downgrade_test.log

# 2. 优雅停止服务
openclaw stop
sleep 5

# 3. 执行降级（检查兼容性警告）
echo "开始降级到 v1.2.0..."
cd /opt/openclaw
./deploy.sh v1.2.0 --preserve-data --check-compat

# 4. 启动旧版本
openclaw start
sleep 10

# 5. 验证降级成功
echo "=== 降级后状态 ===" >> ~/version_test/downgrade_test.log
openclaw version >> ~/version_test/downgrade_test.log
openclaw status >> ~/version_test/downgrade_test.log
```

#### 步骤 3.2: 降级后性能验证

```bash
cd automation_assets

# 运行性能测试
node client.js --config ../test_case_base/performance_case/version-rollback-base-config.json

# 记录降级后结果
echo "=== 降级后性能数据 ===" >> ~/version_test/downgrade_test.log
cat ~/monitoring/metrics.json >> ~/version_test/downgrade_test.log
```

---

### 阶段 4: 回滚测试（模拟生产故障回滚）

#### 步骤 4.1: 模拟生产场景并触发回滚

```bash
# 1. 先升级到新版（模拟生产升级）
openclaw stop
./deploy.sh v3.0.0
openclaw start
sleep 10

# 2. 模拟运行一段时间
sleep 60

# 3. 模拟发现严重问题（如内存泄漏、高延迟）
# 这里通过日志检测或人工标记触发回滚
echo "检测到性能异常，触发紧急回滚..." >> ~/version_test/rollback_test.log

# 4. 执行紧急回滚
ROLLBACK_START=$(date +%s)
openclaw stop
sleep 2
cd /opt/openclaw
./deploy.sh v2.0.0 --rollback-mode
openclaw start
ROLLBACK_END=$(date +%s)

# 计算回滚耗时
ROLLBACK_TIME=$((ROLLBACK_END - ROLLBACK_START))
echo "回滚耗时: ${ROLLBACK_TIME} 秒" >> ~/version_test/rollback_test.log
```

#### 步骤 4.2: 回滚后性能恢复验证

```bash
cd automation_assets

# 立即进行性能测试
node client.js --config ../test_case_base/performance_case/version-rollback-base-config.json

echo "=== 回滚后性能数据 ===" >> ~/version_test/rollback_test.log
cat ~/monitoring/metrics.json >> ~/version_test/rollback_test.log
```

#### 步骤 4.3: 回滚效果评估

对比回滚后与基准版本的性能差异：
- 回滚后性能是否恢复到基准水平（误差 ≤ 10%）
- 回滚操作本身是否引入新的问题
- 数据完整性和配置一致性检查

---

### 阶段 5: 资源异常检测

#### 步骤 5.1: 内存泄漏检测

```bash
# 检查各版本内存趋势
#!/bin/bash
check_memory_trend() {
    local version=$1
    local log_file=$2
    
    echo "=== ${version} 内存趋势分析 ===" >> ~/version_test/memory_analysis.log
    
    # 提取内存使用数据
    grep "Mem:" ${log_file} | awk '{print NR, $3}' > /tmp/mem_${version}.dat
    
    # 计算内存增长率（简单线性回归）
    local start_mem=$(head -1 /tmp/mem_${version}.dat | awk '{print $2}')
    local end_mem=$(tail -1 /tmp/mem_${version}.dat | awk '{print $2}')
    local growth=$((end_mem - start_mem))
    
    echo "起始内存: ${start_mem}MB" >> ~/version_test/memory_analysis.log
    echo "结束内存: ${end_mem}MB" >> ~/version_test/memory_analysis.log
    echo "内存增长: ${growth}MB" >> ~/version_test/memory_analysis.log
    
    # 判断是否超过阈值
    if [ $growth -gt 100 ]; then
        echo "⚠️ 警告: ${version} 内存增长超过100MB，可能存在内存泄漏" >> ~/version_test/memory_analysis.log
    fi
}

check_memory_trend "baseline" "~/monitoring/baseline_monitor.log"
check_memory_trend "upgrade" "~/monitoring/upgrade_monitor.log"
check_memory_trend "downgrade" "~/monitoring/downgrade_monitor.log"
check_memory_trend "rollback" "~/monitoring/rollback_monitor.log"
```

#### 步骤 5.2: CPU 异常检测

```bash
#!/bin/bash
check_cpu_anomalies() {
    local version=$1
    local metrics_file=$2
    
    echo "=== ${version} CPU 分析 ===" >> ~/version_test/cpu_analysis.log
    
    # 提取 CPU 使用数据并计算统计值
    cpu_avg=$(jq '.cpuUsage.avg' ${metrics_file})
    cpu_max=$(jq '.cpuUsage.max' ${metrics_file})
    
    echo "平均 CPU: ${cpu_avg}%" >> ~/version_test/cpu_analysis.log
    echo "峰值 CPU: ${cpu_max}%" >> ~/version_test/cpu_analysis.log
    
    # 检测异常高的 CPU
    if (( $(echo "${cpu_avg} > 80" | bc -l) )); then
        echo "❌ 平均 CPU 超过80%，存在性能问题" >> ~/version_test/cpu_analysis.log
    fi
}
```

## 预期结果

### 升级测试预期

| 检查项 | 预期结果 |
|--------|----------|
| 升级成功率 | 100%（服务正常启动） |
| 升级时间 | ≤ 60 秒 |
| 平均延迟变化 | ≤ 基准版本的 20% |
| 成功率变化 | ≥ 基准版本的 -5% |
| 内存变化 | ≤ 基准版本的 15% |

### 降级测试预期

| 检查项 | 预期结果 |
|--------|----------|
| 降级成功率 | 100%（或明确提示不兼容） |
| 数据兼容性 | 配置和数据可正常读取 |
| 性能恢复 | 降回基准或接近基准水平 |

### 回滚测试预期

| 检查项 | 预期结果 |
|--------|----------|
| 回滚时间 | ≤ 30 秒（紧急回滚） |
| 回滚成功率 | 100% |
| 性能恢复 | 恢复到基准水平的 90% 以上 |
| 数据完整性 | 无数据丢失或损坏 |

## 通过标准

- ✅ 升级后性能下降不超过 20%
- ✅ 降级操作能成功完成且数据兼容
- ✅ 回滚操作在 30 秒内完成
- ✅ 回滚后性能恢复到基准的 90% 以上
- ✅ 各版本间切换无内存泄漏（每小时增长 < 50MB）
- ✅ 切换过程中服务中断时间 < 30 秒
- ✅ 配置和数据在版本间正确迁移

## 失败标准

- ❌ 升级后性能下降超过 20%
- ❌ 降级失败或数据不兼容导致无法启动
- ❌ 回滚后性能无法恢复到基准的 85%
- ❌ 发现明显的内存泄漏（每小时增长 > 100MB）
- ❌ 版本切换导致数据丢失或损坏
- ❌ 回滚时间超过 60 秒（不满足 SLA）

## 测试报告模板

```markdown
# 版本升级/降级/回滚性能测试报告

## 测试概览
- 测试日期: YYYY-MM-DD
- 测试版本: v1.2.0 → v2.0.0 → v3.0.0
- 测试执行人: 
- 测试结论: 通过 / 不通过

## 详细结果

### 基线数据 (v2.0.0)
| 指标 | 数值 |
|------|------|
| 平均延迟 | XX ms |
| P95 延迟 | XX ms |
| 成功率 | XX% |
| 内存占用 | XX MB |
| CPU 平均 | XX% |

### 升级结果 (v2.0.0 → v3.0.0)
| 指标 | 基线 | 升级后 | 变化 | 结果 |
|------|------|--------|------|------|
| 平均延迟 | | | | |
| 成功率 | | | | |
| 内存 | | | | |

### 降级结果 (v3.0.0 → v1.2.0)
...

### 回滚结果 (v3.0.0 → v2.0.0)
...

## 问题记录
| 问题ID | 描述 | 严重程度 | 状态 |
|--------|------|----------|------|
| ISSUE-1 | | | |

## 结论与建议
```

## 自动化脚本

版本切换自动化脚本 `version_switch.sh`:

```bash
#!/bin/bash
set -e

VERSION=$1
ACTION=$2  # upgrade/downgrade/rollback

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a ~/version_test/switch.log
}

log "开始版本切换: ${ACTION} 到 ${VERSION}"

# 停止当前服务
log "停止当前服务..."
openclaw stop || true
sleep 3

# 备份配置
BACKUP_DIR=/backup/pre-${ACTION}-$(date +%Y%m%d-%H%M%S)
mkdir -p ${BACKUP_DIR}
cp -r ~/.openclaw/* ${BACKUP_DIR}/ 2>/dev/null || true
log "配置已备份到 ${BACKUP_DIR}"

# 部署新版本
cd /opt/openclaw
./deploy.sh ${VERSION}

# 启动服务
openclaw start
sleep 10

# 验证
if openclaw status | grep -q "running"; then
    log "✅ 版本切换成功: ${VERSION}"
    openclaw version
else
    log "❌ 版本切换失败"
    exit 1
fi
```

## 注意事项

1. **数据备份** - 每次切换前自动备份配置和数据
2. **兼容性检查** - 降级前检查版本兼容性矩阵
3. **监控连续性** - 版本切换期间保持监控不断
4. **快速回滚准备** - 确保紧急情况下能立即回滚
5. **测试数据隔离** - 使用独立测试数据避免影响生产

## 相关文件

- 测试配置文件: `version-rollback-base-config.json`
- 基线数据: `~/version_test/baseline_results.log`
- 升级记录: `~/version_test/upgrade_test.log`
- 降级记录: `~/version_test/downgrade_test.log`
- 回滚记录: `~/version_test/rollback_test.log`
