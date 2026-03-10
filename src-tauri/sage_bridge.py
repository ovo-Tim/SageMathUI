#!/usr/bin/env python3
"""
SageMath Bridge - JSON stdin/stdout daemon for math computation.
Run with: sage --python sage_bridge.py
"""

import json
import re
import signal
import sys
import traceback
from contextlib import contextmanager
from typing import Any


SAGE_AVAILABLE = True
SAGE_IMPORT_ERROR = None
sage: Any = None


def symbolic_expression_from_string(_expr):
    raise RuntimeError("SageMath is not available")


try:
    # SageMath imports
    import importlib

    sage = importlib.import_module("sage.all")
    symbolic_expression_from_string = importlib.import_module(
        "sage.calculus.calculus"
    ).symbolic_expression_from_string

    # Variable declarations for common math variables
    sage.var("x y z t n k a b c")
except Exception as import_error:  # pragma: no cover - runtime environment dependent
    SAGE_AVAILABLE = False
    SAGE_IMPORT_ERROR = str(import_error)


class ComputationTimeout(Exception):
    """Raised when a computation exceeds timeout."""


def _timeout_handler(_signum, _frame):
    raise ComputationTimeout("Computation timed out after 30 seconds")


@contextmanager
def computation_timeout(seconds=30):
    """Set per-request timeout using SIGALRM."""
    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _extract_braced(text, start_index):
    """Extract {...} content starting at text[start_index] == '{'."""
    if start_index >= len(text) or text[start_index] != "{":
        return None, start_index

    depth = 0
    i = start_index
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_index + 1 : i], i + 1
        i += 1
    return None, start_index


def _replace_frac(text):
    """Replace \frac{a}{b} with ((a)/(b)), supporting nested braces."""
    i = 0
    out = []
    while i < len(text):
        if text.startswith(r"\frac", i):
            j = i + 5
            while j < len(text) and text[j].isspace():
                j += 1
            num, j2 = _extract_braced(text, j)
            if num is None:
                out.append(text[i])
                i += 1
                continue
            while j2 < len(text) and text[j2].isspace():
                j2 += 1
            den, j3 = _extract_braced(text, j2)
            if den is None:
                out.append(text[i])
                i += 1
                continue
            out.append(f"(({num})/({den}))")
            i = j3
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _replace_sqrt(text):
    """Replace \sqrt{x} and \sqrt[n]{x}."""
    i = 0
    out = []
    while i < len(text):
        if text.startswith(r"\sqrt", i):
            j = i + 5
            while j < len(text) and text[j].isspace():
                j += 1

            idx = None
            if j < len(text) and text[j] == "[":
                k = j + 1
                while k < len(text) and text[k] != "]":
                    k += 1
                if k < len(text):
                    idx = text[j + 1 : k]
                    j = k + 1

            while j < len(text) and text[j].isspace():
                j += 1
            radicand, j2 = _extract_braced(text, j)
            if radicand is None:
                out.append(text[i])
                i += 1
                continue

            if idx:
                out.append(f"(({radicand})^(1/({idx})))")
            else:
                out.append(f"sqrt({radicand})")
            i = j2
            continue

        out.append(text[i])
        i += 1

    return "".join(out)


def parse_latex_to_sage(latex_str):
    """Convert LaTeX string to a SageMath expression string."""
    if latex_str is None:
        return ""

    s = str(latex_str).strip()
    if not s:
        return s

    # Remove common wrappers
    s = s.replace("$", "")
    s = s.replace(r"\left", "").replace(r"\right", "")

    # Operators and constants
    s = s.replace(r"\cdot", "*").replace(r"\times", "*")
    s = s.replace(r"\div", "/")
    s = s.replace(r"\pi", "pi")

    # Function names
    fn_map = {
        r"\sin": "sin",
        r"\cos": "cos",
        r"\tan": "tan",
        r"\log": "log",
        r"\ln": "ln",
    }
    for latex_name, sage_name in fn_map.items():
        s = s.replace(latex_name, sage_name)

    # Structural replacements first
    s = _replace_frac(s)
    s = _replace_sqrt(s)

    # e^{x} -> exp(x)
    s = re.sub(r"\be\^\{([^{}]+)\}", r"exp(\1)", s)

    # x^{2} -> x^(2)
    s = re.sub(r"([A-Za-z0-9\)\]])\^\{([^{}]+)\}", r"\1^(\2)", s)
    s = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", s)

    # x_1 or x_{1} -> x1 (basic handling for common index style)
    s = re.sub(r"([A-Za-z])_\{([^{}]+)\}", r"\1\2", s)
    s = re.sub(r"([A-Za-z])_([A-Za-z0-9]+)", r"\1\2", s)

    # Definite and indefinite integrals
    s = re.sub(
        r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.*?)\s*d([A-Za-z])\b",
        r"integral(\3, \4, \1, \2)",
        s,
    )
    s = re.sub(r"\\int\s*(.*?)\s*d([A-Za-z])\b", r"integral(\1, \2)", s)

    # Limits: \lim_{x \to a} expr -> limit(expr, x=a)
    s = re.sub(
        r"\\lim_\{\s*([A-Za-z])\s*\\to\s*([^{}]+)\}\s*(.*)",
        r"limit(\3, \1=\2)",
        s,
    )

    # Sums: \sum_{i=a}^{b} expr -> sum(expr, i, a, b)
    s = re.sub(
        r"\\sum_\{\s*([A-Za-z])\s*=\s*([^{}]+)\}\^\{([^{}]+)\}\s*(.*)",
        r"sum(\4, \1, \2, \3)",
        s,
    )

    # Curly braces to parentheses for easier parsing
    s = s.replace("{", "(").replace("}", ")")

    # Whitespace normalization
    s = re.sub(r"\s+", " ", s).strip()

    # Wrap unparenthesized function arguments for trig/log functions
    _MATH_FUNCS = ["sin", "cos", "tan", "cot", "sec", "csc", "log", "ln"]
    for _fn in _MATH_FUNCS:
        # Case 1: func + space(s) + arg not starting with paren
        # e.g. "sin 2pi" -> "sin(2pi)", "cos 0" -> "cos(0)"
        s = re.sub(rf"\b{_fn}\s+(?!\()(-?[^\s+\-=,)]+)", rf"{_fn}(\1)", s)
        # Case 2: func directly followed by digit-starting arg (no space)
        # e.g. "sin2pi" -> "sin(2pi)"
        s = re.sub(rf"\b{_fn}(?!\()(\d[\w.*^]*)", rf"{_fn}(\1)", s)

    # Case 3: func directly followed by known variable/constant (no space)
    # e.g. "sinpi" -> "sin(pi)", "cosx" -> "cos(x)"
    _KNOWN_NAMES = ["pi", "x", "y", "z", "t", "n", "k", "a", "b", "c"]
    for _fn in _MATH_FUNCS:
        for _name in _KNOWN_NAMES:
            s = re.sub(rf"\b{_fn}{_name}\b", rf"{_fn}({_name})", s)

    # Implicit multiplication: 2pi -> 2*pi, 3x -> 3*x
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)

    return s


def _require_sage():
    if not SAGE_AVAILABLE:
        raise RuntimeError(f"SageMath import failed: {SAGE_IMPORT_ERROR}")


def _var_or_default(variable_name):
    name = (variable_name or "x").strip() or "x"
    try:
        return sage.var(name)
    except Exception:
        return sage.var("x")


def _to_expr(expr_str):
    parsed = parse_latex_to_sage(expr_str)
    return symbolic_expression_from_string(parsed)


def _latex_safe(obj):
    try:
        return sage.latex(obj)
    except Exception:
        return str(obj)


def solve_expression(expr_str, variable="x"):
    """Solve an equation or expression."""
    _require_sage()
    var_obj = _var_or_default(variable)
    parsed = parse_latex_to_sage(expr_str)

    if "=" in parsed:
        lhs_str, rhs_str = parsed.split("=", 1)
        lhs = symbolic_expression_from_string(lhs_str.strip())
        rhs = symbolic_expression_from_string(rhs_str.strip())
        equation = lhs == rhs
    else:
        expr = symbolic_expression_from_string(parsed)
        equation = expr == 0

    solutions = sage.solve(equation, var_obj)
    result_latex = _latex_safe(solutions)

    steps = [
        {"description": "Original equation", "latex": expr_str},
        {
            "description": f"Rewritten for solving in {var_obj}",
            "latex": _latex_safe(equation),
        },
        {"description": f"Solution for {var_obj}", "latex": result_latex},
    ]
    return result_latex, steps


def differentiate_expression(expr_str, variable="x"):
    """Differentiate an expression."""
    _require_sage()
    var_obj = _var_or_default(variable)
    expr = _to_expr(expr_str)
    result = sage.diff(expr, var_obj)
    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": expr_str},
        {
            "description": "Applied differentiation rules",
            "latex": _latex_safe(sage.diff(expr, var_obj, hold=True)),
        },
        {"description": "Derivative result", "latex": result_latex},
    ]
    return result_latex, steps


def integrate_expression(expr_str, variable="x"):
    """Integrate an expression."""
    _require_sage()
    var_obj = _var_or_default(variable)
    expr = _to_expr(expr_str)
    result = sage.integral(expr, var_obj)
    result_latex = f"{_latex_safe(result)} + C"
    steps = [
        {"description": "Original expression", "latex": expr_str},
        {
            "description": "Applied symbolic integration technique",
            "latex": _latex_safe(sage.integral(expr, var_obj, hold=True)),
        },
        {"description": "Antiderivative result", "latex": result_latex},
    ]
    return result_latex, steps


def simplify_expression(expr_str):
    """Simplify an expression."""
    _require_sage()
    expr = _to_expr(expr_str)
    result = expr.full_simplify()
    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": expr_str},
        {"description": "Applied simplification", "latex": result_latex},
    ]
    return result_latex, steps


def factor_expression(expr_str):
    """Factor a polynomial."""
    _require_sage()
    expr = _to_expr(expr_str)
    result = sage.factor(expr)
    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": expr_str},
        {"description": "Factored polynomial", "latex": result_latex},
    ]
    return result_latex, steps


def expand_expression(expr_str):
    """Expand an expression."""
    _require_sage()
    expr = _to_expr(expr_str)
    result = sage.expand(expr)
    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": expr_str},
        {"description": "Expanded form", "latex": result_latex},
    ]
    return result_latex, steps


def limit_expression(expr_str, variable="x", point="0"):
    """Compute a limit."""
    _require_sage()
    var_obj = _var_or_default(variable)
    expr = _to_expr(expr_str)
    parsed_point = parse_latex_to_sage(point)

    if parsed_point in {"inf", "infty", "infinity", r"\infty", "oo"}:
        point_obj = sage.oo
    elif parsed_point in {"-inf", "-infty", "-infinity", "-oo"}:
        point_obj = -sage.oo
    else:
        point_obj = symbolic_expression_from_string(parsed_point)

    result = sage.limit(expr, var_obj, point_obj)
    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original limit expression", "latex": expr_str},
        {
            "description": f"Evaluate as {var_obj} approaches {point_obj}",
            "latex": _latex_safe(sage.limit(expr, var_obj, point_obj, hold=True)),
        },
        {"description": "Limit result", "latex": result_latex},
    ]
    return result_latex, steps


def evaluate_expression(expr_str):
    """Evaluate numerically."""
    _require_sage()
    expr = _to_expr(expr_str)
    result = sage.N(expr)
    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": expr_str},
        {"description": "Numerical evaluation", "latex": result_latex},
    ]
    return result_latex, steps


def process_request(request):
    """Process a single JSON request and return a response."""
    operation = str(request.get("operation", "solve")).strip().lower()
    latex_input = request.get("latex", "")
    variable = request.get("variable", "x")
    point = request.get("point", "0")

    if not latex_input:
        return {
            "success": False,
            "result_latex": "",
            "steps": [],
            "error": "Missing 'latex' input",
        }

    dispatch = {
        "solve": lambda: solve_expression(latex_input, variable),
        "differentiate": lambda: differentiate_expression(latex_input, variable),
        "integrate": lambda: integrate_expression(latex_input, variable),
        "simplify": lambda: simplify_expression(latex_input),
        "factor": lambda: factor_expression(latex_input),
        "expand": lambda: expand_expression(latex_input),
        "limit": lambda: limit_expression(latex_input, variable, point),
        "evaluate": lambda: evaluate_expression(latex_input),
    }

    if operation not in dispatch:
        return {
            "success": False,
            "result_latex": "",
            "steps": [],
            "error": f"Unsupported operation: {operation}",
        }

    try:
        with computation_timeout(30):
            result_latex, steps = dispatch[operation]()
        return {
            "success": True,
            "result_latex": result_latex,
            "steps": steps,
            "error": None,
        }
    except ComputationTimeout as timeout_error:
        return {
            "success": False,
            "result_latex": "",
            "steps": [],
            "error": str(timeout_error),
        }
    except Exception as op_error:
        return {
            "success": False,
            "result_latex": "",
            "steps": [],
            "error": str(op_error),
        }


def main():
    """Main daemon loop - reads JSON from stdin, writes JSON to stdout."""
    response = {
        "type": "ready",
        "version": "0.1.0",
        "sage_available": SAGE_AVAILABLE,
        "sage_import_error": None if SAGE_AVAILABLE else SAGE_IMPORT_ERROR,
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = process_request(request)
        except json.JSONDecodeError as json_error:
            response = {
                "success": False,
                "result_latex": "",
                "steps": [],
                "error": f"Invalid JSON: {json_error}",
            }
        except Exception as unknown_error:
            response = {
                "success": False,
                "result_latex": "",
                "steps": [],
                "error": str(unknown_error),
                "traceback": traceback.format_exc(),
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
