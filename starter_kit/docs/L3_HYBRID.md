# LoomQ L3 Hybrid-QASM Compiler

## Contract

`adapter.compile_hybrid(source)` returns `(quantum_operations, assembly)`.
The implementation is a real parser and compiler for the published grammar; it
does not identify public examples or return precomputed branches.

## Pipeline

```text
Hybrid-QASM
    |
    +-- remove comments and locate balanced classical { ... } blocks
    |       |
    |       v
    |   lexer -> recursive-descent parser -> typed AST
    |       |
    |       v
    |   RISC-V code generator (li/add/sub/addi/beq/bne/j)
    |
    +-- remaining OpenQASM -> L1 parser and 12-gate validation
            |
            v
        ordered gate/measurement strings
```

The classical AST supports sequential assignments, integer and negative
literals, `r1..r9`, measurement values `c[k]`, left-associative `+` and `-`,
`==`, `!=`, nested `if/else`, and multiple classical blocks. Classical
registers map to `x1..x9`; measurement bits map to `x10, x11, ...`; expression
temporaries use `x20..x31`. Labels are generated uniquely for every branch.

The quantum side is not accepted as arbitrary text: after classical blocks are
removed, the existing L1 parser checks declarations, indices, gate arity,
measurements, parameter expressions, and the contest 12-gate whitelist.

## Verification

From the fork root:

```bash
python3 -m unittest tests.test_l3 -v
cd starter_kit
python3 evaluator.py --level l3
```

The tests exhaust all injected measurement combinations for nested two-bit
branches and cover arithmetic conditions, negative constants, sequential and
self assignments, multiple classical blocks, quantum-operation ordering, and
invalid syntax.
