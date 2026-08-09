"""LoomQ L2 agent with L1-backed QASM validation and repair."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from .llm_client import chat_completion
    from .loomq_l1 import QASMError, emit_target, parse_qasm
except ImportError:
    from llm_client import chat_completion
    from loomq_l1 import QASMError, emit_target, parse_qasm


ROOT = Path(__file__).resolve().parent
CAPABILITIES = json.loads((ROOT / "backend_capabilities.json").read_text(encoding="utf-8"))
MAX_REPAIR_ATTEMPTS = 1

SYSTEM_PROMPT = """You are LoomQ, a careful bilingual guide for people with no quantum background.

You have three jobs:
1. Generate complete OpenQASM 2.0 programs from user intent.
2. Repair QASM while preserving the user's explicitly stated target state or behavior.
3. Recommend backends by filtering the supplied official capability records.

QASM rules for runnable circuit requests:
- Include OPENQASM 2.0, qelib1.inc, qreg, creg, and measurement.
- Only use h, x, s, sdg, t, tdg, rz(theta), ry(theta), cx, cu1(theta), swap, ccx.
- Gate names are lowercase. Use valid commas, semicolons, indices, and declared registers.
- For GHZ(n): apply h to q[0], then a cx chain. For a Bell state: h then cx.
- Put the final program in one ```qasm code fence and briefly explain the expected result.
- Think through syntax, register sizes, target-state semantics, and measurements before answering.

Backend rules:
- Treat OFFICIAL_BACKENDS as the only scoring truth.
- Filter every explicit constraint: qubit count, real hardware vs simulator, queue, cost,
  and account requirement. Do not invent live availability.
- Include at least one exact backend `id` from a matching record in the answer.
- If several records match, recommend one and name the alternatives. If none match, say so
  clearly and propose the closest feasible change.

Inclusive communication rules:
- Never assume the user already knows qubit, circuit, gate, backend, shots,
  superposition, or entanglement. Define a technical term immediately when it
  first appears, after giving the everyday-language idea.
- For an experiment, explain in this order: what question we are exploring,
  what the experiment will do, what result the user may see, and only then the
  technical name and QASM.
- Choose the smallest circuit that directly represents the user's intent. Do
  not default unrelated requests to a one-qubit Hadamard coin. Distinct intents
  such as randomness, Bell correlation, GHZ correlation, phase, rotation, swap,
  and controlled logic should produce materially different circuits when the
  science calls for them.
- A conceptual or unsuitable request may legitimately have no QASM. Never add
  a generic circuit merely to make every response runnable.
- Connect bit strings such as 00 and 11 to visible outcomes; say that each digit
  is one measured quantum bit and that the string is not a score.
- Do not exaggerate quantum advantage. If a request is not suitable for the
  supported small circuits, say so plainly and offer a related learning
  experiment instead of pretending to solve it.
- Welcome incomplete, non-technical, and curiosity-driven questions. Never call
  a question basic, naive, wrong, or poorly phrased.
- When conversation history is supplied, resolve short answers and pronouns
  against the recent discussion. The latest user message may answer a question
  you asked in the previous turn. If the user clearly changes topic, prioritize
  the new topic instead of forcing the old experiment to continue.
- In a runnable experiment response, describe only the final requested circuit.
  Do not add unsolicited backend recommendations or repeat obsolete qubit counts
  from earlier turns; the latest user correction is authoritative.

Be concise, concrete, encouraging, and honest. Reply in the user's language.

OFFICIAL_BACKENDS:
""" + json.dumps(CAPABILITIES["backends"], ensure_ascii=False, separators=(",", ":"))


def _content(response: dict[str, Any]) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LoomQ L2 API returned an invalid response shape") from exc
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("LoomQ L2 API returned empty content")
    return value.strip()


def extract_qasm(text: str) -> str | None:
    fenced = re.search(r"```(?:qasm|openqasm)?\s*(OPENQASM\s+2(?:\.0)?;.*?)```", text, re.I | re.S)
    if fenced:
        return fenced.group(1).strip()
    plain = re.search(r"(OPENQASM\s+2(?:\.0)?;.*)\Z", text, re.I | re.S)
    return plain.group(1).strip() if plain else None


def _requested_qubits(prompt: str) -> int | None:
    patterns = (
        r"(?<!\d)(\d+)\s*(?:个\s*)?(?:量子比特|比特)",
        r"(?<!\d)(\d+)\s*[- ]?\s*qubits?\b",
        r"(?:改成|换成|增加到|扩展到|用|要)\s*(\d+)\s*个(?:\b|[，。；、,;])",
        r"(?:make|change|expand)\s+(?:it\s+)?(?:to\s+)?(\d+)\b",
    )
    matches = [
        (match.start(), int(match.group(1)))
        for pattern in patterns
        for match in re.finditer(pattern, prompt, re.I)
    ]
    return max(matches, default=(0, None), key=lambda item: item[0])[1]


def _intent_kind(prompt: str) -> str | None:
    lowered = prompt.lower()
    categories = (
        ("cat", ("ghz", "猫态", "薛定谔", "schrodinger", "schrödinger")),
        ("bell", ("bell", "贝尔态", "贝尔纠缠")),
        ("swap", ("swap", "交换门", "交换量子")),
        ("toffoli", ("toffoli", "ccx", "托福利", "托佛利")),
        ("phase", ("phase", "相位", "干涉")),
        ("rotation", ("rotation", "rotate", "旋转")),
        ("random", ("random", "随机", "硬币")),
    )
    matches = [
        (lowered.rfind(marker), kind)
        for kind, markers in categories
        for marker in markers
        if marker in lowered
    ]
    return max(matches, default=(-1, None), key=lambda item: item[0])[1]


def _resolved_intent_kind(prompt: str) -> str | None:
    """Treat an explicitly resized Bell circuit as the corresponding GHZ family."""
    kind = _intent_kind(prompt)
    requested = _requested_qubits(prompt)
    if kind == "bell" and requested is not None and requested != 2:
        return "cat"
    return kind


def _requests_runnable_experiment(prompt: str) -> bool:
    lowered = prompt.lower()
    markers = (
        "生成", "创建", "制备", "编写", "写一个", "用代码", "运行", "模拟",
        "演示", "设计", "让我看", "让我看到", "给我一个", "generate", "create",
        "prepare", "write", "run", "simulate", "build", "show me", "qasm", "circuit",
    )
    return any(marker in lowered for marker in markers)


def validate_intent(prompt: str, qasm: str | None) -> list[str]:
    """Return deterministic intent/QASM mismatches for common contest experiments."""
    kind = _resolved_intent_kind(prompt)
    requested = _requested_qubits(prompt)
    if qasm is None:
        if kind is not None and _requests_runnable_experiment(prompt):
            return [f"the user requested a runnable {kind} experiment but the answer has no QASM"]
        return []
    try:
        circuit = parse_qasm(qasm)
    except (QASMError, ValueError):
        return []  # Syntax errors are reported by the normal validator.

    errors: list[str] = []
    gates = [operation.name for operation in circuit.operations]
    measured = {qubit for qubit, _ in circuit.measurements}
    if requested is not None and circuit.qubit_count != requested:
        errors.append(
            f"the user requested {requested} qubits but the circuit declares {circuit.qubit_count}"
        )
    if kind == "bell":
        if circuit.qubit_count != 2:
            errors.append("a Bell-state experiment must use exactly 2 qubits")
        if "h" not in gates or "cx" not in gates:
            errors.append("a Bell-state circuit needs both h and cx")
    elif kind == "cat":
        minimum = requested if requested is not None else 3
        if circuit.qubit_count < minimum:
            errors.append(f"the requested cat/GHZ experiment needs at least {minimum} qubits")
        if "h" not in gates:
            errors.append("a cat/GHZ circuit needs an h gate to create superposition")
        if gates.count("cx") < max(circuit.qubit_count - 1, 1):
            errors.append("a cat/GHZ circuit needs a cx chain connecting all qubits")
        if measured != set(range(circuit.qubit_count)):
            errors.append("a cat/GHZ experiment must measure every declared qubit")
    elif kind == "random" and not ({"h", "ry"} & set(gates)):
        errors.append("a quantum-randomness circuit needs h or a non-trivial ry rotation")
    elif kind == "swap" and "swap" not in gates:
        errors.append("the requested swap experiment does not contain a swap gate")
    elif kind == "toffoli" and "ccx" not in gates:
        errors.append("the requested Toffoli experiment does not contain a ccx gate")
    elif kind == "phase" and not ({"s", "sdg", "t", "tdg", "rz", "cu1"} & set(gates)):
        errors.append("the requested phase experiment contains no supported phase gate")
    elif kind == "rotation" and not ({"ry", "rz"} & set(gates)):
        errors.append("the requested rotation experiment contains no ry or rz gate")
    return errors


def circuit_summary(qasm: str) -> dict[str, Any]:
    circuit = parse_qasm(qasm)
    return {
        "qubits": circuit.qubit_count,
        "classical_bits": circuit.classical_count,
        "gates": [operation.name for operation in circuit.operations],
        "measurements": len(circuit.measurements),
    }


def _prose_qubit_counts(text: str) -> set[int]:
    prose = re.sub(r"```(?:qasm|openqasm)?\s*.*?```", "", text, flags=re.I | re.S)
    patterns = (
        r"(?<!\d)(\d+)\s*(?:个\s*)?(?:量子比特|比特)",
        r"(?<!\d)(\d+)\s*[- ]?\s*qubits?\b",
    )
    return {
        int(match.group(1))
        for pattern in patterns
        for match in re.finditer(pattern, prose, re.I)
    }


def _validated_qasm(text: str, prompt: str = "") -> tuple[str | None, str | None]:
    qasm = extract_qasm(text)
    if qasm is None:
        semantic_errors = validate_intent(prompt, None)
        return None, "; ".join(semantic_errors) if semantic_errors else None
    try:
        circuit = parse_qasm(qasm)
        # Exercising every emitter catches target-specific serialization failures too.
        for target in ("spinq", "originq", "braket"):
            emit_target(circuit, target)
    except (QASMError, ValueError) as exc:
        return qasm, str(exc)
    semantic_errors = validate_intent(prompt, qasm)
    requested = _requested_qubits(prompt)
    if requested is not None:
        conflicting = sorted(_prose_qubit_counts(text) - {requested})
        if conflicting:
            semantic_errors.append(
                "the final prose describes obsolete qubit count(s) "
                + ", ".join(map(str, conflicting))
                + f"; describe only the latest requested {requested}-qubit circuit"
            )
    if semantic_errors:
        return qasm, "; ".join(semantic_errors)
    return qasm, None


def _intent_contract_text(prompt: str) -> str:
    kind = _resolved_intent_kind(prompt) or "unspecified"
    qubits = _requested_qubits(prompt)
    return f"experiment={kind}; qubits={qubits if qubits is not None else 'not explicitly fixed'}"


def _latest_history_qasm(history: list[dict[str, str]]) -> str | None:
    for item in reversed(history):
        if item["role"] != "assistant":
            continue
        qasm = extract_qasm(item["content"])
        if qasm is None:
            continue
        try:
            parse_qasm(qasm)
        except (QASMError, ValueError):
            continue
        return qasm
    return None


def _is_ghz_family(qasm: str) -> bool:
    circuit = parse_qasm(qasm)
    operations = circuit.operations
    if circuit.qubit_count < 2 or len(operations) != circuit.qubit_count:
        return False
    if operations[0].name != "h" or operations[0].qubits != (0,):
        return False
    edges = {
        operation.qubits
        for operation in operations[1:]
        if operation.name == "cx"
    }
    if len(edges) != circuit.qubit_count - 1:
        return False
    reached = {0}
    pending = set(edges)
    while pending:
        usable = next((edge for edge in pending if edge[0] in reached and edge[1] not in reached), None)
        if usable is None:
            return False
        reached.add(usable[1])
        pending.remove(usable)
    return reached == set(range(circuit.qubit_count))


def _ghz_qasm(qubits: int) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qubits}];",
        f"creg c[{qubits}];",
        "h q[0];",
    ]
    lines.extend(f"cx q[{index - 1}], q[{index}];" for index in range(1, qubits))
    lines.extend(f"measure q[{index}] -> c[{index}];" for index in range(qubits))
    return "\n".join(lines)


def _deterministic_history_edit(
    prompt: str,
    history: list[dict[str, str]],
    intent_context: str,
) -> str | None:
    """Apply an unambiguous GHZ resize through L1 instead of asking the model to guess."""
    requested = _requested_qubits(prompt)
    if requested is None or requested < 2 or requested > 20:
        return None
    if not re.search(r"改成|换成|增加到|扩展到|change|expand|make", prompt, re.I):
        return None
    prior_qasm = _latest_history_qasm(history)
    if prior_qasm is None or not _is_ghz_family(prior_qasm):
        return None
    qasm = _ghz_qasm(requested)
    errors = validate_intent(intent_context, qasm)
    if errors:
        raise RuntimeError("LoomQ deterministic circuit edit failed validation: " + "; ".join(errors))
    # Exercise every required target emitter before exposing the edited circuit.
    circuit = parse_qasm(qasm)
    for target in ("spinq", "originq", "braket"):
        emit_target(circuit, target)
    zeros = "0" * requested
    ones = "1" * requested
    return (
        f"LoomQ 已把当前关联实验确定性地改成 {requested} 个量子比特，并重新通过 L1 检查。"
        f"电路会测量全部量子比特；理想模拟器中，结果应集中在 {zeros} 和 {ones}。\n\n"
        f"```qasm\n{qasm}\n```"
    )


def _run_agent(
    messages: list[dict[str, str]],
    intent_context: str,
    *,
    max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
) -> str:
    answer = _content(chat_completion(messages))

    for _ in range(max_repair_attempts):
        qasm, error = _validated_qasm(answer, intent_context)
        # A backend-selection or conceptual response legitimately contains no QASM
        # only when the intent validator did not require a runnable experiment.
        if error is None:
            return answer
        messages.extend(
            [
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": (
                        "The latest user instruction overrides every older number or experiment. "
                        "LATEST AUTHORITATIVE REQUIREMENTS: "
                        + _intent_contract_text(intent_context)
                        + "\nYour response failed LoomQ's deterministic syntax, intent, or prose validator: "
                        + error
                        + "\nRepair the complete response for those latest requirements. "
                        "Describe only the final circuit; do not mention obsolete alternatives. "
                        "Return the corrected program in a qasm code fence."
                    ),
                },
            ]
        )
        answer = _content(chat_completion(messages))

    _, final_error = _validated_qasm(answer, intent_context)
    if final_error:
        raise RuntimeError("LoomQ agent could not produce valid QASM: " + final_error)
    return answer


def agent_chat(prompt: str) -> str:
    """Competition contract: one stateless prompt in, one response out."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    clean_prompt = prompt.strip()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": clean_prompt},
    ]
    return _run_agent(messages, clean_prompt)


def agent_chat_with_history(prompt: str, history: list[dict[str, str]]) -> str:
    """Product-layer multi-turn chat; the formal agent_chat contract stays unchanged."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if not isinstance(history, list):
        raise ValueError("history must be a list")
    cleaned: list[dict[str, str]] = []
    for item in history[-8:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            raise ValueError("history entries must use user or assistant roles")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("history content must be non-empty text")
        cleaned.append({"role": item["role"], "content": content.strip()[:8000]})
    clean_prompt = prompt.strip()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *cleaned,
        {"role": "user", "content": clean_prompt},
    ]
    user_context = [item["content"] for item in cleaned if item["role"] == "user"]
    user_context.append(clean_prompt)
    # An explicit experiment family in the latest message starts a fresh intent
    # contract, while short answers such as "改成 4 个" inherit the recent topic.
    intent_context = clean_prompt if _intent_kind(clean_prompt) else "\n".join(user_context)
    deterministic = _deterministic_history_edit(clean_prompt, cleaned, intent_context)
    if deterministic is not None:
        return deterministic
    return _run_agent(messages, intent_context, max_repair_attempts=2)


RESULT_SYSTEM_PROMPT = """You are LoomQ's result interpreter. Explain one completed quantum
experiment using the user's language and no assumed quantum background. Ground every claim in
the supplied original question, exact QASM, backend metadata, shots, and measured counts.
Explain what the code did, whether the observed dominant states answer the original question,
what the experiment supports, and what it cannot establish. Distinguish an ideal local simulator
from real quantum hardware. Do not generate or replace QASM, do not invent counts, and do not
answer a different experiment. Return readable plain text without Markdown headings or code fences.
Be concise and concrete."""


def explain_experiment_result(
    original_prompt: str,
    qasm: str,
    result: dict[str, Any],
    *,
    agent_reply: str = "",
    follow_up: str = "",
    previous_explanation: str = "",
) -> str:
    """Use the configured model to explain an actual result in its experiment context."""
    if not isinstance(original_prompt, str) or not original_prompt.strip():
        raise ValueError("original_prompt must be a non-empty string")
    if not isinstance(qasm, str) or not qasm.strip():
        raise ValueError("qasm must be a non-empty string")
    summary = circuit_summary(qasm)
    safe_result = {
        "backend": result.get("backend"),
        "shots": result.get("shots"),
        "counts": result.get("counts"),
        "bit_order": result.get("bit_order"),
        "meta": result.get("meta"),
    }
    context = {
        "original_question": original_prompt.strip(),
        "experiment_design_explanation": agent_reply.strip()[:8000],
        "circuit_summary": summary,
        "executed_qasm": qasm.strip(),
        "actual_result": safe_result,
        "previous_result_explanation": previous_explanation.strip()[:8000],
        "current_follow_up": follow_up.strip(),
    }
    messages = [
        {"role": "system", "content": RESULT_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]
    return _content(chat_completion(messages))
