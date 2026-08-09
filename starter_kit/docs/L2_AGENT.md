# LoomQ L2 Agent

## Audience

LoomQ is designed for students, teachers, and cross-disciplinary creators who
have an experiment in mind but do not know quantum-computing syntax. The agent
responds in the user's language and turns intent into an executable circuit,
instead of requiring the user to learn platform-specific SDKs first.

## Runtime contract

The agent uses the competition's OpenAI-compatible environment contract:

```text
LOOMQ_LLM_BASE_URL
LOOMQ_LLM_API_KEY
LOOMQ_LLM_MODEL
LOOMQ_LLM_TIMEOUT_SECONDS
```

No URL, credential, or model name is stored in the repository. Formal judging
injects `deepseek-v4-flash`; local development may use another compatible model.

## Closed loop

```text
user request
    |
    v
LLM with QASM rules + official backend records
    |
    +-- backend recommendation -> exact canonical backend id
    |
    +-- QASM response -> extract -> L1 syntax + target emit validation
                                      |
                                      v
                           deterministic intent validation
                     (qubits / Bell / GHZ-cat / phase / rotation /
                       randomness / SWAP / Toffoli / measurement)
                                      |
                                      +-- valid -> return to user
                                      +-- mismatch -> send exact error to LLM
                                                     -> validate repaired QASM
                                      |
                                      v
                             run actual local shots
                                      |
                                      v
                    original question + exact QASM + counts
                                      |
                                      v
                       grounded result explanation / follow-up
```

The formal `agent_chat(prompt)` entry point remains stateless exactly as the
competition contract requires. The local web product uses a separate
`agent_chat_with_history` layer with at most eight recent user/assistant
messages. Short replies and pronouns can therefore continue the active topic;
the latest explicit topic wins, and choosing a new experiment clears history.
System-role messages from browser input are rejected.

The capability records come directly from `backend_capabilities.json`. This
allows the model to filter unseen combinations of qubit count, queue, cost,
hardware type, and account requirements without memorizing the public examples.

## Local configuration

Set variables in the shell that launches the test. Never paste a key into a
source file, screenshot, issue, or Git commit.

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<YOUR_OWN_KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
export LOOMQ_LLM_TIMEOUT_SECONDS=120
python3 evaluator.py --level l2
```

## Tests

Offline tests mock only the model response, not the L1 validator:

```bash
python3 -m unittest tests.test_l2_agent -v
```

They cover valid generation, validator-driven repair, capability-record
grounding, non-QASM backend replies, and malformed API responses. The official
transport-contract tests separately exercise a real local HTTP endpoint.

With real model environment variables configured, run the entrant smoke suite:

```bash
python3 l2_smoke_test.py
```

It covers a four-qubit Schrödinger-cat closed loop, a four-qubit GHZ variant,
broken Bell code, and three backend-constraint combinations. The cat case makes
an additional model call after execution and checks that the explanation names
an actually observed dominant state. Generated circuits are executed by L1 and
checked for semantic fidelity rather than accepted on syntax alone.
