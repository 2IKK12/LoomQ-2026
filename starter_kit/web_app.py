#!/usr/bin/env python3
"""Zero-dependency local web interface for the LoomQ L2 experience."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from . import adapter
    from .hardware_runner import hardware_status, run_hardware
    from .loomq_agent import (
        agent_chat_with_history,
        circuit_summary,
        explain_dictionary_term,
        explain_experiment_result,
        extract_qasm,
    )
except ImportError:
    import adapter
    from hardware_runner import hardware_status, run_hardware
    from loomq_agent import agent_chat_with_history, circuit_summary, explain_dictionary_term, explain_experiment_result, extract_qasm


WEB_ROOT = Path(__file__).resolve().parent / "web"
MAX_REQUEST_BYTES = 256 * 1024
API_VERSION = "closed-loop-4"


def build_translation_evidence(qasm: str) -> dict[str, Any]:
    """Build target programs through the public L1 transpiler, without claiming vendor execution."""
    labels = {
        "braket": "Braket · OpenQASM 3.0",
        "originq": "OriginQ · OriginIR",
        "spinq": "SpinQ · OpenQASM 2.0",
    }
    targets = []
    for target in ("braket", "originq", "spinq"):
        output = adapter.transpile(qasm, target)
        targets.append(
            {
                "target": target,
                "label": labels[target],
                "status": "generated_from_shared_ir",
                "output": output,
            }
        )
    return {
        "source": "OpenQASM 2.0",
        "verification": "All outputs were generated from the same L1 shared IR.",
        "vendor_execution_verified": False,
        "targets": targets,
    }


class LoomQHandler(BaseHTTPRequestHandler):
    server_version = "LoomQ/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print("[loomq] " + format % args)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length 无效") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("请求内容为空或过大")
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("请求不是有效 JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("请求必须是 JSON 对象")
        return value

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._json(200, {"service": "LoomQ", "api_version": API_VERSION})
            return
        if self.path == "/api/backends":
            self._json(200, hardware_status())
            return
        requested = "index.html" if self.path in {"/", "/index.html"} else self.path.lstrip("/")
        if requested not in {"index.html", "styles.css", "app.js"}:
            self.send_error(404)
            return
        path = WEB_ROOT / requested
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", media_type + ("; charset=utf-8" if media_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/api/chat":
                prompt = payload.get("prompt")
                history = payload.get("history", [])
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError("请先输入你想做的量子实验")
                reply = agent_chat_with_history(prompt.strip(), history)
                qasm = extract_qasm(reply)
                translations = build_translation_evidence(qasm) if qasm else None
                self._json(
                    200,
                    {
                        "reply": reply,
                        "qasm": qasm,
                        "circuit": circuit_summary(qasm) if qasm else None,
                        "translations": translations,
                    },
                )
                return
            if self.path == "/api/run":
                qasm = payload.get("qasm")
                target = payload.get("target", "braket")
                shots = payload.get("shots", 1024)
                if not isinstance(qasm, str) or not qasm.strip():
                    raise ValueError("当前没有可运行的 QASM 电路")
                execution_mode = payload.get("execution_mode", "local")
                if execution_mode == "hardware":
                    result = run_hardware(qasm, payload.get("hardware_backend", "braket_qpu"), shots)
                elif execution_mode == "local":
                    result = adapter.run(qasm, target, shots)
                else:
                    raise ValueError("execution_mode 必须是 local 或 hardware")
                response: dict[str, Any] = {"result": result}
                if payload.get("explain") is True:
                    prompt = payload.get("prompt")
                    agent_reply = payload.get("agent_reply", "")
                    if not isinstance(prompt, str) or not prompt.strip():
                        raise ValueError("解释运行结果时缺少原始问题")
                    if not isinstance(agent_reply, str):
                        raise ValueError("实验设计说明必须是文本")
                    try:
                        response["explanation"] = explain_experiment_result(
                            prompt,
                            qasm,
                            result,
                            agent_reply=agent_reply,
                        )
                    except Exception as exc:
                        response["explanation_error"] = f"{type(exc).__name__}: {exc}"
                self._json(200, response)
                return
            if self.path == "/api/explain":
                prompt = payload.get("prompt")
                qasm = payload.get("qasm")
                result = payload.get("result")
                question = payload.get("question", "")
                agent_reply = payload.get("agent_reply", "")
                previous = payload.get("previous_explanation", "")
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError("追问时缺少原始问题")
                if not isinstance(qasm, str) or not qasm.strip():
                    raise ValueError("追问时缺少实验 QASM")
                if not isinstance(result, dict):
                    raise ValueError("追问时缺少实验结果")
                if not all(isinstance(value, str) for value in (question, agent_reply, previous)):
                    raise ValueError("追问上下文必须是文本")
                explanation = explain_experiment_result(
                    prompt,
                    qasm,
                    result,
                    agent_reply=agent_reply,
                    follow_up=question,
                    previous_explanation=previous,
                )
                self._json(200, {"explanation": explanation})
                return
            if self.path == "/api/dictionary":
                term_key = payload.get("term_key")
                prompt = payload.get("prompt", "")
                qasm = payload.get("qasm")
                explanation = explain_dictionary_term(term_key, prompt, qasm)
                self._json(200, {"contextual_explanation": explanation})
                return
            self._json(404, {"error": "接口不存在"})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            # The LLM client deliberately excludes credentials from its errors.
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LoomQ local experience")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), LoomQHandler)
    print(f"LoomQ is ready: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLoomQ stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
