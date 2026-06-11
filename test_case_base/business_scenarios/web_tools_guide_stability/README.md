# Web-Tools-Guide Skill 稳定性测试

## 概述

本测试用例用于检验 `web-tools-guide` skill 在高频调用场景下的稳定性，监测系统资源占用情况（CPU、内存、响应时间）。

## 测试目标

- **技能稳定性**：验证 skill 在长时间运行下是否正常
- **资源占用**：监测 CPU 和内存使用情况
- **响应时间**：测试各种场景下的响应延迟
- **崩溃临界点**：探测系统在何种负载下会出现问题

## 测试覆盖场景

| 场景 | 描述 | 预期行为 |
|-----|------|---------|
| web_search | 搜索场景（无明确URL） | 选择 web_search 工具 |
| web_fetch | 获取静态页面（已知URL） | 选择 web_fetch 工具 |
| opencli | CLI工具作为fallback | 选择 opencli 工具 |
| browser | 浏览器作为最后兜底 | 选择 browser 工具 |

## 文件说明

| 文件 | 说明 |
|-----|------|
| `web_tools_guide_stability_test.py` | 主测试脚本 |
| `test_config.json` | 测试配置参数 |
| `README.md` | 本文档 |

## 使用方法

### 1. 安装依赖

```bash
pip install psutil
```

### 2. 运行测试

```bash
# 基础测试（60秒）
python web_tools_guide_stability_test.py

# 指定输出文件
python web_tools_guide_stability_test.py result.json

# 修改测试时长（编辑 test_config.json）
{
  "stress_parameters": {
    "duration_sec": 300,  // 测试5分钟
    "max_iterations": 1000
  }
}
```

### 3. 查看结果

测试完成后会生成 JSON 格式的报告，包含：
- 总调用次数和成功率
- CPU/内存使用峰值
- 各场景响应时间统计
- 异常事件记录

## 测试指标

### 资源阈值

- **内存警告**: 85%
- **内存危险**: 95%（触发告警）
- **CPU警告**: 80%
- **最大响应时间**: 2000ms
- **最低成功率**: 95%

### 预期结果

在标准测试配置下（2核2GB）：
- CPU 峰值 < 50%
- 内存峰值 < 60%
- 平均响应时间 < 500ms
- 成功率 = 100%

## 集成到CI/CD

```yaml
name: Skill Stability Test
on:
  schedule:
    - cron: '0 3 * * *'  # 每天凌晨3点
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install psutil
      - name: Run stability test
        run: |
          cd test_case_base/business_scenarios/web_tools_guide_stability
          python web_tools_guide_stability_test.py result.json
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: skill-stability-report
          path: result.json
```

## 版本

- **Version**: 1.0.0
- **Author**: OpenClaw Eval Group 2
- **Date**: 2026-06-11
