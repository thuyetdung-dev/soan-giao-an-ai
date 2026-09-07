"""Restricted AST-to-SymPy parser for untrusted mathematical expressions."""
from __future__ import annotations

import ast
from typing import Any

import sympy as sp


class SafeMathError(ValueError):
    pass


DEFAULT_SYMBOLS = {name: sp.Symbol(name, real=True) for name in ("x", "t", "m", "n", "a", "b", "c")}
CONSTANTS = {"pi": sp.pi, "E": sp.E, "e": sp.E, "oo": sp.oo, "inf": sp.oo}
FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
    "sqrt": sp.sqrt, "log": sp.log, "ln": sp.log, "exp": sp.exp,
    "abs": sp.Abs, "Abs": sp.Abs,
}
BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
          ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
          ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: sp.Mod(a, b)}
UNARYOPS = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}


def _normalise(text: Any) -> str:
    value = str(text or "").strip().replace("−", "-").replace("×", "*").replace("÷", "/")
    value = value.replace("^", "**").replace("∞", "oo")
    if len(value) > 500:
        raise SafeMathError("Biểu thức dài quá giới hạn 500 ký tự.")
    if not value:
        raise SafeMathError("Biểu thức trống.")
    return value


def parse_math_expression(text: Any, symbols: dict[str, sp.Symbol] | None = None) -> sp.Expr:
    """Parse an arithmetic expression without eval/sympify on user text."""
    allowed_symbols = dict(DEFAULT_SYMBOLS)
    if symbols:
        allowed_symbols.update(symbols)
    try:
        tree = ast.parse(_normalise(text), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise SafeMathError("Biểu thức không đúng cú pháp; hãy dùng dấu * cho phép nhân.") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 160:
        raise SafeMathError("Biểu thức quá phức tạp.")

    def convert(node: ast.AST, depth: int = 0):
        if depth > 24:
            raise SafeMathError("Biểu thức lồng quá sâu.")
        if isinstance(node, ast.Expression):
            return convert(node.body, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if isinstance(node.value, int) and len(str(abs(node.value))) > 30:
                raise SafeMathError("Số nguyên quá lớn.")
            return sp.Integer(node.value) if isinstance(node.value, int) else sp.Float(node.value)
        if isinstance(node, ast.Name):
            if node.id in allowed_symbols:
                return allowed_symbols[node.id]
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
            raise SafeMathError(f"Tên '{node.id}' không được phép.")
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARYOPS:
            return UNARYOPS[type(node.op)](convert(node.operand, depth + 1))
        if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            left, right = convert(node.left, depth + 1), convert(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and right.is_number:
                try:
                    if abs(float(right)) > 100:
                        raise SafeMathError("Số mũ vượt giới hạn an toàn.")
                except (TypeError, ValueError):
                    pass
            return BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                raise SafeMathError("Hàm toán học không được hỗ trợ.")
            if node.keywords or len(node.args) not in (1, 2):
                raise SafeMathError("Số đối số của hàm không hợp lệ.")
            return FUNCTIONS[node.func.id](*[convert(arg, depth + 1) for arg in node.args])
        raise SafeMathError(f"Thành phần {type(node).__name__} không được phép.")

    try:
        result = convert(tree)
        return sp.sympify(result)  # result is already a trusted SymPy object
    except SafeMathError:
        raise
    except Exception as exc:
        raise SafeMathError("Không thể chuyển biểu thức sang dạng toán học an toàn.") from exc


def parse_numeric(text: Any) -> sp.Expr:
    result = parse_math_expression(text, symbols={})
    if result.free_symbols:
        raise SafeMathError("Giá trị số không được chứa biến.")
    return result
