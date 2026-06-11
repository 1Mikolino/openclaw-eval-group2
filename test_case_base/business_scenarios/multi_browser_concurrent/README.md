# 多浏览器并发压力测试

## 概述

本测试用例用于模拟真实业务场景中的多浏览器并发，监测系统资源占用情况（CPU、内存），并探测系统崩溃临界点。

## 测试目标

1. **评估系统承载能力**: 确定OpenClaw在多浏览器并发场景下的性能极限
2. **发现资源瓶颈**: 识别CPU、内存、IO等关键资源的瓶颈
3. **探测崩溃临界点**: 找出导致系统不稳定的并发浏览器数量
4. **建立性能基线**: 为后续版本回归测试提供参考数据

## 测试原理

```
┌─────────────────────────────────────────────────────────────┐
│                   多浏览器并发测试架构                         │
├─────────────────────────────────────────────────────────────┤
│  Test Controller                                            │
│       │                                                     │
│       ├── 监控线程 ──→ 实时采集 CPU/内存/负载                │
│       │                                                     │
│       └── 浏览器池 ──→ 并发管理多个浏览器会话                 │
│               │                                             │
│               ├── 浏览器 #1 ──→ 打开页面 ──→ 执行操作        │
│               ├── 浏览器 #2 ──→ 打开页面 ──→ 执行操作        │
│               ├── 浏览器 #3 ──→ 打开页面 ──→ 执行操作        │
│               └── ...                                       │
└─────────────────────────────────────────────────────────────┘
```

## 文件说明

| 文件 | 说明 |
|-----|------|
| `multi_browser_concurrent_test.py` | 主测试脚本 |
| `test_config.json` | 测试配置参数 |
| `README.md` | 本文档 |

## 使用方法

### 1. 安装依赖

```bash
pip install psutil
```

### 2. 运行测试

```bash
# 使用默认配置（最多20个并发浏览器）
python multi_browser_concurrent_test.py

# 指定并发浏览器数量
python multi_browser_concurrent_test.py 10
python multi_browser_concurrent_test.py 50
```

### 3. 查看结果

测试完成后会生成JSON格式的报告文件：
```
browser_concurrent_test_20260611_215000.json
```

### 4. 分析指标

报告包含以下关键指标：
- `peak_cpu_percent`: CPU使用率峰值
- `peak_memory_percent`: 内存使用率峰值
- `peak_browser_count`: 峰值浏览器数量
- `crash_analysis`: 崩溃分析（如发生）

## 测试场景

### 场景1: 基线测试
```bash
python multi_browser_concurrent_test.py 5
```
验证系统在轻负载下的稳定性。

### 场景2: 标准负载测试
```bash
python multi_browser_concurrent_test.py 10
```
模拟正常业务场景的并发量。

### 场景3: 压力测试
```bash
python multi_browser_concurrent_test.py 20
```
测试系统在高负载下的表现。

### 场景4: 极限测试
```bash
python multi_browser_concurrent_test.py 50
```
探测系统崩溃临界点。

## 配置说明

编辑 `test_config.json` 修改测试参数：

```json
{
  "max_concurrent_browsers": 20,    // 最大并发数
  "browser_start_delay": 2,          // 启动间隔
  "test_duration_per_browser": 60,   // 每个浏览器运行时长
  "memory_warning": 85,              // 内存告警阈值(%)
  "cpu_warning": 80                  // CPU告警阈值(%)
}
```

## 预期结果

### 正常情况
- 系统在配置的并发数下稳定运行
- 内存增长率 < 20MB/分钟
- 无浏览器进程崩溃

### 资源告警
- 内存使用超过85%时输出告警
- CPU使用超过80%时输出告警

### 崩溃检测
- 内存使用超过95%时自动停止测试
- 记录崩溃时的浏览器数量和资源状态

## 集成到CI/CD

```yaml
# .github/workflows/browser-stress-test.yml
name: Browser Stress Test

on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点运行

jobs:
  stress-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install psutil
      - name: Run stress test
        run: python test_case_base/business_scenarios/multi_browser_concurrent_test.py 20
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: stress-test-report
          path: browser_concurrent_test_*.json
```

## 注意事项

1. **资源占用**: 测试会占用大量系统资源，建议在专用测试环境运行
2. **真实浏览器**: 本测试使用模拟浏览器，真实测试需要集成实际浏览器自动化工具
3. **内存限制**: 如果系统内存小于4GB，建议降低 `max_concurrent_browsers`
4. **超时设置**: 根据系统性能调整 `test_duration_per_browser`

## 版本历史

| 版本 | 日期 | 说明 |
|-----|------|-----|
| 1.0.0 | 2026-06-11 | 初始版本 |

## 作者

OpenClaw Eval Group 2
