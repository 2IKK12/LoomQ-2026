"""Parser and compiler for the contest Hybrid-QASM classical subset."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

try:
    from .loomq_l1 import parse_qasm
except ImportError:
    from loomq_l1 import parse_qasm


class HybridSyntaxError(ValueError):
    """Raised when Hybrid-QASM is outside the published grammar."""


@dataclass(frozen=True)
class Value:
    kind: str
    value: int


@dataclass(frozen=True)
class Binary:
    operator: str
    left: object
    right: object


@dataclass(frozen=True)
class Assign:
    register: int
    expression: object


@dataclass(frozen=True)
class IfElse:
    operator: str
    left: object
    right: object
    then_body: tuple[object, ...]
    else_body: tuple[object, ...]


TOKEN = re.compile(
    r"\s*(?:(?P<NUMBER>\d+)|(?P<REG>r[1-9]\b)|(?P<CBIT>c\b)|"
    r"(?P<IF>if\b)|(?P<ELSE>else\b)|(?P<EQ>==)|(?P<NE>!=)|"
    r"(?P<SYMBOL>[+\-=;(){}\[\]]))",
    re.IGNORECASE,
)


def _tokens(text: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            if text[position:].strip():
                excerpt = text[position : position + 30].replace("\n", " ")
                raise HybridSyntaxError(f"unsupported classical syntax near {excerpt!r}")
            break
        kind = match.lastgroup
        assert kind is not None
        result.append((kind, match.group(kind)))
        position = match.end()
    result.append(("EOF", ""))
    return result


class ClassicalParser:
    def __init__(self, text: str):
        self.tokens = _tokens(text)
        self.position = 0

    def current(self) -> tuple[str, str]:
        return self.tokens[self.position]

    def accept(self, value: str) -> bool:
        kind, token = self.current()
        if kind == value or token == value:
            self.position += 1
            return True
        return False

    def expect(self, value: str) -> str:
        kind, token = self.current()
        if kind != value and token != value:
            raise HybridSyntaxError(f"expected {value!r}, found {token or kind!r}")
        self.position += 1
        return token

    def parse(self) -> tuple[object, ...]:
        statements = self.block(until_brace=False)
        self.expect("EOF")
        return tuple(statements)

    def block(self, *, until_brace: bool) -> list[object]:
        statements: list[object] = []
        while self.current()[0] != "EOF" and not (until_brace and self.current()[1] == "}"):
            statements.append(self.statement())
        return statements

    def statement(self) -> object:
        if self.accept("IF"):
            return self.if_statement()
        register = int(self.expect("REG")[1:])
        self.expect("=")
        expression = self.expression()
        self.expect(";")
        return Assign(register, expression)

    def if_statement(self) -> IfElse:
        self.expect("(")
        left = self.expression()
        if self.accept("EQ"):
            operator = "=="
        elif self.accept("NE"):
            operator = "!="
        else:
            raise HybridSyntaxError("if condition requires == or !=")
        right = self.expression()
        self.expect(")")
        self.expect("{")
        then_body = tuple(self.block(until_brace=True))
        self.expect("}")
        else_body: tuple[object, ...] = ()
        if self.accept("ELSE"):
            self.expect("{")
            else_body = tuple(self.block(until_brace=True))
            self.expect("}")
        return IfElse(operator, left, right, then_body, else_body)

    def expression(self) -> object:
        node = self.primary()
        while self.current()[1] in {"+", "-"}:
            operator = self.expect(self.current()[1])
            node = Binary(operator, node, self.primary())
        return node

    def primary(self) -> object:
        if self.accept("-"):
            return Binary("-", Value("integer", 0), self.primary())
        kind, token = self.current()
        if kind == "NUMBER":
            self.position += 1
            return Value("integer", int(token))
        if kind == "REG":
            self.position += 1
            return Value("register", int(token[1:]))
        if kind == "CBIT":
            self.position += 1
            self.expect("[")
            index = int(self.expect("NUMBER"))
            self.expect("]")
            if index > 21:
                raise HybridSyntaxError("c[k] supports k=0..21 for x10..x31 mapping")
            return Value("measurement", index)
        if self.accept("("):
            node = self.expression()
            self.expect(")")
            return node
        raise HybridSyntaxError(f"expected expression, found {token or kind!r}")


def _strip_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|#[^\n]*", "", source)


def _split_hybrid(source: str) -> tuple[str, list[str]]:
    clean = _strip_comments(source)
    blocks: list[str] = []
    quantum_parts: list[str] = []
    cursor = 0
    pattern = re.compile(r"\bclassical\s*\{", re.IGNORECASE)
    while True:
        match = pattern.search(clean, cursor)
        if match is None:
            quantum_parts.append(clean[cursor:])
            break
        quantum_parts.append(clean[cursor : match.start()])
        opening = clean.find("{", match.start(), match.end())
        depth = 1
        index = opening + 1
        while index < len(clean) and depth:
            if clean[index] == "{":
                depth += 1
            elif clean[index] == "}":
                depth -= 1
            index += 1
        if depth:
            raise HybridSyntaxError("unclosed classical block")
        blocks.append(clean[opening + 1 : index - 1])
        cursor = index
    if not blocks:
        raise HybridSyntaxError("Hybrid-QASM requires at least one classical block")
    return "".join(quantum_parts), blocks


def _quantum_operations(qasm: str) -> list[str]:
    parse_qasm(qasm)  # Reuse the L1 whitelist, register, arity, and measurement validation.
    operations: list[str] = []
    for raw in qasm.split(";"):
        statement = " ".join(raw.split())
        lowered = statement.lower()
        if not statement or lowered.startswith(("openqasm", "include", "qreg", "creg", "barrier")):
            continue
        operations.append(statement + ";")
    return operations


class AssemblyCompiler:
    def __init__(self):
        self.lines: list[str] = []
        self.free_temporaries = list(range(31, 19, -1))
        self.label_counter = 0

    def temporary(self) -> int:
        if not self.free_temporaries:
            raise HybridSyntaxError("expression requires more than 12 temporary registers")
        return self.free_temporaries.pop()

    def release(self, register: int) -> None:
        if 20 <= register <= 31 and register not in self.free_temporaries:
            self.free_temporaries.append(register)

    def label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"LQ_{prefix}_{self.label_counter}"

    def expression(self, node: object) -> tuple[int, bool]:
        if isinstance(node, Value):
            if node.kind == "register":
                return node.value, False
            if node.kind == "measurement":
                return 10 + node.value, False
            register = self.temporary()
            self.lines.append(f"li x{register}, {node.value}")
            return register, True
        if not isinstance(node, Binary):
            raise HybridSyntaxError("invalid expression node")
        left, left_temp = self.expression(node.left)
        right, right_temp = self.expression(node.right)
        destination = self.temporary()
        instruction = "add" if node.operator == "+" else "sub"
        self.lines.append(f"{instruction} x{destination}, x{left}, x{right}")
        if left_temp:
            self.release(left)
        if right_temp:
            self.release(right)
        return destination, True

    def statements(self, statements: Iterable[object]) -> None:
        for statement in statements:
            if isinstance(statement, Assign):
                source, temporary = self.expression(statement.expression)
                self.lines.append(f"addi x{statement.register}, x{source}, 0")
                if temporary:
                    self.release(source)
                continue
            if not isinstance(statement, IfElse):
                raise HybridSyntaxError("invalid statement node")
            left, left_temp = self.expression(statement.left)
            right, right_temp = self.expression(statement.right)
            else_label = self.label("ELSE")
            end_label = self.label("END")
            branch = "bne" if statement.operator == "==" else "beq"
            self.lines.append(f"{branch} x{left}, x{right}, {else_label}")
            if left_temp:
                self.release(left)
            if right_temp:
                self.release(right)
            self.statements(statement.then_body)
            self.lines.append(f"j {end_label}")
            self.lines.append(f"{else_label}:")
            self.statements(statement.else_body)
            self.lines.append(f"{end_label}:")


def compile_hybrid(source: str) -> tuple[list[str], str]:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("hybrid_qasm_str must be a non-empty string")
    quantum_source, classical_blocks = _split_hybrid(source)
    quantum_operations = _quantum_operations(quantum_source)
    compiler = AssemblyCompiler()
    for block in classical_blocks:
        compiler.statements(ClassicalParser(block).parse())
    if not compiler.lines:
        raise HybridSyntaxError("classical block must contain executable statements")
    return quantum_operations, "\n".join(compiler.lines) + "\n"
