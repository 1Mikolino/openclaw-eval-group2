#!/usr/bin/env python3
"""
Ontology real white-box matrix test.

This file is intentionally only a judge:
- it provides user input to OpenClaw;
- it loads and snapshots white-box targets such as SKILL.md and graph.jsonl;
- it Strict Equal checks the internal output paths declared by each case.

Entity extraction is not implemented here. The actual values must come from the
OpenClaw kernel or from /skills/ontology/SKILL.md driven framework behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ontology_whitebox_cases import (
    EXPECTED_SKILL_ENTITY_TYPES,
    EXPECTED_SKILL_RELATION_TYPES,
    TEST_CASES,
)


SKILL_MD_PATH = os.environ.get(
    "ONTOLOGY_SKILL_MD_PATH",
    "/root/.openclaw/workspace/skills/ontology/SKILL.md",
)
ONTOLOGY_STORAGE = os.environ.get(
    "ONTOLOGY_STORAGE",
    "/root/.openclaw/workspace/memory/ontology",
)
TEST_RESULT_PATH = os.environ.get(
    "ONTOLOGY_TEST_RESULT_PATH",
    "/root/.openclaw/workspace/ontology_stability_whitebox_matrix.json",
)

OPENCLAW_COMMAND = os.environ.get("OPENCLAW_COMMAND")
OPENCLAW_TRACE_PATH = os.environ.get("OPENCLAW_TRACE_PATH")
OPENCLAW_TIMEOUT_SECONDS = int(os.environ.get("OPENCLAW_TIMEOUT_SECONDS", "120"))


class MissingPath:
    pass


MISSING = MissingPath()


@dataclass(frozen=True)
class StrictCheck:
    name: str
    path: str
    expected: Any


@dataclass(frozen=True)
class TestCase:
    case_id: str
    user_request: str
    checks: list[StrictCheck]


def format_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def read_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_json_from_stdout(stdout: str) -> Any:
    stdout = stdout.strip()
    if not stdout:
        raise ValueError("OpenClaw stdout is empty and no trace file was provided")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        pass

    # Some CLIs print logs before the final JSON line. Treat the last JSON-looking
    # line as the machine-readable white-box output.
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)

    raise ValueError("OpenClaw stdout did not contain a JSON object")


def split_selector(path: str) -> tuple[str, list[str]]:
    parts = path.split(".")
    if not parts or not parts[0]:
        raise ValueError(f"invalid selector: {path}")
    return parts[0], parts[1:]


def select_path(document: dict[str, Any], path: str) -> Any:
    root, selectors = split_selector(path)
    if root not in document:
        return MISSING

    current: Any = document[root]
    for selector in selectors:
        explode = selector.endswith("[]")
        key = selector[:-2] if explode else selector

        if isinstance(current, dict):
            current = current.get(key, MISSING)
        elif isinstance(current, list) and key.isdigit():
            index = int(key)
            current = current[index] if 0 <= index < len(current) else MISSING
        else:
            return MISSING

        if current is MISSING:
            return MISSING

        if explode:
            if not isinstance(current, list):
                return MISSING
            current = list(current)

    return current


def select_path_with_projection(document: dict[str, Any], path: str) -> Any:
    """Resolve paths like kernel.trace.entities[].name into a flat list."""
    if "[]." not in path:
        return select_path(document, path)

    prefix, suffix = path.split("[].", 1)
    collection = select_path(document, f"{prefix}[]")
    if collection is MISSING or not isinstance(collection, list):
        return MISSING

    projected = []
    for item in collection:
        if not isinstance(item, dict):
            return MISSING
        value = select_path({"item": item}, f"item.{suffix}")
        if value is MISSING:
            return MISSING
        projected.append(value)
    return projected


class SkillProbe:
    def __init__(self, skill_md_path: str):
        self.skill_md_path = skill_md_path

    def load(self) -> dict[str, Any]:
        result = {
            "exists": False,
            "path": self.skill_md_path,
            "content_sha_hint": None,
            "entity_types": [],
            "relation_types": [],
            "load_error": None,
        }

        try:
            if not os.path.exists(self.skill_md_path):
                result["load_error"] = "File not found"
                return result

            with open(self.skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()

            result["exists"] = True
            result["content_sha_hint"] = f"chars:{len(content)}"
            result["entity_types"] = self._extract_entity_types(content)
            result["relation_types"] = self._extract_relation_types(content)
        except Exception as exc:
            result["load_error"] = str(exc)

        return result

    def _extract_entity_types(self, content: str) -> list[str]:
        section = re.search(r"## Core Types.*?\n```yaml\n(.*?)```", content, re.DOTALL)
        if not section:
            section = re.search(r"```yaml\n(.*?)```", content, re.DOTALL)

        types = []
        if section:
            for raw_line in section.group(1).splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"^([A-Z]\w*):", line)
                if match and match.group(1) not in ("Types", "Relations"):
                    types.append(match.group(1))

        if not types:
            types = [name for name in EXPECTED_SKILL_ENTITY_TYPES if name in content]

        return sorted(set(types))

    def _extract_relation_types(self, content: str) -> list[str]:
        relations = self._extract_first_level_mapping_keys(content, "relations")

        for relation in EXPECTED_SKILL_RELATION_TYPES:
            if relation in content and relation not in relations:
                relations.append(relation)

        return sorted(set(relations))

    def _extract_first_level_mapping_keys(
        self,
        content: str,
        parent_key: str,
    ) -> list[str]:
        lines = content.splitlines()
        parent_indent = None
        child_indent = None
        keys = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(line.lstrip(" "))
            if parent_indent is None:
                if re.match(rf"^{re.escape(parent_key)}\s*:\s*$", stripped):
                    parent_indent = indent
                continue

            if indent <= parent_indent:
                break

            match = re.match(r"^([A-Za-z_]\w*)\s*:", stripped)
            if not match:
                continue

            if child_indent is None:
                child_indent = indent

            if indent == child_indent:
                keys.append(match.group(1))

        return keys


class StorageProbe:
    def __init__(self, ontology_storage: str):
        self.ontology_storage = ontology_storage
        self.graph_path = os.path.join(ontology_storage, "graph.jsonl")

    def init(self) -> None:
        os.makedirs(self.ontology_storage, exist_ok=True)
        if not os.path.exists(self.graph_path):
            open(self.graph_path, "a", encoding="utf-8").close()

    def snapshot(self) -> dict[str, Any]:
        result = {
            "path": self.ontology_storage,
            "graph_path": self.graph_path,
            "exists": os.path.isdir(self.ontology_storage),
            "graph_exists": os.path.exists(self.graph_path),
            "line_count": 0,
            "graph_records": [],
            "entity_ids": [],
            "entity_names": [],
            "relation_types": [],
            "read_errors": [],
        }

        if not result["graph_exists"]:
            return result

        with open(self.graph_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                result["line_count"] += 1
                try:
                    record = json.loads(line)
                    result["graph_records"].append(record)
                    entity = record.get("entity", {})
                    relation = record.get("relation", {})
                    if entity.get("id") is not None:
                        result["entity_ids"].append(entity["id"])
                    name = entity.get("properties", {}).get("name") or entity.get("name")
                    if name is not None:
                        result["entity_names"].append(name)
                    if relation.get("type") is not None:
                        result["relation_types"].append(relation["type"])
                except json.JSONDecodeError as exc:
                    result["read_errors"].append(
                        {"line": line_number, "error": str(exc), "raw": line}
                    )

        return result

    def delta(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        before_record_count = len(before.get("graph_records", []))
        after_records = after.get("graph_records", [])
        new_records = after_records[before_record_count:]
        entity_names = []
        relation_types = []

        for record in new_records:
            entity = record.get("entity", {})
            relation = record.get("relation", {})
            name = entity.get("properties", {}).get("name") or entity.get("name")
            if name is not None:
                entity_names.append(name)
            if relation.get("type") is not None:
                relation_types.append(relation["type"])

        return {
            "line_count_before": before.get("line_count", 0),
            "line_count_after": after.get("line_count", 0),
            "record_count_before": before_record_count,
            "record_count_after": len(after_records),
            "new_record_count": len(new_records),
            "new_records": new_records,
            "entity_names": entity_names,
            "relation_types": relation_types,
        }


class OpenClawKernelProbe:
    def __init__(
        self,
        command: str | None,
        trace_path: str | None,
        timeout_seconds: int,
    ):
        self.command = command
        self.trace_path = trace_path
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.command or self.trace_path)

    def run(self, case_id: str, user_request: str) -> dict[str, Any]:
        trace_path = self._format_optional(self.trace_path, case_id, user_request)
        command_output = None

        if self.command:
            command_output = self._run_command(case_id, user_request)

        if trace_path:
            return read_json_file(trace_path)

        if not self.command:
            raise RuntimeError(
                "No OpenClaw source configured. Set OPENCLAW_COMMAND to run the "
                "kernel, or OPENCLAW_TRACE_PATH to replay a real white-box trace."
            )

        return command_output

    def _run_command(self, case_id: str, user_request: str) -> dict[str, Any]:
        command = self._format_optional(self.command, case_id, user_request)
        payload = json.dumps(
            {
                "input": user_request,
                "case_id": case_id,
                "white_box": True,
                "skill": "ontology",
            },
            ensure_ascii=False,
        )

        completed = subprocess.run(
            command,
            input=payload.encode("utf-8"),
            capture_output=True,
            shell=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")

        if completed.returncode != 0:
            raise RuntimeError(
                "OpenClaw command failed "
                f"(exit={completed.returncode}, stderr={stderr.strip()})"
            )

        return parse_json_from_stdout(stdout)

    def _format_optional(
        self,
        template: str | None,
        case_id: str,
        user_request: str,
    ) -> str | None:
        if template is None:
            return None
        return (
            template.replace("{case_id}", case_id)
            .replace("{request_json}", json.dumps(user_request, ensure_ascii=False))
            .replace("{request}", user_request)
        )


class OntologyWhiteboxMatrixTest:
    def __init__(
        self,
        skill_md_path: str,
        ontology_storage: str,
        result_path: str,
        kernel_probe: OpenClawKernelProbe,
    ):
        self.skill_probe = SkillProbe(skill_md_path)
        self.storage_probe = StorageProbe(ontology_storage)
        self.result_path = result_path
        self.kernel_probe = kernel_probe
        self.results: list[dict[str, Any]] = []

    def run_case(self, test_case: TestCase) -> dict[str, Any]:
        print(f"\n{'=' * 72}")
        print(f"[{test_case.case_id}] {test_case.user_request}")

        skill_load = self.skill_probe.load()
        state_before = self.storage_probe.snapshot()
        kernel_output: dict[str, Any] = {}
        execution_error = None

        try:
            kernel_output = self.kernel_probe.run(
                test_case.case_id,
                test_case.user_request,
            )
        except Exception as exc:
            execution_error = str(exc)

        state_after = self.storage_probe.snapshot()
        state_delta = self.storage_probe.delta(state_before, state_after)

        context = {
            "skill": skill_load,
            "kernel": kernel_output,
            "state_before": state_before,
            "state_after": state_after,
            "state_delta": state_delta,
        }
        validation = self._validate(test_case.checks, context, execution_error)
        success = validation["passed"]

        result = {
            "test_case_id": test_case.case_id,
            "user_request": test_case.user_request,
            "success": success,
            "white_box_trace": {
                "skill_load": skill_load,
                "kernel_output": kernel_output,
                "state_before": state_before,
                "state_after": state_after,
                "state_delta": state_delta,
                "validation": validation,
            },
            "answer": {
                "success": success,
                "final_answer": "Strict Equal passed"
                if success
                else "Strict Equal failed",
            },
        }
        self.results.append(result)

        print("结果:", "PASS" if success else "FAIL")
        if not success:
            for error in validation["errors"]:
                print(f"  - {error}")

        return result

    def _validate(
        self,
        checks: list[StrictCheck],
        context: dict[str, Any],
        execution_error: str | None,
    ) -> dict[str, Any]:
        errors = []
        details = []

        if execution_error:
            errors.append(f"OpenClaw execution error: {execution_error}")

        for check in checks:
            actual = select_path_with_projection(context, check.path)
            passed = actual == check.expected
            detail = {
                "name": check.name,
                "path": check.path,
                "expected": check.expected,
                "actual": None if actual is MISSING else actual,
                "passed": passed,
            }
            details.append(detail)

            if actual is MISSING:
                errors.append(f"{check.name}: missing internal path {check.path}")
            elif not passed:
                errors.append(
                    f"{check.name}: expected {format_json(check.expected)}, "
                    f"actual {format_json(actual)}"
                )

        return {
            "passed": not errors,
            "errors": errors,
            "checks": details,
            "confidence_score": 1.0 if not errors else 0.0,
        }

    def generate_report(self) -> dict[str, Any]:
        report = {
            "test_name": "ontology_whitebox_matrix_strict_equal",
            "timestamp": datetime.now().isoformat(),
            "judge_contract": {
                "entity_extraction_in_test_script": False,
                "actual_source": "OpenClaw kernel white-box output",
                "strict_equal": "actual == expected",
            },
            "summary": {
                "total_cases": len(self.results),
                "successful": sum(1 for result in self.results if result["success"]),
                "failed": sum(1 for result in self.results if not result["success"]),
            },
            "results": self.results,
        }
        total = report["summary"]["total_cases"]
        report["summary"]["success_rate"] = (
            report["summary"]["successful"] / total if total else 0
        )

        with open(self.result_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 72}")
        print(f"报告: {self.result_path}")
        print(f"总用例: {report['summary']['total_cases']}")
        print(f"成功: {report['summary']['successful']}")
        print(f"失败: {report['summary']['failed']}")
        print(f"成功率: {report['summary']['success_rate']:.1%}")
        return report


def load_test_matrix() -> list[TestCase]:
    matrix = []
    for raw_case in TEST_CASES:
        checks = [
            StrictCheck(
                name=raw_check["name"],
                path=raw_check["path"],
                expected=raw_check["expected"],
            )
            for raw_check in raw_case["checks"]
        ]
        matrix.append(
            TestCase(
                case_id=raw_case["case_id"],
                user_request=raw_case["user_request"],
                checks=checks,
            )
        )
    return matrix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ontology white-box matrix tests as a Strict Equal judge."
    )
    parser.add_argument(
        "--case",
        dest="case_id",
        help="Run one case id only, for example REAL-001.",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="Print the matrix selectors and expected values, then exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = load_test_matrix()

    if args.case_id:
        matrix = [case for case in matrix if case.case_id == args.case_id]
        if not matrix:
            raise SystemExit(f"Unknown case id: {args.case_id}")

    if args.list_checks:
        for case in matrix:
            print(f"\n[{case.case_id}] {case.user_request}")
            for check in case.checks:
                print(f"  {check.path} == {format_json(check.expected)}")
        return 0

    print("Ontology real white-box matrix test")
    print(f"SKILL.md: {SKILL_MD_PATH}")
    print(f"Ontology storage: {ONTOLOGY_STORAGE}")
    print("Actual extraction source: OpenClaw kernel / ontology skill trace")

    kernel_probe = OpenClawKernelProbe(
        command=OPENCLAW_COMMAND,
        trace_path=OPENCLAW_TRACE_PATH,
        timeout_seconds=OPENCLAW_TIMEOUT_SECONDS,
    )
    if not kernel_probe.is_configured():
        print()
        print("配置错误: 没有 OpenClaw 输出源，无法计算 ontology 正确率。")
        print("请设置 OPENCLAW_COMMAND 运行真实内核，或设置 OPENCLAW_TRACE_PATH 回放真实 trace。")
        print("示例:")
        print("  export OPENCLAW_COMMAND='你的 openclaw 白盒执行命令'")
        print("  python3 ontology_real_whitebox_test.py")
        print("或:")
        print("  export OPENCLAW_TRACE_PATH='/root/.openclaw/workspace/traces/{case_id}.json'")
        print("  python3 ontology_real_whitebox_test.py")
        return 2

    tester = OntologyWhiteboxMatrixTest(
        skill_md_path=SKILL_MD_PATH,
        ontology_storage=ONTOLOGY_STORAGE,
        result_path=TEST_RESULT_PATH,
        kernel_probe=kernel_probe,
    )
    tester.storage_probe.init()

    for test_case in matrix:
        tester.run_case(test_case)

    report = tester.generate_report()
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
