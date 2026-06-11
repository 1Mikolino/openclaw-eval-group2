#!/usr/bin/env python3
"""
Web-Tools-Guide Skill 稳定性测试
测试场景：模拟真实业务中频繁调用 web-tools-guide skill 的情况
监测指标：CPU、内存、响应时间、成功率

Author: OpenClaw Eval Group 2
Version: 1.0.0
"""

import json
import psutil
import time
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List
import threading
import os

class SkillStabilityTest:
    """Skill 稳定性测试框架"""
    
    def __init__(self, skill_name: str, test_config: Dict[str, Any]):
        self.skill_name = skill_name
        self.config = test_config
        self.metrics = []
        self.events = []
        self.running = False
        self.peak_resources = {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_mb": 0
        }
        
    def collect_metrics(self) -> Dict[str, Any]:
        """收集系统资源指标"""
        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_used_mb": memory.used / 1024 / 1024,
            "memory_available_mb": memory.available / 1024 / 1024
        }
        
        # 更新峰值
        if cpu > self.peak_resources["cpu_percent"]:
            self.peak_resources["cpu_percent"] = cpu
        if memory.percent > self.peak_resources["memory_percent"]:
            self.peak_resources["memory_percent"] = memory.percent
        if metrics["memory_used_mb"] > self.peak_resources["memory_used_mb"]:
            self.peak_resources["memory_used_mb"] = metrics["memory_used_mb"]
            
        return metrics
    
    def simulate_skill_invocation(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """模拟 skill 调用"""
        start_time = time.time()
        start_memory = psutil.virtual_memory().used / 1024 / 1024
        
        test_type = test_case.get("type", "web_search")
        
        try:
            # 模拟读取 SKILL.md（这是 skill 调用的第一步）
            skill_path = f"~/.openclaw/workspace/skills/{self.skill_name}"
            skill_md_path = os.path.expanduser(f"{skill_path}/SKILL.md")
            
            if os.path.exists(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 解析关键决策逻辑
                    decision_tree = self._parse_decision_tree(content)
            else:
                content = ""
                decision_tree = {}
            
            # 模拟根据测试类型执行不同分支
            if test_type == "web_search":
                self._simulate_web_search(test_case)
            elif test_type == "web_fetch":
                self._simulate_web_fetch(test_case)
            elif test_type == "opencli":
                self._simulate_opencli(test_case)
            elif test_type == "browser":
                self._simulate_browser(test_case)
                
            # 模拟工具选择决策（skill 的核心逻辑）
            time.sleep(0.1)  # 模拟决策耗时
            
            result = {
                "type": test_type,
                "success": True,
                "duration_sec": time.time() - start_time,
                "memory_delta_mb": (psutil.virtual_memory().used / 1024 / 1024) - start_memory,
                "decision": decision_tree.get("recommended_tool", "unknown")
            }
            
        except Exception as e:
            result = {
                "type": test_type,
                "success": False,
                "duration_sec": time.time() - start_time,
                "error": str(e)
            }
        
        return result
    
    def _parse_decision_tree(self, content: str) -> Dict[str, Any]:
        """解析 skill 中的决策树（简化版）"""
        tree = {}
        if "web_search" in content:
            tree["has_web_search"] = True
        if "web_fetch" in content:
            tree["has_web_fetch"] = True
        if "opencli" in content:
            tree["has_opencli"] = True
        if "browser" in content:
            tree["has_browser"] = True
        return tree
    
    def _simulate_web_search(self, test_case: Dict[str, Any]):
        """模拟 web_search 场景"""
        # 模拟搜索关键词
        keywords = test_case.get("keywords", "OpenClaw documentation")
        time.sleep(0.5)  # 模拟搜索耗时
        
    def _simulate_web_fetch(self, test_case: Dict[str, Any]):
        """模拟 web_fetch 场景"""
        url = test_case.get("url", "https://docs.openclaw.ai")
        # 模拟页面获取
        time.sleep(0.3)
        
    def _simulate_opencli(self, test_case: Dict[str, Any]):
        """模拟 opencli 场景"""
        site = test_case.get("site", "github")
        # 模拟 CLI 调用
        time.sleep(0.2)
        
    def _simulate_browser(self, test_case: Dict[str, Any]):
        """模拟 browser 场景"""
        action = test_case.get("action", "snapshot")
        # 模拟浏览器操作
        time.sleep(0.8)  # 浏览器操作更耗时
    
    def run_stress_test(self) -> Dict[str, Any]:
        """运行压力测试"""
        print(f"🦞 {self.skill_name} Skill 稳定性测试")
        print("=" * 60)
        print(f"开始时间: {datetime.now().isoformat()}")
        print(f"测试配置: {json.dumps(self.config, indent=2)}")
        print("=" * 60)
        
        # 初始状态
        initial_metrics = self.collect_metrics()
        print(f"\n[初始状态] CPU: {initial_metrics['cpu_percent']:.1f}% | "
              f"内存: {initial_metrics['memory_percent']:.1f}%")
        
        self.running = True
        start_time = time.time()
        
        # 测试用例定义（覆盖 skill 的各种场景）
        test_cases = [
            {"type": "web_search", "keywords": "OpenClaw documentation"},
            {"type": "web_search", "keywords": "最新AI助手评测"},
            {"type": "web_fetch", "url": "https://docs.openclaw.ai"},
            {"type": "web_fetch", "url": "https://github.com/openclaw/openclaw"},
            {"type": "opencli", "site": "github"},
            {"type": "opencli", "site": "youtube"},
            {"type": "browser", "action": "snapshot"},
            {"type": "browser", "action": "navigate"},
        ]
        
        results = []
        iteration = 0
        
        print("\n📊 开始压力测试...")
        print("-" * 60)
        
        # 持续运行测试
        while self.running and iteration < self.config.get("max_iterations", 100):
            for test_case in test_cases:
                if not self.running:
                    break
                    
                iteration += 1
                
                # 执行测试
                result = self.simulate_skill_invocation(test_case)
                results.append(result)
                
                # 收集指标
                metrics = self.collect_metrics()
                metrics["iteration"] = iteration
                metrics["test_type"] = test_case["type"]
                self.metrics.append(metrics)
                
                # 实时显示
                if iteration % 10 == 0:
                    print(f"\r[迭代 {iteration:4d}] "
                          f"CPU: {metrics['cpu_percent']:5.1f}% | "
                          f"内存: {metrics['memory_percent']:5.1f}% | "
                          f"已用: {metrics['memory_used_mb']:6.0f}MB", 
                          end="", flush=True)
                
                # 检查资源阈值
                if metrics["memory_percent"] > self.config.get("memory_threshold", 90):
                    print(f"\n⚠️ 警告: 内存使用超过90%")
                    self.events.append({
                        "type": "memory_warning",
                        "timestamp": datetime.now().isoformat(),
                        "memory_percent": metrics["memory_percent"]
                    })
                
                # 检查是否达到测试时长
                if time.time() - start_time > self.config.get("duration_sec", 300):
                    self.running = False
                    break
                
                # 小间隔避免CPU占满
                time.sleep(0.1)
        
        total_duration = time.time() - start_time
        
        # 最终状态
        final_metrics = self.collect_metrics()
        print(f"\n\n[最终状态] CPU: {final_metrics['cpu_percent']:.1f}% | "
              f"内存: {final_metrics['memory_percent']:.1f}%")
        
        # 生成报告
        report = self._generate_report(results, total_duration, initial_metrics, final_metrics)
        
        return report
    
    def _generate_report(self, results: List[Dict], duration: float, 
                        initial: Dict, final: Dict) -> Dict[str, Any]:
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 测试报告")
        print("=" * 60)
        
        # 统计
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        # 按类型统计
        by_type = {}
        for r in results:
            t = r.get("type", "unknown")
            if t not in by_type:
                by_type[t] = {"total": 0, "success": 0}
            by_type[t]["total"] += 1
            if r.get("success"):
                by_type[t]["success"] += 1
        
        # 延迟统计
        durations = [r.get("duration_sec", 0) for r in results]
        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        report = {
            "test_name": f"{self.skill_name}_stability_test",
            "timestamp": datetime.now().isoformat(),
            "duration_sec": duration,
            "config": self.config,
            "summary": {
                "total_invocations": len(results),
                "successful": successful,
                "failed": failed,
                "success_rate": successful / len(results) if results else 0,
                "avg_response_time_sec": avg_duration,
                "max_response_time_sec": max_duration
            },
            "resource_usage": {
                "initial": initial,
                "final": final,
                "peak_cpu_percent": self.peak_resources["cpu_percent"],
                "peak_memory_percent": self.peak_resources["memory_percent"],
                "peak_memory_used_mb": self.peak_resources["memory_used_mb"],
                "memory_growth_mb": final["memory_used_mb"] - initial["memory_used_mb"]
            },
            "by_type": by_type,
            "events": self.events,
            "timeline_sample": self.metrics[::10] if len(self.metrics) > 10 else self.metrics  # 采样
        }
        
        # 打印摘要
        print(f"\n执行统计:")
        print(f"   总调用次数: {report['summary']['total_invocations']}")
        print(f"   成功: {successful} | 失败: {failed}")
        print(f"   成功率: {report['summary']['success_rate']*100:.1f}%")
        print(f"   平均响应: {avg_duration*1000:.1f}ms")
        
        print(f"\n资源使用峰值:")
        print(f"   CPU: {report['resource_usage']['peak_cpu_percent']:.1f}%")
        print(f"   内存: {report['resource_usage']['peak_memory_percent']:.1f}%")
        print(f"   内存增长: {report['resource_usage']['memory_growth_mb']:+.1f}MB")
        
        print(f"\n按类型统计:")
        for t, stats in by_type.items():
            rate = stats['success'] / stats['total'] * 100
            print(f"   {t:15s}: {stats['success']}/{stats['total']} ({rate:.0f}%)")
        
        if self.events:
            print(f"\n⚠️ 事件记录: {len(self.events)} 个")
        else:
            print(f"\n✅ 无异常事件")
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """保存报告到文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.skill_name}_test_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 报告已保存: {filename}")
        return filename


def main():
    """主函数"""
    # 测试配置
    config = {
        "duration_sec": 60,           # 测试时长（秒）
        "max_iterations": 1000,       # 最大迭代次数
        "memory_threshold": 90,       # 内存告警阈值(%)
        "cpu_threshold": 80,          # CPU告警阈值(%)
        "monitor_interval": 1         # 监控采样间隔(秒)
    }
    
    # 创建测试实例
    tester = SkillStabilityTest("web-tools-guide", config)
    
    try:
        # 运行测试
        report = tester.run_stress_test()
        
        # 保存报告
        output_file = sys.argv[1] if len(sys.argv) > 1 else None
        tester.save_report(report, output_file)
        
        # 返回码（用于CI/CD）
        if report["events"]:
            return 1  # 有异常事件
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        return 130
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
