from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


class ExprError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


TOKEN_RE = re.compile(
    r"""
    \s*(?:(?P<num>\d+)|(?P<id>[A-Za-z_]\w*)|(?P<op>==|!=|<=|>=|&&|\|\||[()+\-*/%!,<>]))
    """,
    re.VERBOSE,
)


def tokenize(text: str) -> list[Token]:
    pos = 0
    tokens: list[Token] = []
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ExprError(f"Token invalido cerca: {text[pos:pos+20]!r}")
        pos = m.end()
        if m.group("num"):
            tokens.append(Token("num", m.group("num")))
        elif m.group("id"):
            tokens.append(Token("id", m.group("id")))
        else:
            tokens.append(Token("op", m.group("op")))
    tokens.append(Token("eof", ""))
    return tokens


class Node:
    def eval(self, env: dict[str, int | bool], old: dict[str, int | bool], result: Any = None) -> Any:
        raise NotImplementedError

    def vars(self) -> set[str]:
        return set()


@dataclass(frozen=True)
class Number(Node):
    value: int

    def eval(self, env, old, result=None):
        return self.value


@dataclass(frozen=True)
class Bool(Node):
    value: bool

    def eval(self, env, old, result=None):
        return self.value


@dataclass(frozen=True)
class Ident(Node):
    name: str

    def eval(self, env, old, result=None):
        if self.name == "result":
            return result
        if self.name in env:
            return env[self.name]
        if self.name in old:
            return old[self.name]
        # Los identificadores desconocidos valen 0 en modo acotado, pero siguen registrados en vars().
        return 0

    def vars(self) -> set[str]:
        if self.name in {"true", "false", "result"}:
            return set()
        return {self.name}


@dataclass(frozen=True)
class Unary(Node):
    op: str
    inner: Node

    def eval(self, env, old, result=None):
        v = self.inner.eval(env, old, result)
        if self.op == "!":
            return not bool(v)
        if self.op == "-":
            return -int(v)
        raise ExprError(f"Operador unario no soportado: {self.op}")

    def vars(self) -> set[str]:
        return self.inner.vars()


@dataclass(frozen=True)
class Binary(Node):
    op: str
    left: Node
    right: Node

    def eval(self, env, old, result=None):
        a = self.left.eval(env, old, result)
        if self.op == "&&":
            return bool(a) and bool(self.right.eval(env, old, result))
        if self.op == "||":
            return bool(a) or bool(self.right.eval(env, old, result))
        b = self.right.eval(env, old, result)
        if self.op == "+":
            return int(a) + int(b)
        if self.op == "-":
            return int(a) - int(b)
        if self.op == "*":
            return int(a) * int(b)
        if self.op == "/":
            return int(a) // int(b) if int(b) != 0 else 0
        if self.op == "%":
            return int(a) % int(b) if int(b) != 0 else 0
        if self.op == "==":
            return a == b
        if self.op == "!=":
            return a != b
        if self.op == "<":
            return int(a) < int(b)
        if self.op == "<=":
            return int(a) <= int(b)
        if self.op == ">":
            return int(a) > int(b)
        if self.op == ">=":
            return int(a) >= int(b)
        raise ExprError(f"Operador binario no soportado: {self.op}")

    def vars(self) -> set[str]:
        return self.left.vars() | self.right.vars()


@dataclass(frozen=True)
class Call(Node):
    name: str
    args: tuple[Node, ...]

    def eval(self, env, old, result=None):
        if self.name == "old":
            if len(self.args) != 1:
                raise ExprError("old() espera un argumento")
            # Evalúa la expresión interna en el estado anterior.
            return self.args[0].eval(old, old, result)
        if self.name == "size":
            for candidate in ("size_", "size", "n", "n_", "_size", "count", "count_"):
                if candidate in env:
                    return env[candidate]
                if candidate in old:
                    return old[candidate]
            return 0
        if self.name == "empty":
            return self._size_value(env, old) == 0
        if self.name == "capacity":
            for candidate in ("capacity_", "capacity", "_capacity", "cap", "cap_"):
                if candidate in env:
                    return env[candidate]
                if candidate in old:
                    return old[candidate]
            return 0
        if self.name == "parent":
            return (int(self.args[0].eval(env, old, result)) - 1) // 2
        if self.name == "left":
            return 2 * int(self.args[0].eval(env, old, result)) + 1
        if self.name == "right":
            return 2 * int(self.args[0].eval(env, old, result)) + 2
        # Los predicados puros desconocidos no se prueban en modo acotado.
        return False

    def _size_value(self, env, old):
        for candidate in ("size_", "size", "n", "n_", "_size", "count", "count_"):
            if candidate in env:
                return env[candidate]
            if candidate in old:
                return old[candidate]
        return 0

    def vars(self) -> set[str]:
        out = set()
        for a in self.args:
            out |= a.vars()
        return out


class Parser:
    def __init__(self, text: str):
        self.text = normalize_expr(text)
        self.tokens = tokenize(self.text)
        self.i = 0

    def peek(self) -> Token:
        return self.tokens[self.i]

    def take(self, value: str | None = None) -> Token:
        tok = self.peek()
        if value is not None and tok.value != value:
            raise ExprError(f"Se esperaba {value!r}, se obtuvo {tok.value!r}")
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.parse_or()
        if self.peek().kind != "eof":
            raise ExprError(f"Token final inesperado: {self.peek().value}")
        return node

    def parse_or(self) -> Node:
        node = self.parse_and()
        while self.peek().value == "||":
            op = self.take().value
            node = Binary(op, node, self.parse_and())
        return node

    def parse_and(self) -> Node:
        node = self.parse_cmp()
        while self.peek().value == "&&":
            op = self.take().value
            node = Binary(op, node, self.parse_cmp())
        return node

    def parse_cmp(self) -> Node:
        node = self.parse_add()
        while self.peek().value in {"==", "!=", "<", "<=", ">", ">="}:
            op = self.take().value
            node = Binary(op, node, self.parse_add())
        return node

    def parse_add(self) -> Node:
        node = self.parse_mul()
        while self.peek().value in {"+", "-"}:
            op = self.take().value
            node = Binary(op, node, self.parse_mul())
        return node

    def parse_mul(self) -> Node:
        node = self.parse_unary()
        while self.peek().value in {"*", "/", "%"}:
            op = self.take().value
            node = Binary(op, node, self.parse_unary())
        return node

    def parse_unary(self) -> Node:
        if self.peek().value in {"!", "-"}:
            op = self.take().value
            return Unary(op, self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        tok = self.peek()
        if tok.kind == "num":
            self.take()
            return Number(int(tok.value))
        if tok.kind == "id":
            self.take()
            if tok.value == "true":
                return Bool(True)
            if tok.value == "false":
                return Bool(False)
            if self.peek().value == "(":
                self.take("(")
                args: list[Node] = []
                if self.peek().value != ")":
                    while True:
                        args.append(self.parse_or())
                        if self.peek().value == ",":
                            self.take(",")
                            continue
                        break
                self.take(")")
                return Call(tok.value, tuple(args))
            return Ident(tok.value)
        if tok.value == "(":
            self.take("(")
            node = self.parse_or()
            self.take(")")
            return node
        raise ExprError(f"Token invalido: {tok.value}")


def normalize_expr(text: str) -> str:
    text = text.strip()
    text = text.replace("this->", "")
    # Las cabeceras CC-232 suelen usar ods::array<T> a; con a.length como capacidad.
    text = re.sub(r"\b[aA]\s*\.\s*length\b", "capacity_", text)
    text = re.sub(r"\blength\(\)", "capacity()", text)
    # Modela casts comunes de C++ y static_cast<size_t>(x) como la expresión interna.
    text = re.sub(r"static_cast\s*<[^>]+>\s*\(([^()]*)\)", r"(\1)", text)
    text = text.replace("&&", " && ").replace("||", " || ")
    text = re.sub(r"\btrue\b", "true", text, flags=re.I)
    text = re.sub(r"\bfalse\b", "false", text, flags=re.I)
    return text


def parse_expr(text: str) -> Node:
    return Parser(text).parse()


def vars_in_expressions(expressions: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for e in expressions:
        try:
            out |= parse_expr(e).vars()
        except ExprError:
            pass
    return out
