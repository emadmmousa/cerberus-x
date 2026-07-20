"""Dynamic YAML playbook compiler with safe condition evaluation."""

from __future__ import annotations

import ast
import logging
import operator
import re
from typing import Any

import yaml
from celery import group

from orchestrator.ai_decision import AIDecisionEngine
from utils.global_state import get_session_state
from workers.tasks import run_tool

logger = logging.getLogger(__name__)

_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

_BIN_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
}


class DynamicPlaybookCompiler:
    @staticmethod
    def compile(
        playbook_yaml: str, session_id: str, context: dict | None = None, *, use_ai: bool = True
    ) -> list[dict]:
        data = yaml.safe_load(playbook_yaml) or {}
        tasks: list[dict] = []
        context = dict(context or {})
        state = get_session_state(session_id) or {}

        steps = data.get("steps") or data.get("phases") or []
        # Support default.yaml-like phases: [{name, tools:[{tool,args}]}]
        if steps and isinstance(steps[0], dict) and "tools" in steps[0] and "tool" not in steps[0]:
            for phase in steps:
                for tool in phase.get("tools") or []:
                    if isinstance(tool, dict) and tool.get("tool"):
                        tasks.append(
                            {
                                "tool": tool["tool"],
                                "params": {"args": tool.get("args") or []},
                            }
                        )
            return tasks

        for step in steps:
            if not isinstance(step, dict) or not step.get("tool"):
                continue
            if "when" in step:
                if not DynamicPlaybookCompiler._eval_condition(
                    str(step["when"]), state, context
                ):
                    continue
            if "loop" in step and isinstance(step["loop"], dict):
                loop_var = step["loop"].get("var", "item")
                loop_over = step["loop"].get("over", [])
                items = DynamicPlaybookCompiler._resolve_loop(loop_over, state, context)
                for item in items:
                    local_ctx = {**context, loop_var: item, "loop": {loop_var: item}}
                    tasks.append(
                        DynamicPlaybookCompiler._build_task(step, state, local_ctx)
                    )
            else:
                tasks.append(DynamicPlaybookCompiler._build_task(step, state, context))

        if use_ai:
            try:
                ai_plan = AIDecisionEngine().decide(
                    session_id, state.get("last_scan") or {"target": context.get("target")}
                )
                for ai_task in ai_plan:
                    if ai_task.get("tool"):
                        tasks.append(
                            {"tool": ai_task["tool"], "params": ai_task.get("params") or {}}
                        )
            except Exception as exc:
                logger.warning("AI append skipped: %s", exc)
        return tasks

    @staticmethod
    def _resolve_value(path: str, state: dict, context: dict) -> Any:
        root = None
        parts = path.split(".")
        if not parts:
            return None
        if parts[0] == "state":
            root = state
            parts = parts[1:]
        elif parts[0] == "context":
            root = context
            parts = parts[1:]
        elif parts[0] == "loop":
            root = context.get("loop") or {}
            parts = parts[1:]
        else:
            return context.get(path, state.get(path))
        cur: Any = root
        for part in parts:
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        return cur

    @staticmethod
    def _render(value: Any, state: dict, context: dict) -> Any:
        if isinstance(value, str):

            def repl(match):
                resolved = DynamicPlaybookCompiler._resolve_value(
                    match.group(1), state, context
                )
                return "" if resolved is None else str(resolved)

            return _TEMPLATE_RE.sub(repl, value)
        if isinstance(value, dict):
            return {
                k: DynamicPlaybookCompiler._render(v, state, context)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [DynamicPlaybookCompiler._render(v, state, context) for v in value]
        return value

    @staticmethod
    def _eval_condition(cond: str, state: dict, context: dict) -> bool:
        """
        Safe boolean evaluator for expressions like:
          {{context.allow_scan}}
          {{context.aggressive_level}} > 5
          {{state.web_found}} and {{context.allow_scan}}
        """
        expr = cond.strip()
        if not expr:
            return True

        # Replace templates with literal Python values via AST-friendly tokens.
        mapping: dict[str, Any] = {}

        def repl(match):
            key = f"V{len(mapping)}"
            mapping[key] = DynamicPlaybookCompiler._resolve_value(
                match.group(1), state, context
            )
            return key

        rendered = _TEMPLATE_RE.sub(repl, expr)
        rendered = rendered.replace("&&", " and ").replace("||", " or ")
        # Support "X is defined"
        rendered = re.sub(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s+is\s+defined\b",
            r"(\1 is not None)",
            rendered,
        )
        try:
            tree = ast.parse(rendered, mode="eval")
            return bool(DynamicPlaybookCompiler._eval_ast(tree.body, mapping))
        except Exception:
            # Fallback: truthiness of a single resolved template.
            if expr.startswith("{{") and expr.endswith("}}"):
                inner = expr.strip("{} ")
                return bool(DynamicPlaybookCompiler._resolve_value(inner, state, context))
            return False

    @staticmethod
    def _eval_ast(node: ast.AST, env: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in {"True", "False", "None"}:
                return {"True": True, "False": False, "None": None}[node.id]
            raise ValueError(f"unknown name {node.id}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not DynamicPlaybookCompiler._eval_ast(node.operand, env)
        if isinstance(node, ast.BoolOp):
            vals = [DynamicPlaybookCompiler._eval_ast(v, env) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(vals)
            if isinstance(node.op, ast.Or):
                return any(vals)
        if isinstance(node, ast.Compare):
            left = DynamicPlaybookCompiler._eval_ast(node.left, env)
            for op, comparator in zip(node.ops, node.comparators):
                right = DynamicPlaybookCompiler._eval_ast(comparator, env)
                fn = _BIN_OPS.get(type(op))
                if fn is None:
                    raise ValueError("unsupported compare")
                if not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add,)):
            # disallow arbitrary math except simple compares already handled
            raise ValueError("unsupported binop")
        raise ValueError(f"unsupported expression: {type(node)}")

    @staticmethod
    def _resolve_loop(over: Any, state: dict, context: dict) -> list:
        if isinstance(over, list):
            return over
        if isinstance(over, str):
            rendered = DynamicPlaybookCompiler._render(over, state, context)
            if isinstance(rendered, list):
                return rendered
            if isinstance(over, str) and (over.startswith("state.") or over.startswith("{{state.")):
                key = over.replace("{{", "").replace("}}", "").strip()
                val = DynamicPlaybookCompiler._resolve_value(key, state, context)
                return val if isinstance(val, list) else []
            if over.startswith("context.") or over.startswith("{{context."):
                key = over.replace("{{", "").replace("}}", "").strip()
                val = DynamicPlaybookCompiler._resolve_value(key, state, context)
                return val if isinstance(val, list) else []
        return []

    @staticmethod
    def _build_task(step: dict, state: dict, context: dict) -> dict:
        params = DynamicPlaybookCompiler._render(step.get("params") or {}, state, context)
        if not isinstance(params, dict):
            params = {}
        # Ensure target surfaces for workers.tasks.run_tool
        if "target" not in params and context.get("target"):
            params["target"] = context["target"]
        return {"tool": step["tool"], "params": params}

    @staticmethod
    def execute_playbook(
        playbook_path: str,
        session_id: str,
        context: dict | None = None,
        *,
        use_ai: bool = False,
    ) -> int:
        with open(playbook_path, encoding="utf-8") as handle:
            yaml_content = handle.read()
        tasks = DynamicPlaybookCompiler.compile(
            yaml_content, session_id, context, use_ai=use_ai
        )
        if not tasks:
            logger.info("No tasks compiled from %s", playbook_path)
            return 0
        job = group(
            run_tool.s(t["tool"], t.get("params") or {}, session_id) for t in tasks
        )
        job.apply_async()
        logger.info(
            "Executed %s dynamic tasks from %s for session %s",
            len(tasks),
            playbook_path,
            session_id,
        )
        return len(tasks)
