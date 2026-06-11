#!/usr/bin/env python3
"""
OpenClaw 多浏览器并发压力测试
模拟真实业务场景中的多浏览器并发，监测系统资源占用和崩溃临界点

Author: OpenClaw Eval Group 2
Date: 2026-06-11
Version: 1.0.0
"""

import asyncio
import json
import psutil
import time
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, List, Any
import subprocess
import signal
import os

# 测试配置
CONFIG = {
    "test_name": "multi_browser_concurrent_stress_test",
    "version": "1.0.0",
    "max_concurrent_browsers": 20,  # 最大并发浏览器数
    "browser_start_delay": 2,       # 每个浏览器启动间隔(秒)
    "test_duration_per_browser": 60, # 每个浏览器测试时长(秒)
    "monitor_interval": 1,          # 监控采样间隔(秒)
    "memory_threshold": 85,         # 内存告警阈值(%)
    "cpu_threshold": 80,            # CPU告警阈值(%)
    "crash_detection": True,        # 是否启用崩溃检测
}

# 测试状态
class TestState:
    def __init__(self):
        self.running = True
        self.browsers = []
        self.metrics = []
        self.crash_info = None
        self.peak_resources = {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_mb": 0,
            "browser_count": 0
        }

state = TestState()

def get_system_metrics() -> Dict[str, Any]:
    """获取系统资源指标"""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_mb": memory.used / 1024 / 1024,
        "memory_available_mb": memory.available / 1024 / 1024,
        "disk_percent": disk.percent,
        "load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0],
        "browser_count": len(state.browsers)
    }

def check_resource_thresholds(metrics: Dict[str, Any]) -> List[str]:
    """检查资源是否超过阈值"""
    alerts = []
    if metrics["memory_percent"] > CONFIG["memory_threshold"]:
        alerts.append(f"内存使用超过阈值: {metrics['memory_percent']:.1f}% > {CONFIG['memory_threshold']}%")
    if metrics["cpu_percent"] > CONFIG["cpu_threshold"]:
        alerts.append(f"CPU使用超过阈值: {metrics['cpu_percent']:.1f}% > {CONFIG['cpu_threshold']}%")
    return alerts

def simulate_browser_session(browser_id: int) -> Dict[str, Any]:
    """模拟单个浏览器会话"""
    start_time = time.time()
    browser_info = {
        "id": browser_id,
        "pid": None,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration": 0,
        "pages_opened": 0,
        "memory_usage_mb": 0,
        "status": "running"
    }
    
    state.browsers.append(browser_info)
    
    try:
        # 模拟浏览器启动
        time.sleep(0.5)
        browser_info["pid"] = 10000 + browser_id  # 模拟PID
        
        # 模拟打开多个页面
        pages = [
            "https://github.com",
            "https://docs.openclaw.ai",
            "https://clawhub.ai"
        ]
        
        for i, page in enumerate(pages):
            if not state.running:
                break
            # 模拟页面加载
            time.sleep(2)
            browser_info["pages_opened"] += 1
            
            # 模拟页面操作
            time.sleep(1)
        
        # 保持浏览器运行一段时间
        elapsed = 0
        while elapsed < CONFIG["test_duration_per_browser"] and state.running:
            time.sleep(1)
            elapsed = time.time() - start_time
            
            # 模拟内存增长（真实浏览器会占用更多内存）
            browser_info["memory_usage_mb"] = 100 + (elapsed * 2)  # 逐步增长
            
        browser_info["status"] = "completed"
        
    except Exception as e:
        browser_info["status"] = "crashed"
        browser_info["error"] = str(e)
        
    finally:
        browser_info["end_time"] = datetime.now().isoformat()
        browser_info["duration"] = time.time() - start_time
        
    return browser_info

def monitor_resources():
    """后台监控线程"""
    print("[监控] 启动资源监控...")
    
    while state.running:
        try:
            metrics = get_system_metrics()
            state.metrics.append(metrics)
            
            # 更新峰值
            if metrics["cpu_percent"] > state.peak_resources["cpu_percent"]:
                state.peak_resources["cpu_percent"] = metrics["cpu_percent"]
            if metrics["memory_percent"] > state.peak_resources["memory_percent"]:
                state.peak_resources["memory_percent"] = metrics["memory_percent"]
            if metrics["memory_used_mb"] > state.peak_resources["memory_used_mb"]:
                state.peak_resources["memory_used_mb"] = metrics["memory_used_mb"]
            if metrics["browser_count"] > state.peak_resources["browser_count"]:
                state.peak_resources["browser_count"] = metrics["browser_count"]
            
            # 检查阈值
            alerts = check_resource_thresholds(metrics)
            for alert in alerts:
                print(f"[告警] {alert}")
            
            # 显示实时状态
            print(f"\r[实时监控] 浏览器: {metrics['browser_count']:2d} | "
                  f"CPU: {metrics['cpu_percent']:5.1f}% | "
                  f"内存: {metrics['memory_percent']:5.1f}% | "
                  f"已用: {metrics['memory_used_mb']:6.0f}MB", end="", flush=True)
            
            # 检测崩溃临界点
            if CONFIG["crash_detection"] and metrics["memory_percent"] > 95:
                print(f"\n[崩溃检测] 内存超过95%，停止测试！")
                state.crash_info = {
                    "timestamp": datetime.now().isoformat(),
                    "browser_count": metrics["browser_count"],
                    "memory_percent": metrics["memory_percent"],
                    "reason": "内存耗尽"
                }
                state.running = False
                break
                
            time.sleep(CONFIG["monitor_interval"])
            
        except Exception as e:
            print(f"\n[监控错误] {e}")
            break
    
    print("\n[监控] 资源监控停止")

def run_concurrent_test(target_browsers: int = None):
    """运行并发测试"""
    if target_browsers is None:
        target_browsers = CONFIG["max_concurrent_browsers"]
    
    print(f"\n{'='*60}")
    print(f"🔥 多浏览器并发压力测试")
    print(f"{'='*60}")
    print(f"目标并发数: {target_browsers}")
    print(f"每个浏览器运行时长: {CONFIG['test_duration_per_browser']}秒")
    print(f"启动间隔: {CONFIG['browser_start_delay']}秒")
    print(f"{'='*60}\n")
    
    # 初始状态
    initial_metrics = get_system_metrics()
    print(f"[初始状态] CPU: {initial_metrics['cpu_percent']:.1f}% | "
          f"内存: {initial_metrics['memory_percent']:.1f}%")
    
    # 启动监控线程
    import threading
    monitor_thread = threading.Thread(target=monitor_resources)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 逐步启动浏览器
    browser_futures = []
    active_browsers = 0
    
    with ThreadPoolExecutor(max_workers=target_browsers) as executor:
        for i in range(target_browsers):
            if not state.running:
                print(f"\n[停止] 检测到停止信号，已启动 {i} 个浏览器")
                break
            
            # 提交浏览器任务
            future = executor.submit(simulate_browser_session, i + 1)
            browser_futures.append(future)
            active_browsers += 1
            
            print(f"\n[启动] 浏览器 #{i+1} (总计: {active_browsers})")
            
            # 间隔启动
            if i < target_browsers - 1:
                time.sleep(CONFIG["browser_start_delay"])
    
    # 等待所有浏览器完成
    print("\n[等待] 等待所有浏览器会话结束...")
    completed_browsers = []
    for future in browser_futures:
        try:
            result = future.result(timeout=CONFIG["test_duration_per_browser"] + 30)
            completed_browsers.append(result)
        except Exception as e:
            print(f"[错误] 浏览器任务异常: {e}")
    
    # 停止监控
    state.running = False
    monitor_thread.join(timeout=5)
    
    return completed_browsers

def generate_report(browsers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成测试报告"""
    print(f"\n\n{'='*60}")
    print(f"📊 测试报告")
    print(f"{'='*60}")
    
    # 统计
    successful = [b for b in browsers if b["status"] == "completed"]
    crashed = [b for b in browsers if b["status"] == "crashed"]
    
    report = {
        "test_name": CONFIG["test_name"],
        "version": CONFIG["version"],
        "timestamp": datetime.now().isoformat(),
        "config": CONFIG,
        "summary": {
            "total_browsers": len(browsers),
            "successful": len(successful),
            "crashed": len(crashed),
            "success_rate": len(successful) / len(browsers) if browsers else 0,
        },
        "resource_usage": {
            "peak_cpu_percent": state.peak_resources["cpu_percent"],
            "peak_memory_percent": state.peak_resources["memory_percent"],
            "peak_memory_used_mb": state.peak_resources["memory_used_mb"],
            "peak_browser_count": state.peak_resources["browser_count"],
        },
        "crash_analysis": state.crash_info,
        "browsers": browsers,
        "metrics_timeline": state.metrics
    }
    
    # 打印摘要
    print(f"\n测试摘要:")
    print(f"   总浏览器数: {report['summary']['total_browsers']}")
    print(f"   成功: {report['summary']['successful']}")
    print(f"   崩溃: {report['summary']['crashed']}")
    print(f"   成功率: {report['summary']['success_rate']*100:.1f}%")
    
    print(f"\n资源使用峰值:")
    print(f"   CPU: {report['resource_usage']['peak_cpu_percent']:.1f}%")
    print(f"   内存: {report['resource_usage']['peak_memory_percent']:.1f}%")
    print(f"   内存使用: {report['resource_usage']['peak_memory_used_mb']:.0f}MB")
    print(f"   浏览器数: {report['resource_usage']['peak_browser_count']}")
    
    if state.crash_info:
        print(f"\n⚠️ 崩溃检测:")
        print(f"   时间: {state.crash_info['timestamp']}")
        print(f"   浏览器数: {state.crash_info['browser_count']}")
        print(f"   原因: {state.crash_info['reason']}")
    else:
        print(f"\n✅ 未检测到崩溃")
    
    return report

def save_report(report: Dict[str, Any]):
    """保存报告到文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"browser_concurrent_test_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 报告已保存: {filename}")
    return filename

def main():
    """主函数"""
    print("🦞 OpenClaw 多浏览器并发压力测试")
    print("=" * 60)
    
    # 解析命令行参数
    target_browsers = CONFIG["max_concurrent_browsers"]
    if len(sys.argv) > 1:
        try:
            target_browsers = int(sys.argv[1])
        except:
            pass
    
    # 运行测试
    browsers = run_concurrent_test(target_browsers)
    
    # 生成报告
    report = generate_report(browsers)
    
    # 保存报告
    filename = save_report(report)
    
    print(f"\n{'='*60}")
    print(f"测试完成")
    print(f"{'='*60}")
    
    # 返回退出码（用于CI/CD）
    if state.crash_info:
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
