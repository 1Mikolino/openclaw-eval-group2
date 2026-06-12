#!/usr/bin/env python3
"""
Top 10 Skills 高并发压力测试 - 崩溃临界点测试
测试场景：模拟多用户高并发高频调用 Top 10 插件，监测 OpenClaw 何时崩溃
监测指标：CPU、内存、响应时间、并发连接数、崩溃临界点

Author: OpenClaw Eval Group 2
Version: 1.0.0
"""

import json
import psutil
import time
import sys
import os
import threading
import queue
from datetime import datetime
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal

# Top 10 常用 Skills（按使用频率和复杂度）
TOP_10_SKILLS = [
    {"name": "web-tools-guide", "weight": 25, "complexity": "high"},   # Web搜索/抓取
    {"name": "browser", "weight": 20, "complexity": "high"},          # 浏览器自动化
    {"name": "github", "weight": 15, "complexity": "medium"},         # GitHub API
    {"name": "file-ops", "weight": 10, "complexity": "low"},          # 文件操作
    {"name": "memory", "weight": 8, "complexity": "medium"},          # 内存操作
    {"name": "sessions", "weight": 7, "complexity": "medium"},        # 会话管理
    {"name": "message", "weight": 5, "complexity": "low"},            # 消息发送
    {"name": "github-analysis", "weight": 4, "complexity": "high"},   # GitHub分析
    {"name": "search", "weight": 3, "complexity": "medium"},          # 搜索工具
    {"name": "weather", "weight": 3, "complexity": "low"},            # 天气查询
]

class CrashTestMonitor:
    """崩溃测试监控器"""
    
    def __init__(self, test_config: Dict[str, Any]):
        self.config = test_config
        self.metrics = []
        self.events = []
        self.running = False
        self.crash_detected = False
        self.crash_reason = None
        self.start_time = None
        self.peak_resources = {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_mb": 0,
            "concurrent_threads": 0
        }
        self.lock = threading.Lock()
        self.active_threads = 0
        
    def collect_metrics(self) -> Dict[str, Any]:
        """收集系统资源指标"""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # 获取进程信息
            process = psutil.Process()
            process_memory = process.memory_info()
            
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / 1024 / 1024,
                "memory_available_mb": memory.available / 1024 / 1024,
                "process_memory_mb": process_memory.rss / 1024 / 1024,
                "active_threads": self.active_threads,
                "system_load": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
            
            with self.lock:
                # 更新峰值
                if cpu > self.peak_resources["cpu_percent"]:
                    self.peak_resources["cpu_percent"] = cpu
                if memory.percent > self.peak_resources["memory_percent"]:
                    self.peak_resources["memory_percent"] = memory.percent
                if metrics["memory_used_mb"] > self.peak_resources["memory_used_mb"]:
                    self.peak_resources["memory_used_mb"] = metrics["memory_used_mb"]
                if self.active_threads > self.peak_resources["concurrent_threads"]:
                    self.peak_resources["concurrent_threads"] = self.active_threads
                    
            return metrics
        except Exception as e:
            self._record_event("metrics_error", {"error": str(e)})
            return {}
    
    def _record_event(self, event_type: str, data: Dict[str, Any]):
        """记录事件"""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data
        }
        with self.lock:
            self.events.append(event)
        print(f"\n⚠️  [{event_type}] {json.dumps(data, ensure_ascii=False)}")
    
    def check_crash_conditions(self, metrics: Dict[str, Any]) -> bool:
        """检查是否达到崩溃条件"""
        if not metrics:
            return False
            
        # 检查内存临界
        memory_threshold = self.config.get("crash_memory_threshold", 95)
        if metrics.get("memory_percent", 0) >= memory_threshold:
            self.crash_detected = True
            self.crash_reason = f"内存达到临界值: {metrics['memory_percent']:.1f}%"
            return True
        
        # 检查CPU临界
        cpu_threshold = self.config.get("crash_cpu_threshold", 98)
        if metrics.get("cpu_percent", 0) >= cpu_threshold:
            self.crash_detected = True
            self.crash_reason = f"CPU达到临界值: {metrics['cpu_percent']:.1f}%"
            return True
        
        # 检查内存不足
        available_mb = metrics.get("memory_available_mb", 1000)
        min_memory_mb = self.config.get("min_memory_mb", 100)
        if available_mb < min_memory_mb:
            self.crash_detected = True
            self.crash_reason = f"可用内存过低: {available_mb:.0f}MB"
            return True
            
        return False


class Top10SkillCrashTest:
    """Top 10 Skills 崩溃测试"""
    
    def __init__(self, test_config: Dict[str, Any]):
        self.config = test_config
        self.monitor = CrashTestMonitor(test_config)
        self.results_queue = queue.Queue()
        self.total_invocations = 0
        self.successful_invocations = 0
        self.failed_invocations = 0
        self.skill_stats = {skill["name"]: {"total": 0, "success": 0, "failed": 0} for skill in TOP_10_SKILLS}
        
    def simulate_skill_call(self, skill_info: Dict[str, Any], worker_id: int) -> Dict[str, Any]:
        """模拟单个 skill 调用"""
        start_time = time.time()
        skill_name = skill_info["name"]
        complexity = skill_info["complexity"]
        
        with self.monitor.lock:
            self.monitor.active_threads += 1
        
        try:
            # 模拟 skill 调用耗时（根据复杂度）
            if complexity == "high":
                base_time = 0.5
            elif complexity == "medium":
                base_time = 0.3
            else:
                base_time = 0.1
            
            # 添加随机波动
            duration = base_time + (worker_id % 10) * 0.02
            time.sleep(duration)
            
            # 模拟 skill 内部操作
            self._simulate_skill_work(skill_name, complexity)
            
            result = {
                "skill": skill_name,
                "worker_id": worker_id,
                "success": True,
                "duration_sec": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            result = {
                "skill": skill_name,
                "worker_id": worker_id,
                "success": False,
                "duration_sec": time.time() - start_time,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            with self.monitor.lock:
                self.monitor.active_threads -= 1
        
        return result
    
    def _simulate_skill_work(self, skill_name: str, complexity: str):
        """模拟 skill 内部工作负载"""
        # CPU 密集型模拟
        if complexity == "high":
            # 模拟复杂计算
            _ = [x**2 for x in range(10000)]
        elif complexity == "medium":
            _ = [x**2 for x in range(5000)]
        else:
            _ = [x**2 for x in range(1000)]
        
        # 内存分配模拟
        if complexity == "high":
            temp_data = "x" * (1024 * 1024)  # 1MB
        elif complexity == "medium":
            temp_data = "x" * (512 * 1024)   # 512KB
        else:
            temp_data = "x" * (100 * 1024)   # 100KB
        
        del temp_data
    
    def spawn_load(self, duration_sec: int, concurrent_workers: int):
        """生成负载"""
        start_time = time.time()
        iteration = 0
        
        print(f"\n🚀 启动高并发负载: {concurrent_workers} 并发线程")
        print(f"   目标持续时间: {duration_sec} 秒")
        print(f"   崩溃内存阈值: {self.config.get('crash_memory_threshold', 95)}%")
        print(f"   崩溃CPU阈值: {self.config.get('crash_cpu_threshold', 98)}%")
        print("-" * 60)
        
        with ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = []
            
            while self.monitor.running:
                # 检查是否超时或崩溃
                elapsed = time.time() - start_time
                if elapsed >= duration_sec or self.monitor.crash_detected:
                    break
                
                # 提交新任务（保持并发数）
                while len(futures) < concurrent_workers and self.monitor.running:
                    skill = TOP_10_SKILLS[iteration % len(TOP_10_SKILLS)]
                    future = executor.submit(
                        self.simulate_skill_call, 
                        skill, 
                        iteration
                    )
                    futures.append(future)
                    iteration += 1
                
                # 收集完成的任务
                done_futures = [f for f in futures if f.done()]
                for future in done_futures:
                    try:
                        result = future.result(timeout=1)
                        self.results_queue.put(result)
                        self._update_stats(result)
                    except Exception as e:
                        self.failed_invocations += 1
                        self.monitor._record_event("task_error", {"error": str(e)})
                    futures.remove(future)
                
                # 实时监测
                if iteration % 50 == 0:
                    metrics = self.monitor.collect_metrics()
                    if metrics:
                        self.monitor.metrics.append(metrics)
                        self._print_progress(metrics, elapsed)
                        
                        if self.monitor.check_crash_conditions(metrics):
                            print(f"\n💥 崩溃条件触发! 原因: {self.monitor.crash_reason}")
                            self.monitor.running = False
                            break
                
                time.sleep(0.01)  # 避免CPU占满
        
        return iteration
    
    def _update_stats(self, result: Dict[str, Any]):
        """更新统计"""
        skill_name = result["skill"]
        with self.monitor.lock:
            self.total_invocations += 1
            if result["success"]:
                self.successful_invocations += 1
                self.skill_stats[skill_name]["success"] += 1
            else:
                self.failed_invocations += 1
                self.skill_stats[skill_name]["failed"] += 1
            self.skill_stats[skill_name]["total"] += 1
    
    def _print_progress(self, metrics: Dict[str, Any], elapsed: float):
        """打印进度"""
        print(f"\r[运行 {elapsed:5.1f}s] "
              f"调用: {self.total_invocations:5d} | "
              f"并发: {metrics['active_threads']:3d} | "
              f"CPU: {metrics['cpu_percent']:5.1f}% | "
              f"内存: {metrics['memory_percent']:5.1f}% | "
              f"已用: {metrics['memory_used_mb']:7.0f}MB", 
              end="", flush=True)
    
    def run_crash_test(self) -> Dict[str, Any]:
        """运行崩溃测试"""
        print("💥 Top 10 Skills 高并发崩溃测试")
        print("=" * 60)
        print(f"开始时间: {datetime.now().isoformat()}")
        print(f"测试配置: {json.dumps(self.config, indent=2, ensure_ascii=False)}")
        print(f"\n测试 Skills 列表:")
        for i, skill in enumerate(TOP_10_SKILLS, 1):
            print(f"  {i}. {skill['name']:20s} (权重: {skill['weight']}%, 复杂度: {skill['complexity']})")
        print("=" * 60)
        
        # 初始状态
        initial_metrics = self.monitor.collect_metrics()
        print(f"\n[初始状态] CPU: {initial_metrics.get('cpu_percent', 0):.1f}% | "
              f"内存: {initial_metrics.get('memory_percent', 0):.1f}%")
        
        self.monitor.running = True
        self.monitor.start_time = time.time()
        
        # 阶段1: 逐步增加并发
        stages = self.config.get("load_stages", [
            {"concurrent": 10, "duration": 30},
            {"concurrent": 50, "duration": 60},
            {"concurrent": 100, "duration": 120},
            {"concurrent": 200, "duration": 300}
        ])
        
        stage_results = []
        
        for stage_idx, stage in enumerate(stages):
            if not self.monitor.running or self.monitor.crash_detected:
                break
                
            print(f"\n📊 阶段 {stage_idx + 1}/{len(stages)}: "
                  f"{stage['concurrent']} 并发, {stage['duration']} 秒")
            
            invocations = self.spawn_load(
                duration_sec=stage['duration'],
                concurrent_workers=stage['concurrent']
            )
            
            stage_results.append({
                "stage": stage_idx + 1,
                "concurrent": stage['concurrent'],
                "invocations": invocations,
                "peak_cpu": self.monitor.peak_resources['cpu_percent'],
                "peak_memory": self.monitor.peak_resources['memory_percent']
            })
        
        total_duration = time.time() - self.monitor.start_time
        
        # 最终状态
        final_metrics = self.monitor.collect_metrics()
        print(f"\n\n[最终状态] CPU: {final_metrics.get('cpu_percent', 0):.1f}% | "
              f"内存: {final_metrics.get('memory_percent', 0):.1f}%")
        
        # 生成报告
        report = self._generate_report(total_duration, initial_metrics, final_metrics, stage_results)
        
        return report
    
    def _generate_report(self, duration: float, initial: Dict, final: Dict, 
                        stage_results: List[Dict]) -> Dict[str, Any]:
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 崩溃测试报告")
        print("=" * 60)
        
        # 计算统计数据
        success_rate = (self.successful_invocations / self.total_invocations * 100) 
                       if self.total_invocations > 0 else 0
        
        # 计算平均响应时间
        response_times = []
        while not self.results_queue.empty():
            try:
                result = self.results_queue.get(timeout=0.1)
                response_times.append(result.get("duration_sec", 0))
            except:
                break
        
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        max_response = max(response_times) if response_times else 0
        
        report = {
            "test_name": "top10_skill_crash_test",
            "timestamp": datetime.now().isoformat(),
            "duration_sec": duration,
            "config": self.config,
            "crash_detected": self.monitor.crash_detected,
            "crash_reason": self.monitor.crash_reason,
            "summary": {
                "total_invocations": self.total_invocations,
                "successful": self.successful_invocations,
                "failed": self.failed_invocations,
                "success_rate": success_rate,
                "avg_response_time_ms": avg_response * 1000,
                "max_response_time_ms": max_response * 1000,
                "stages_completed": len(stage_results),
                "peak_concurrent_threads": self.monitor.peak_resources["concurrent_threads"]
            },
            "resource_usage": {
                "initial": initial,
                "final": final,
                "peak_cpu_percent": self.monitor.peak_resources["cpu_percent"],
                "peak_memory_percent": self.monitor.peak_resources["memory_percent"],
                "peak_memory_used_mb": self.monitor.peak_resources["memory_used_mb"],
                "memory_growth_mb": final.get("memory_used_mb", 0) - initial.get("memory_used_mb", 0)
            },
            "stage_results": stage_results,
            "skill_breakdown": self.skill_stats,
            "events": self.monitor.events,
            "all_metrics": self.monitor.metrics
        }
        
        # 打印摘要
        print(f"\n执行统计:")
        print(f"   总调用次数: {self.total_invocations}")
        print(f"   成功: {self.successful_invocations} | 失败: {self.failed_invocations}")
        print(f"   成功率: {success_rate:.1f}%")
        print(f"   平均响应: {avg_response*1000:.1f}ms")
        
        print(f"\n资源使用峰值:")
        print(f"   CPU: {report['resource_usage']['peak_cpu_percent']:.1f}%")
        print(f"   内存: {report['resource_usage']['peak_memory_percent']:.1f}%")
        print(f"   内存增长: {report['resource_usage']['memory_growth_mb']:+.1f}MB")
        print(f"   最大并发: {report['summary']['peak_concurrent_threads']}")
        
        print(f"\n阶段结果:")
        for stage in stage_results:
            print(f"   阶段{stage['stage']}: {stage['concurrent']:3d}并发 | "
                  f"调用{stage['invocations']:5d}次 | "
                  f"峰值CPU {stage['peak_cpu']:5.1f}%")
        
        if self.monitor.crash_detected:
            print(f"\n💥 崩溃检测结果:")
            print(f"   原因: {self.monitor.crash_reason}")
            print(f"   测试在阶段 {len(stage_results)} 终止")
        else:
            print(f"\n✅ 测试完成，未达到崩溃条件")
        
        if self.monitor.events:
            print(f"\n⚠️ 异常事件: {len(self.monitor.events)} 个")
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """保存报告到文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"top10_crash_test_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 报告已保存: {filename}")
        return filename


def signal_handler(signum, frame):
    """信号处理"""
    print("\n\n⚠️ 收到中断信号，正在停止测试...")
    sys.exit(130)


def main():
    """主函数"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 测试配置
    config = {
        "duration_sec": 600,              # 最大测试时长（秒）
        "crash_memory_threshold": 95,     # 崩溃内存阈值(%)
        "crash_cpu_threshold": 98,        # 崩溃CPU阈值(%)
        "min_memory_mb": 100,             # 最小可用内存(MB)
        "monitor_interval": 0.5,          # 监控采样间隔(秒)
        "load_stages": [                  # 负载阶段
            {"concurrent": 10, "duration": 30},    # 阶段1: 10并发
            {"concurrent": 50, "duration": 60},    # 阶段2: 50并发
            {"concurrent": 100, "duration": 120},  # 阶段3: 100并发
            {"concurrent": 200, "duration": 300},  # 阶段4: 200并发
            {"concurrent": 500, "duration": 600}   # 阶段5: 500并发（极限测试）
        ]
    }
    
    # 从命令行参数覆盖配置
    if len(sys.argv) > 1:
        try:
            override_config = json.loads(sys.argv[1])
            config.update(override_config)
        except:
            pass
    
    # 创建测试实例
    tester = Top10SkillCrashTest(config)
    
    try:
        # 运行测试
        report = tester.run_crash_test()
        
        # 保存报告
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        filename = tester.save_report(report, output_file)
        
        # 返回码
        if tester.monitor.crash_detected:
            print("\n💥 测试检测到系统崩溃临界点")
            return 2  # 特殊返回码表示崩溃
        elif report["events"]:
            return 1
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
        return 130
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
