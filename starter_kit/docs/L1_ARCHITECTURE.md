# LoomQ L1 Architecture

## Goal

LoomQ accepts the competition's OpenQASM 2.0 subset once, represents it as a
backend-neutral circuit, and then routes that circuit to SpinQ, OriginQ, or AWS
Braket. The implementation does not recognize public circuit names and contains
no precomputed result tables.

## Data flow

```text
OpenQASM 2.0
      |
      v
safe lexer/parser ---- validation (registers, indices, arity, 12-gate whitelist)
      |
      v
Circuit(Operation[], Measurement[])
      |-------------------|--------------------|
      v                   v                    v
SpinQ QASM 2       OriginIR emitter      Braket QASM 3
      |
      v
shared local statevector executor -> normalized little-endian counts JSON
```

The parser flattens multiple source registers into deterministic global qubit and
classical-bit indices. This keeps all target emitters and result normalization on
the same bit-order contract: a counts key is `c[n-1]...c[0]` and
`bit_order` is always `little`.

## Supported operations

The complete contest whitelist is implemented:

- Single-qubit: `h`, `x`, `s`, `sdg`, `t`, `tdg`, `rz(theta)`, `ry(theta)`
- Two-qubit: `cx`, `cu1(theta)`, `swap`
- Three-qubit: `ccx`

Angle expressions are parsed with a restricted syntax supporting numeric
literals, `pi`, unary signs, and `+ - * /`. Python evaluation and function calls
are not allowed.

## Target mappings

- SpinQ: complete OpenQASM 2.0 using the contest whitelist.
- OriginQ: canonical OriginIR (`CNOT`, `CU1`, `TOFFOLI`, `SDAG`, `TDAG`).
- Braket: complete OpenQASM 3, mapping `cx` to `cnot` and `cu1` to the standard
  controlled-phase gate `cp`.

## Execution and reproducibility

`run()` uses the same parsed circuit as `transpile()`. The standard-library
statevector executor computes the exact ideal output probabilities, then draws
the requested number of independent shots from that distribution. Counts can
therefore vary between runs, as measurement samples do, while their sum remains
exactly equal to `shots`. The result metadata identifies the executor as
`loomq_statevector_v1`; it is not presented as vendor-cloud or real-hardware data.

## Verification

From the fork root:

```bash
python3 -m unittest tests.test_l1 -v
cd starter_kit
python3 evaluator.py --level l1 --target spinq,originq,braket
```

The unit suite covers all 12 gates, parameter arithmetic, comments, barriers,
multiple registers, bit order, three target syntaxes, invalid indices, invalid
shots, unsupported gates, and unsafe parameter expressions.
