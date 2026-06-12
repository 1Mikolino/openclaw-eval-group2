# Ontology Skill 稳定性测试

## 概述

本测试用例用于检验 **ontology** skill 的稳定性，监测运行 skill 时的 CPU、内存占用情况以及响应时间。

## 测试场景

测试覆盖以下 5 种 ontology skill 核心场景：

| 场景 | 描述 | 权重 |
|------|------|------|
| entity_extraction | 实体提取 - 从文本中识别和提取实体 | 25% |
| relationship_mapping | 关系映射 - 分析实体之间的关系 | 25% |
| knowledge_query | 知识库查询 - 查询知识图谱 | 25% |
| ontology_validation | 本体验证 - 验证本体一致性 | 15% |
| inference_reasoning | 推理 - 基于本体进行逻辑推理 | 10% |

## 监测指标

### 资源使用
- **CPU 使用率**: 实时监测百分比
- **内存使用率**: 实时监测百分比
- **内存使用量**: MB 单位

### 性能指标
- **响应时间**: 每次调用的耗时（毫秒）
- **成功率**: 成功调用 / 总调用次数
- **吞吐量**: 每秒处理请求数

## 使用方法

### 直接运行

```bash
python ontology_stability_test.py
```

### 指定输出文件

```bash
python ontology_stability_test.py ontology_test_report.json
```

### 修改测试配置

编辑 `test_config.json` 文件：

```json
{
  "duration_sec": 60,        // 测试时长（秒）
  "max_iterations": 1000,    // 最大迭代次数
  "memory_threshold": 90,    // 内存告警阈值(%)
  "cpu_threshold": 80,       // CPU告警阈值(%)
  "monitor_interval": 1      // 监控采样间隔(秒)
}
```

## 测试报告

测试完成后会生成 JSON 格式的详细报告，包含：

- 执行统计（总调用次数、成功率、平均响应时间）
- 资源使用峰值（CPU、内存最高值）
- 按类型统计（各类场景的成功率和响应时间）
- 事件记录（告警和异常）
- 时间线采样（资源使用趋势）

## 预期结果

- 成功率 ≥ 95%
- 平均响应时间 ≤ 1000ms
- 内存增长 ≤ 100MB

## 依赖

```bash
pip install psutil
```

## 作者

OpenClaw Eval Group 2

## 版本

v1.0.0
