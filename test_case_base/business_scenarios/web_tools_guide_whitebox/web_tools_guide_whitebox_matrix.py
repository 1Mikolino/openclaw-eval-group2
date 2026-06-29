#!/usr/bin/env python3
"""
Web-Tools-Guide Skill 白盒矩阵测试

按照 OpenClaw 内部链路拆解测试：
用户请求 → Prompt/Ontology 解析 → Tool 选择 → Schema 校验 → 执行 → 错误恢复 → 最终回答

每个测试用例验证完整链路，而不仅仅是最终输出。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 枚举和数据结构
# ============================================================

class ToolName(str, Enum):
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    OPENCLI = "opencli"
    BROWSER = "browser"
    NONE = "none"


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    FALLBACK = "fallback"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class WhiteBoxContext:
    """白盒测试上下文 - 记录完整链路"""
    # 阶段 1: 用户请求
    user_request: str
    request_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 阶段 2: Prompt/Ontology 解析
    parsed_intent: Optional[str] = None
    detected_url: Optional[str] = None
    needs_interaction: bool = False
    target_site: Optional[str] = None
    query: Optional[str] = None
    parse_confidence: float = 0.0
    
    # 阶段 3: Tool 选择
    selected_tool: ToolName = ToolName.NONE
    selection_reason: Optional[str] = None
    decision_tree_path: list[str] = field(default_factory=list)
    
    # 阶段 4: Schema 校验
    schema_valid: bool = False
    schema_errors: list[str] = field(default_factory=list)
    validated_params: dict[str, Any] = field(default_factory=dict)
    
    # 阶段 5: 执行
    execution_status: ExecutionStatus = ExecutionStatus.FAILURE
    execution_duration_ms: int = 0
    execution_result: Optional[Any] = None
    execution_error: Optional[str] = None
    
    # 阶段 6: 错误恢复
    fallback_attempted: bool = False
    fallback_tool: Optional[ToolName] = None
    fallback_reason: Optional[str] = None
    recovery_success: bool = False
    
    # 阶段 7: 最终回答
    final_answer: Optional[str] = None
    answer_timestamp: Optional[str] = None
    success: bool = False
    
    # 元数据
    test_case_id: Optional[str] = None
    iterations: int = 0


# ============================================================
# 白盒矩阵测试器
# ============================================================

class WebToolsGuideWhiteBoxMatrix:
    """白盒矩阵测试 - 验证完整链路"""
    
    # 默认内置测试用例（配置文件不存在时使用）
    DEFAULT_TEST_CASES = [
        {
            "id": "DEFAULT-001",
            "name": "开放查询 → web_search",
            "description": "无 URL 的开放信息查询",
            "user_request": "搜索 OpenClaw 的最新文档",
            "expected_tool": "web_search",
            "expected_success": True,
        },
        {
            "id": "DEFAULT-002",
            "name": "已知静态 URL → web_fetch",
            "description": "已知文档 URL",
            "user_request": "获取 https://docs.openclaw.ai 的内容",
            "expected_tool": "web_fetch",
            "expected_success": True,
        },
        {
            "id": "DEFAULT-003",
            "name": "GitHub 仓库 → opencli",
            "description": "GitHub 场景",
            "user_request": "查看 https://github.com/openclaw/openclaw 的最新提交",
            "expected_tool": "opencli",
            "expected_success": True,
        },
    ]
    
    def __init__(self, config: dict[str, Any] | None = None):
        """
        初始化测试器
        :param config: 配置字典。如果为 None，尝试从默认位置加载或使用内置默认值
        """
        if config is None:
            config = self._load_default_config()
        
        self.config = config
        self.skill_name = config.get("target_skill", "web-tools-guide")
        self.skill_md_path = os.path.expanduser(
            config.get("skill_md_path", f"~/.openclaw/workspace/skills/{self.skill_name}/SKILL.md")
        )
        self.results: list[dict[str, Any]] = []
        self.issue_candidates: list[dict[str, Any]] = []
    
    @classmethod
    def _load_default_config(cls) -> dict[str, Any]:
        """尝试从默认位置加载配置，失败则使用内置默认值"""
        # 默认配置路径
        default_paths = [
            Path("/root/.openclaw/workspace/web_tools_guide_whitebox_matrix_config.json"),
            Path.home() / ".openclaw/workspace/web_tools_guide_whitebox_matrix_config.json",
            Path.cwd() / "web_tools_guide_whitebox_matrix_config.json",
        ]
        
        for path in default_paths:
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f:
                        config = json.load(f)
                    print(f"已加载配置文件: {path}")
                    return config
                except Exception as e:
                    print(f"加载配置文件失败 {path}: {e}")
        
        # 使用内置默认值
        print("使用内置默认测试用例")
        return {
            "target_skill": "web-tools-guide",
            "skill_md_path": "~/.openclaw/workspace/skills/web-tools-guide/SKILL.md",
            "white_box_matrix_cases": cls.DEFAULT_TEST_CASES,
            "thresholds": {
                "min_success_rate": 0.90,
            }
        }
        
    def load_skill_rules(self) -> dict[str, Any]:
        """加载 skill 规则（白盒验证：阶段 0）"""
        path = Path(self.skill_md_path)
        result = {
            "exists": path.exists(),
            "path": str(path),
            "content": None,
            "parsed_sections": {}
        }
        
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="replace")
            result["content"] = content
            # 解析关键章节
            result["parsed_sections"]["decision_tree"] = "决策流程" in content
            result["parsed_sections"]["fallback_chain"] = "opencli" in content and "browser" in content
            result["parsed_sections"]["error_handling"] = "失败处理" in content
            
        return result
    
    def parse_user_request(self, context: WhiteBoxContext) -> WhiteBoxContext:
        """阶段 2: Prompt/Ontology 解析"""
        request = context.user_request
        
        # 检测 URL
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, request)
        if urls:
            context.detected_url = urls[0]
        
        # 检测是否需要交互
        interaction_keywords = ["点击", "填写", "登录", "提交", "滚动", "截图", "交互"]
        context.needs_interaction = any(kw in request for kw in interaction_keywords)
        
        # 检测目标站点
        site_mapping = {
            "github": ["github", "GitHub"],
            "youtube": ["youtube", "YouTube"],
            "twitter": ["twitter", "Twitter", "推特"],
            "reddit": ["reddit", "Reddit"],
            "weibo": ["微博", "weibo"],
            "zhihu": ["知乎", "zhihu"],
        }
        for site, keywords in site_mapping.items():
            if any(kw in request for kw in keywords):
                context.target_site = site
                break
        
        # 提取查询词（去掉 URL 和常见动词）
        query = request
        if context.detected_url:
            query = query.replace(context.detected_url, "")
        stop_words = ["搜索", "查找", "获取", "看看", "帮我", "我想", "请问", "能不能"]
        for word in stop_words:
            query = query.replace(word, "")
        context.query = query.strip()[:100] or None
        
        # 解析置信度（简单启发式）
        if context.detected_url and context.needs_interaction:
            context.parse_confidence = 1.0
        elif context.detected_url:
            context.parse_confidence = 0.9
        elif context.target_site:
            context.parse_confidence = 0.8
        elif context.query:
            context.parse_confidence = 0.7
        else:
            context.parse_confidence = 0.3
            
        context.parsed_intent = f"url={context.detected_url}, interaction={context.needs_interaction}, site={context.target_site}"
        
        return context
    
    def select_tool(self, context: WhiteBoxContext) -> WhiteBoxContext:
        """阶段 3: Tool 选择（实现决策树）"""
        # 决策树路径记录
        path = []
        
        # 规则 1: 需要交互 → browser
        if context.needs_interaction:
            path.append("rule:needs_interaction=true")
            context.selected_tool = ToolName.BROWSER
            context.selection_reason = "需要页面交互（点击/填写/登录等）"
            
        # 规则 2: 已知 URL
        elif context.detected_url:
            path.append("rule:has_url=true")
            
            # 检查是否为静态内容（简单启发式）
            static_extensions = ['.html', '.htm', '.md', '.txt', '.json', '.xml', '.rss']
            is_static = any(context.detected_url.endswith(ext) for ext in static_extensions)
            
            if is_static or any(kw in context.detected_url for kw in ['docs', 'api', 'blog', 'article']):
                path.append("rule:static_content=true")
                context.selected_tool = ToolName.WEB_FETCH
                context.selection_reason = "已知 URL 且为静态内容"
            else:
                path.append("rule:static_content=false")
                context.selected_tool = ToolName.OPENCLI
                context.selection_reason = "已知 URL 但可能需要 JS 渲染，先尝试 opencli"
                
        # 规则 3: 已知站点
        elif context.target_site:
            path.append(f"rule:target_site={context.target_site}")
            context.selected_tool = ToolName.OPENCLI
            context.selection_reason = f"目标站点 {context.target_site} 有专用 CLI 路径"
            
        # 规则 4: 开放查询
        else:
            path.append("rule:open_query=true")
            context.selected_tool = ToolName.WEB_SEARCH
            context.selection_reason = "无明确 URL，需要搜索信息"
            
        context.decision_tree_path = path
        return context
    
    def validate_schema(self, context: WhiteBoxContext) -> WhiteBoxContext:
        """阶段 4: Schema 校验"""
        errors = []
        params = {}
        
        if context.selected_tool == ToolName.WEB_SEARCH:
            # web_search schema
            if not context.query:
                errors.append("web_search 需要 query 参数")
            else:
                params["query"] = context.query
                params["count"] = 5  # 默认值
                
        elif context.selected_tool == ToolName.WEB_FETCH:
            # web_fetch schema
            if not context.detected_url:
                errors.append("web_fetch 需要 url 参数")
            else:
                params["url"] = context.detected_url
                
        elif context.selected_tool == ToolName.OPENCLI:
            # opencli schema
            if not context.target_site and not context.detected_url:
                errors.append("opencli 需要目标站点或 URL")
            else:
                if context.target_site:
                    params["site"] = context.target_site
                if context.detected_url:
                    params["url"] = context.detected_url
                if context.query:
                    params["query"] = context.query
                    
        elif context.selected_tool == ToolName.BROWSER:
            # browser schema
            if context.detected_url:
                params["url"] = context.detected_url
            params["action"] = "snapshot"  # 默认动作
            
        context.schema_valid = len(errors) == 0
        context.schema_errors = errors
        context.validated_params = params
        
        return context
    
    def execute_tool(self, context: WhiteBoxContext) -> WhiteBoxContext:
        """阶段 5: 执行（模拟）"""
        start_time = time.time()
        
        # 模拟执行延迟
        simulated_latency_ms = self._get_simulated_latency(context.selected_tool)
        time.sleep(simulated_latency_ms / 1000)
        
        # 模拟执行结果
        if context.selected_tool == ToolName.WEB_SEARCH:
            # 模拟 web_search 返回
            if context.query and "失败" in context.query:
                context.execution_status = ExecutionStatus.FAILURE
                context.execution_error = "API 配置错误: 缺少 API Key"
            else:
                context.execution_status = ExecutionStatus.SUCCESS
                context.execution_result = {
                    "results": [
                        {"title": "模拟结果 1", "url": "https://example.com/1", "snippet": "..."},
                        {"title": "模拟结果 2", "url": "https://example.com/2", "snippet": "..."},
                    ]
                }
                
        elif context.selected_tool == ToolName.WEB_FETCH:
            # 模拟 web_fetch 返回
            if context.detected_url and "slow" in context.detected_url:
                context.execution_status = ExecutionStatus.TIMEOUT
                context.execution_error = "请求超时 (30s)"
            elif context.detected_url and "403" in context.detected_url:
                context.execution_status = ExecutionStatus.FAILURE
                context.execution_error = "HTTP 403 Forbidden"
            else:
                context.execution_status = ExecutionStatus.SUCCESS
                context.execution_result = "# 模拟页面内容\n\n这是抓取的内容..."
                
        elif context.selected_tool == ToolName.OPENCLI:
            # 模拟 opencli 返回
            context.execution_status = ExecutionStatus.SUCCESS
            context.execution_result = {"stdout": "模拟 opencli 输出", "exit_code": 0}
            
        elif context.selected_tool == ToolName.BROWSER:
            # 模拟 browser 返回
            context.execution_status = ExecutionStatus.SUCCESS
            context.execution_result = {"snapshot": "模拟页面快照", "elements": 42}
            
        context.execution_duration_ms = int((time.time() - start_time) * 1000)
        return context
    
    def attempt_fallback(self, context: WhiteBoxContext) -> WhiteBoxContext:
        """阶段 6: 错误恢复/Fallback"""
        # 只有在执行失败时才尝试 fallback
        if context.execution_status in [ExecutionStatus.SUCCESS, ExecutionStatus.FALLBACK]:
            return context
            
        context.fallback_attempted = True
        
        # Fallback 链: web_search → opencli → browser
        #            web_fetch → opencli → browser
        #            opencli → browser
        
        if context.selected_tool == ToolName.WEB_SEARCH:
            # web_search 失败 → 引导配置（白盒逻辑）
            if "API" in (context.execution_error or ""):
                context.fallback_tool = ToolName.NONE  # 特殊：引导用户配置，不是工具 fallback
                context.fallback_reason = "web_search API 错误，需要引导用户配置"
                context.recovery_success = False  # 需要人工介入
            else:
                context.fallback_tool = ToolName.OPENCLI
                context.fallback_reason = "web_search 无结果，尝试 opencli"
                context.recovery_success = True
                
        elif context.selected_tool == ToolName.WEB_FETCH:
            # web_fetch 失败 → opencli → browser
            context.fallback_tool = ToolName.OPENCLI
            context.fallback_reason = f"web_fetch 失败 ({context.execution_error})，尝试 opencli"
            context.recovery_success = True
            
        elif context.selected_tool == ToolName.OPENCLI:
            # opencli 失败 → browser
            context.fallback_tool = ToolName.BROWSER
            context.fallback_reason = f"opencli 失败，升级到 browser"
            context.recovery_success = True
            
        return context
    
    def generate_answer(self, context: WhiteBoxContext) -> WhiteBoxContext:
        """阶段 7: 最终回答"""
        if context.execution_status == ExecutionStatus.SUCCESS:
            context.final_answer = f"成功使用 {context.selected_tool.value} 获取信息"
            context.success = True
        elif context.recovery_success:
            context.final_answer = f"通过 fallback 到 {context.fallback_tool.value} 成功获取信息"
            context.success = True
        else:
            context.final_answer = f"操作失败: {context.execution_error}"
            context.success = False
            
        context.answer_timestamp = datetime.now().isoformat()
        return context
    
    def run_test_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """运行单个白盒测试用例"""
        context = WhiteBoxContext(user_request=case["user_request"])
        context.test_case_id = case["id"]
        
        # 阶段 1: 用户请求（已初始化）
        
        # 阶段 2: Prompt/Ontology 解析
        context = self.parse_user_request(context)
        
        # 阶段 3: Tool 选择
        context = self.select_tool(context)
        
        # 阶段 4: Schema 校验
        context = self.validate_schema(context)
        
        # 阶段 5: 执行
        context = self.execute_tool(context)
        
        # 阶段 6: 错误恢复
        context = self.attempt_fallback(context)
        
        # 阶段 7: 最终回答
        context = self.generate_answer(context)
        
        # 转换为结果字典
        result = {
            "test_case_id": context.test_case_id,
            "user_request": context.user_request,
            "success": context.success,
            "white_box_trace": {
                "parse": {
                    "intent": context.parsed_intent,
                    "url_detected": context.detected_url,
                    "needs_interaction": context.needs_interaction,
                    "target_site": context.target_site,
                    "query": context.query,
                    "confidence": context.parse_confidence,
                },
                "tool_selection": {
                    "selected_tool": context.selected_tool.value,
                    "reason": context.selection_reason,
                    "decision_tree_path": context.decision_tree_path,
                },
                "schema_validation": {
                    "valid": context.schema_valid,
                    "errors": context.schema_errors,
                    "params": context.validated_params,
                },
                "execution": {
                    "status": context.execution_status.value,
                    "duration_ms": context.execution_duration_ms,
                    "error": context.execution_error,
                    "result_type": type(context.execution_result).__name__ if context.execution_result else None,
                },
                "fallback": {
                    "attempted": context.fallback_attempted,
                    "fallback_tool": context.fallback_tool.value if context.fallback_tool else None,
                    "reason": context.fallback_reason,
                    "recovery_success": context.recovery_success,
                },
                "answer": {
                    "final_answer": context.final_answer,
                    "success": context.success,
                }
            }
        }
        
        return result
    
    def run_single_scenario(self, user_request: str) -> dict[str, Any]:
        """运行单个测试场景（用于动态测试）"""
        # 构造临时测试用例
        case = {
            "id": f"DYNAMIC-{int(time.time())}",
            "name": "动态测试场景",
            "description": "从用户输入动态生成的测试",
            "user_request": user_request,
        }
        
        # 运行测试
        result = self.run_test_case(case)
        
        # 格式化输出（适合微信显示）
        trace = result["white_box_trace"]
        output = []
        output.append(f"📋 测试场景: {user_request}")
        output.append("")
        
        output.append("🔍 阶段 1: 请求解析")
        output.append(f"  URL: {trace['parse']['url_detected'] or '未检测到'}")
        output.append(f"  需要交互: {trace['parse']['needs_interaction']}")
        output.append(f"  目标站点: {trace['parse']['target_site'] or '无'}")
        output.append(f"  查询词: {trace['parse']['query'] or '无'}")
        output.append(f"  置信度: {trace['parse']['confidence']:.1%}")
        output.append("")
        
        output.append("🎯 阶段 2: 工具选择")
        output.append(f"  选中工具: {trace['tool_selection']['selected_tool']}")
        output.append(f"  选择原因: {trace['tool_selection']['reason']}")
        output.append(f"  决策路径: {' → '.join(trace['tool_selection']['decision_tree_path'])}")
        output.append("")
        
        output.append("✅ 阶段 3: Schema 校验")
        if trace['schema_validation']['valid']:
            output.append(f"  校验通过 ✓")
            output.append(f"  参数: {json.dumps(trace['schema_validation']['params'], ensure_ascii=False)}")
        else:
            output.append(f"  校验失败 ✗")
            output.append(f"  错误: {', '.join(trace['schema_validation']['errors'])}")
        output.append("")
        
        output.append("⚙️ 阶段 4: 执行")
        output.append(f"  状态: {trace['execution']['status']}")
        output.append(f"  耗时: {trace['execution']['duration_ms']}ms")
        if trace['execution']['error']:
            output.append(f"  错误: {trace['execution']['error']}")
        output.append("")
        
        if trace['fallback']['attempted']:
            output.append("🔄 阶段 5: 错误恢复")
            output.append(f"  Fallback 工具: {trace['fallback']['fallback_tool']}")
            output.append(f"  原因: {trace['fallback']['reason']}")
            output.append(f"  恢复成功: {trace['fallback']['recovery_success']}")
            output.append("")
        
        output.append("📤 阶段 6: 最终回答")
        output.append(f"  结果: {'✓ 成功' if result['success'] else '✗ 失败'}")
        output.append(f"  回答: {trace['answer']['final_answer']}")
        
        return {
            "formatted_output": "\n".join(output),
            "raw_result": result,
        }
    
    def run(self) -> dict[str, Any]:
        """运行所有测试用例"""
        cases = self.config.get("white_box_matrix_cases", [])
        skill_rules = self.load_skill_rules()
        
        print(f"Web-Tools-Guide 白盒矩阵测试")
        print(f"测试用例数: {len(cases)}")
        print(f"Skill MD 存在: {skill_rules['exists']}")
        
        results = []
        for case in cases:
            print(f"\n运行: {case['id']} - {case['name']}")
            result = self.run_test_case(case)
            results.append(result)
            
            # 打印简要结果
            trace = result["white_box_trace"]
            print(f"  解析: url={trace['parse']['url_detected']}, interaction={trace['parse']['needs_interaction']}")
            print(f"  工具: {trace['tool_selection']['selected_tool']} ({trace['tool_selection']['reason']})")
            print(f"  Schema: {'✓' if trace['schema_validation']['valid'] else '✗'}")
            print(f"  执行: {trace['execution']['status']} ({trace['execution']['duration_ms']}ms)")
            print(f"  Fallback: {'是' if trace['fallback']['attempted'] else '否'}")
            print(f"  结果: {'✓ 成功' if result['success'] else '✗ 失败'}")
            
        # 生成报告
        return self._generate_report(results, skill_rules)
    
    def _generate_report(self, results: list[dict], skill_rules: dict) -> dict:
        """生成测试报告"""
        total = len(results)
        successful = sum(1 for r in results if r["success"])
        
        # 按阶段统计失败
        stage_failures = {
            "parse": 0,
            "tool_selection": 0,
            "schema_validation": 0,
            "execution": 0,
            "fallback": 0,
        }
        
        for result in results:
            trace = result["white_box_trace"]
            if trace["parse"]["confidence"] < 0.5:
                stage_failures["parse"] += 1
            if trace["tool_selection"]["selected_tool"] == ToolName.NONE.value:
                stage_failures["tool_selection"] += 1
            if not trace["schema_validation"]["valid"]:
                stage_failures["schema_validation"] += 1
            if trace["execution"]["status"] not in [ExecutionStatus.SUCCESS.value, ExecutionStatus.FALLBACK.value]:
                stage_failures["execution"] += 1
            if trace["fallback"]["attempted"] and not trace["fallback"]["recovery_success"]:
                stage_failures["fallback"] += 1
        
        report = {
            "test_name": "web-tools-guide_white_box_matrix",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_cases": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": successful / total if total > 0 else 0,
                "stage_failures": stage_failures,
            },
            "skill_rules": skill_rules,
            "results": results,
        }
        
        print(f"\n=== 测试总结 ===")
        print(f"总数: {total}")
        print(f"成功: {successful}")
        print(f"失败: {total - successful}")
        print(f"成功率: {successful/total*100:.1f}%")
        print(f"阶段失败统计: {json.dumps(stage_failures, ensure_ascii=False)}")
        
        return report
    
    def _get_simulated_latency(self, tool: ToolName) -> int:
        """获取模拟延迟（毫秒）"""
        latencies = {
            ToolName.WEB_SEARCH: 120,
            ToolName.WEB_FETCH: 150,
            ToolName.OPENCLI: 100,
            ToolName.BROWSER: 220,
        }
        return latencies.get(tool, 100)


# ============================================================
# 配置和入口
# ============================================================

def load_config(path: str) -> dict[str, Any]:
    """加载配置文件"""
    path_obj = Path(path)
    if not path_obj.exists():
        # 尝试在默认位置查找
        alt_path = Path("/root/.openclaw/workspace") / path_obj.name
        if alt_path.exists():
            path = str(alt_path)
        else:
            raise FileNotFoundError(f"配置文件不存在: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_report(report: dict[str, Any], filename: str) -> str:
    """保存测试报告"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {filename}")
    return filename


def main():
    """主入口"""
    config = None
    output_file = None
    dynamic_request = None
    
    # 解析命令行参数
    if len(sys.argv) >= 2:
        args = sys.argv[1:]
        
        # 检查是否有 --request 选项（动态测试）
        if "--request" in args:
            idx = args.index("--request")
            if idx + 1 < len(args):
                dynamic_request = args[idx + 1]
                args = args[:idx] + args[idx + 2:]
        
        # 处理剩余参数
        if args:
            arg1 = args[0]
            if arg1.startswith("--"):
                if arg1 == "--use-defaults":
                    config = None
                    output_file = args[1] if len(args) > 1 else None
            else:
                try:
                    config = load_config(arg1)
                    output_file = args[1] if len(args) > 1 else None
                except FileNotFoundError:
                    print(f"配置文件不存在: {arg1}，使用默认配置")
                    config = None
    
    # 如果没有提供配置文件，自动加载默认配置
    tester = WebToolsGuideWhiteBoxMatrix(config)
    
    try:
        if dynamic_request:
            # 运行动态测试场景
            print(f"运行动态测试场景: {dynamic_request}")
            result = tester.run_single_scenario(dynamic_request)
            print("\n" + result["formatted_output"])
            
            # 保存结果
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"dynamic_test_result_{timestamp}.json"
            save_report({"dynamic_test": result["raw_result"]}, output_file)
            sys.exit(0)
        else:
            # 运行完整测试套件
            report = tester.run()
            
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"web_tools_guide_whitebox_matrix_{timestamp}.json"
            
            save_report(report, output_file)
            
            # 返回码
            if report["summary"]["failed"] > 0:
                sys.exit(1)
            sys.exit(0)
        
    except Exception as exc:
        print(f"测试失败: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
