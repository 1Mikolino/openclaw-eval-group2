 
$(tail -n +2 $RESULTS_DIR/combined_load_results.csv 2>/dev/null | awk -F',' 'BEGIN{OFS="|"} {print "| "$2" | "$3" | "$4" | "$5" | "$7" | "$9" ms | "$14" |"}')

---

## 4. 性能拐点识别

### 4.1 关键拐点

| 维度 | 拐点位置 | 现象描述 | 建议阈值 |
|------|----------|----------|----------|
| 用户并发 | 待填写 | 待观察 | 待确定 |
| 会话容量 | 待填写 | 待观察 | 待确定 |
| 插件并发 | 待填写 | 待观察 | 待确定 |
| 消息吞吐 | 待填写 | 待观察 | 待确定 |

### 4.2 饱和点分析

| 指标 | 饱和值 | 饱和前表现 | 饱和后表现 |
|------|--------|------------|------------|
| TPS | 待填写 | 线性增长 | 增长放缓/ plateau |
| 延迟 | 待填写 | 稳定低位 | 指数增长 |
| 成功率 | 待填写 | 保持 99%+ | 开始下降 |

---

## 5. 可解释性评估

### 5.1 曲线线性度 (R² 评分)

| 曲线类型 | R² 值 | 可解释性 |
|----------|-------|----------|
| 延迟-负载曲线 | 待计算 | 待评估 |
| 吞吐-负载曲线 | 待计算 | 待评估 |
| 资源-负载曲线 | 待计算 | 待评估 |

### 5.2 异常行为检测

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 性能回退 | $([ -f "$RESULTS_DIR/user_concurrency_results.csv" ] && grep -q "LOW_SUCCESS_RATE\|HIGH_LATENCY" $RESULTS_DIR/combined_load_results.csv 2>/dev/null && echo "⚠️ 发现" || echo "✅ 未检出") | 随负载增加性能突然下降 |
| 资源泄漏 | 待评估 | 长时间运行后资源未释放 |
| 死锁/阻塞 | 待评估 | 高并发下的阻塞现象 |

---

## 6. 容量规划建议

基于性能曲线分析，建议的生产环境配置上限：

| 维度 | 建议上限 | 安全边际 | 备注 |
|------|----------|----------|------|
| 并发用户 | 待填写 | 80% 拐点值 | 留 20% 缓冲 |
| 活跃会话 | 待填写 | 80% 拐点值 | 考虑内存限制 |
| 插件并发 | 待填写 | 80% 拐点值 | 避免 CPU 饱和 |
| 消息吞吐 | 待填写 | 70% 饱和值 | 应对突发流量 |

---

## 7. 结论与建议

### 7.1 主要发现

1. **性能曲线可解释性**: 待评估
2. **系统扩展能力**: 待评估
3. **潜在瓶颈**: 待识别

### 7.2 优化建议

- 待根据实际测试结果填写

### 7.3 后续测试建议

- 长时间稳定性测试
- 故障恢复测试
- 升级前后对比测试

---

**报告生成时间**: $(date)  
**测试数据目录**: \`$TEST_DIR\`
EOF

echo "测试报告模板已生成: $REPORT_FILE"
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
