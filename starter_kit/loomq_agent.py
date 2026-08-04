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

QASM rules:
- Always include OPENQASM 2.0, qelib1.inc, qreg, creg, and measurement.
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


def _validated_qasm(text: str) -> tuple[str | None, str | None]:
    qasm = extract_qasm(text)
    if qasm is None:
        return None, None
    try:
        circuit = parse_qasm(qasm)
        # Exercising every emitter catches target-specific serialization failures too.
        for target in ("spinq", "originq", "braket"):
            emit_target(circuit, target)
    except (QASMError, ValueError) as exc:
        return qasm, str(exc)
    return qasm, None


def agent_chat(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt.strip()},
    ]
    answer = _content(chat_completion(messages))

    for _ in range(MAX_REPAIR_ATTEMPTS):
        qasm, error = _validated_qasm(answer)
        # A backend-selection or conceptual response legitimately contains no QASM.
        if qasm is None or error is None:
            return answer
        messages.extend(
            [
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": (
                        "Your QASM failed LoomQ's deterministic L1 validator with this error: "
                        + error
                        + "\nRepair the complete program while preserving my original intent. "
                        "Return the corrected program in a qasm code fence."
                    ),
                },
            ]
        )
        answer = _content(chat_completion(messages))

    _, final_error = _validated_qasm(answer)
    if final_error:
        raise RuntimeError("LoomQ agent could not produce valid QASM: " + final_error)
    return answer
