#!/usr/bin/env python3
"""
Unified SageMath/SymPy bridge for SageMathUI.

JSON stdin/stdout daemon — reads one JSON object per line, writes one JSON response per line.
Tries SageMath first; falls back to SymPy if SageMath is unavailable.

Supported operations: solve, differentiate, integrate, simplify, factor, expand, limit, evaluate.
"""

import json
import sys
import re
import traceback

# ── Platform-specific timeout ────────────────────────────────────────────────

_HAS_SIGALRM = False
try:
    import signal

    if hasattr(signal, "SIGALRM"):
        _HAS_SIGALRM = True
except ImportError:
    pass

if _HAS_SIGALRM:
    from contextlib import contextmanager

    class ComputationTimeout(Exception):
        pass

    @contextmanager
    def computation_timeout(seconds=30):
        def _handler(signum, frame):
            raise ComputationTimeout(f"Computation timed out after {seconds} seconds")

        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
else:
    from contextlib import contextmanager

    @contextmanager
    def computation_timeout(seconds=30):
        # No SIGALRM on Android — Rust handles timeout
        yield

# ── Backend detection ────────────────────────────────────────────────────────

SAGE_AVAILABLE = False
SAGE_IMPORT_ERROR = None
SYMPY_AVAILABLE = False
SYMPY_IMPORT_ERROR = None

# Try SageMath first
try:
    sage_all = __import__("sage.all", fromlist=["*"])
    SAGE_AVAILABLE = True
except Exception as e:
    SAGE_IMPORT_ERROR = str(e)

# Always try SymPy too (used as fallback, or when SageMath is present but SymPy is also available)
try:
    import sympy
    from sympy import (
        Symbol,
        symbols,
        Eq,
        solve,
        diff,
        integrate,
        simplify,
        factor,
        expand,
        limit,
        summation,
        N,
        latex as sympy_latex,
        sympify,
        oo,
        I,
        pi,
        E,
        sin,
        cos,
        tan,
        cot,
        sec,
        csc,
        exp,
        log,
        sqrt,
        Abs,
        S,
        sinh,
        cosh,
        tanh,
        asin,
        acos,
        atan,
        Matrix,
    )

    SYMPY_AVAILABLE = True
except Exception as e:
    SYMPY_IMPORT_ERROR = str(e)

# Build SymPy locals dict for sympify() — only needed if SymPy is available
_SYMPY_LOCALS = {}
if SYMPY_AVAILABLE:
    for _vname in "abcdefghijklmnopqrstuvwxyz":
        _SYMPY_LOCALS[_vname] = Symbol(_vname)
    _SYMPY_LOCALS.update(
        {
            "pi": pi,
            "e": E,
            "E": E,
            "I": I,
            "oo": oo,
            "sin": sin,
            "cos": cos,
            "tan": tan,
            "cot": cot,
            "sec": sec,
            "csc": csc,
            "exp": exp,
            "log": log,
            "ln": log,
            "sqrt": sqrt,
            "abs": Abs,
            "Abs": Abs,
            "sinh": sinh,
            "cosh": cosh,
            "tanh": tanh,
            "arcsin": asin,
            "arccos": acos,
            "arctan": atan,
            "Matrix": Matrix,
        }
    )

# Determine primary backend
BACKEND = "sage" if SAGE_AVAILABLE else ("sympy" if SYMPY_AVAILABLE else "none")

# ── Backend helpers ──────────────────────────────────────────────────────────


def _get_var(name="x"):
    """Get a symbolic variable."""
    if SAGE_AVAILABLE:
        return sage_all.var(name)
    return _SYMPY_LOCALS.get(name, Symbol(name))


_CAS_FN_CALLS = (
    "integrate(",
    "integral(",
    "diff(",
    "limit(",
    "Sum(",
    "matrix(",
    "Matrix(",
)


def _to_expr(s):
    """Parse a string into a symbolic expression."""
    if SAGE_AVAILABLE:
        # If parsed string contains CAS function calls (integrate, diff, etc.),
        # symbolic_expression_from_string can't handle them — use eval with
        # a safe SageMath namespace instead.
        if any(fn in s for fn in _CAS_FN_CALLS):
            _ns = {"__builtins__": {}}
            for _name in [
                "integrate",
                "integral",
                "diff",
                "limit",
                "sum",
                "sin",
                "cos",
                "tan",
                "cot",
                "sec",
                "csc",
                "exp",
                "log",
                "sqrt",
                "abs",
                "pi",
                "e",
                "oo",
                "I",
                "Integer",
                "Rational",
                "sinh",
                "cosh",
                "tanh",
                "arcsin",
                "arccos",
                "arctan",
                "matrix",
            ]:
                if hasattr(sage_all, _name):
                    _ns[_name] = getattr(sage_all, _name)
            # Add single-letter symbolic variables
            for _v in "abcdefghijklmnopqrstuvwxyz":
                _ns[_v] = sage_all.var(_v)
            try:
                return eval(s, _ns)
            except Exception:
                pass
        from sage.calculus.calculus import symbolic_expression_from_string

        return symbolic_expression_from_string(s)
    return sympify(s, locals=_SYMPY_LOCALS)


def _latex_safe(expr):
    """Convert a symbolic expression to LaTeX."""
    if SAGE_AVAILABLE:
        return sage_all.latex(expr)
    return sympy_latex(expr)


# ── LaTeX parser ─────────────────────────────────────────────────────────────


_BARE_FN_NAMES = [
    "arcsin",
    "arccos",
    "arctan",
    "sinh",
    "cosh",
    "tanh",
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "log",
    "exp",
    "ln",
]
_RE_BARE_FN = re.compile(r"(" + "|".join(re.escape(fn) for fn in _BARE_FN_NAMES) + r")")
_RE_OPERATORNAME = re.compile(r"\\operatorname\{(\w+)\}")

_RE_DERIVATIVE_1 = re.compile(r"\\frac\{d\}\{d([a-zA-Z])\}\s*(.+)")
_RE_DERIVATIVE_N = re.compile(
    r"\\frac\{d\^\{?(\d+)\}?\}\{d([a-zA-Z])\^\{?\d+\}?\}\s*(.+)"
)

_RE_DEF_INTEGRAL = re.compile(
    r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.+?)\\?[,;]?\s*d([a-zA-Z])"
)
_RE_INDEF_INTEGRAL = re.compile(r"\\int\s*(.+?)\\?[,;]?\s*d([a-zA-Z])")
_RE_LIMIT = re.compile(r"\\lim_\{([a-zA-Z])\s*\\to\s*([^{}]+)\}\s*(.+)")
_RE_SUM = re.compile(r"\\sum_\{([a-zA-Z])=([^{}]+)\}\^\{([^{}]+)\}\s*(.+)")

_RE_FRAC = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_RE_SQRT_INDEXED = re.compile(r"\\sqrt\[([^\]]+)\]\{([^{}]+)\}")
_RE_SQRT = re.compile(r"\\sqrt\{([^{}]+)\}")
_RE_SUPERSCRIPT_BRACED = re.compile(r"\^\{([^{}]+)\}")
_RE_SUBSCRIPT_BRACED = re.compile(r"_\{([^{}]+)\}")

_FN_MAP = {
    r"\arcsin": "arcsin",
    r"\arccos": "arccos",
    r"\arctan": "arctan",
    r"\sinh": "sinh",
    r"\cosh": "cosh",
    r"\tanh": "tanh",
    r"\sin": "sin",
    r"\cos": "cos",
    r"\tan": "tan",
    r"\cot": "cot",
    r"\sec": "sec",
    r"\csc": "csc",
    r"\log": "log",
    r"\ln": "log",
    r"\exp": "exp",
    r"\abs": "abs",
}

_RE_NUM_TIMES_SYMBOL = re.compile(r"(\d)(pi|oo|[a-zA-Z])")
_RE_PAREN_TIMES_WORD = re.compile(r"\)\s*(\w)")
_RE_MATRIX_BLOCK = re.compile(
    r"\\begin\{([pbvBV]?)matrix\}(.+?)\\end\{[pbvBV]?matrix\}"
)
_RE_ADJACENT_MATRIX = re.compile(r"\)(matrix|Matrix)\(")
_RE_WHITESPACE = re.compile(r"\s+")
_RE_FINAL_NUM_TIMES = re.compile(r"(\d)([a-zA-Z(])")
_RE_FINAL_ADJACENT_PARENS = re.compile(r"\)\(")
_KFN_NO_SCT = (
    "integrate|integral|summation|limit|diff|sqrt|"
    "arcsin|arccos|arctan|sinh|cosh|tanh|"
    "cot|sec|csc|log|exp|abs"
)
_RE_FINAL_KNOWN_FN = re.compile(r"([a-zA-Z0-9])(" + _KFN_NO_SCT + r")\(")
_RE_FINAL_SCT_FN = re.compile(r"([a-zA-Z0-9])(?<!arc)((?:sin|cos|tan)\()")
_RE_FINAL_LETTER_PAREN = re.compile(r"(?<![a-zA-Z])([a-zA-Z])\(")


def _sqrt_to_power(radicand: str, index: str | None = None) -> str:
    """Convert sqrt forms to fractional-power syntax."""
    if index:
        return f"(({radicand})**(1/({index})))"
    return f"(({radicand})**(1/2))"


def _replace_sqrt(m: re.Match[str]) -> str:
    """Replace indexed sqrt regex matches using _sqrt_to_power()."""
    return _sqrt_to_power(m.group(2), m.group(1))


def _replace_matrix(m: re.Match[str]) -> str:
    """Convert \\begin{pmatrix}a&b\\\\c&d\\end{pmatrix} → matrix([[a,b],[c,d]]).

    For \\begin{vmatrix} (determinant notation), wraps with .det().
    """
    matrix_type = m.group(1) or ""  # 'p', 'b', 'v', 'V', 'B', or ''
    content = m.group(2)
    # Split rows by \\ (literal double-backslash row separator)
    rows = [r.strip() for r in re.split(r"\\\\", content) if r.strip()]
    matrix_rows = []
    for row in rows:
        elements = [elem.strip() for elem in row.split("&")]
        matrix_rows.append("[" + ", ".join(elements) + "]")
    result = "[" + ", ".join(matrix_rows) + "]"
    fn = "matrix" if SAGE_AVAILABLE else "Matrix"
    mat_expr = f"{fn}({result})"
    # vmatrix / Vmatrix = determinant notation
    if matrix_type in ("v", "V"):
        return f"{mat_expr}.det()"
    return mat_expr


def _normalize_bare_functions(s: str) -> str:
    """Normalize bare function names by adding a leading backslash."""
    placeholders = {}
    for i, fn in enumerate(_BARE_FN_NAMES):
        ph = f"__FN{i}__"
        placeholders[ph] = "\\" + fn
        s = s.replace("\\" + fn, ph)

    s = _RE_BARE_FN.sub(r"\\\1", s)

    for ph, original in placeholders.items():
        s = s.replace(ph, original)
    return s


def _strip_display_wrappers(s: str) -> str:
    """Remove display-only wrappers and normalize arithmetic operators."""
    for wrap in [r"\displaystyle", r"\left", r"\right", r"\!", r"\quad", r"\qquad"]:
        s = s.replace(wrap, "")
    s = s.replace(r"\cdot", "*").replace(r"\times", "*").replace(r"\div", "/")
    s = s.replace(r"\pm", "+")
    return s


def _convert_derivatives(s: str) -> str:
    """Convert LaTeX derivative fractions into diff() syntax."""
    s = _RE_DERIVATIVE_1.sub(r"diff(\2, \1)", s)
    s = _RE_DERIVATIVE_N.sub(r"diff(\3, \2, \1)", s)
    return s


def _convert_integrals(s: str) -> str:
    """Convert LaTeX integrals into backend-appropriate calls."""
    if SAGE_AVAILABLE:
        s = _RE_DEF_INTEGRAL.sub(r"integral(\3, \4, \1, \2)", s)
        s = _RE_INDEF_INTEGRAL.sub(r"integral(\1, \2)", s)
    else:
        s = _RE_DEF_INTEGRAL.sub(r"integrate(\3, (\4, \1, \2))", s)
        s = _RE_INDEF_INTEGRAL.sub(r"integrate(\1, \2)", s)
    return s


def _convert_limits(s: str) -> str:
    """Convert LaTeX limits into backend-appropriate limit() syntax."""
    if SAGE_AVAILABLE:
        return _RE_LIMIT.sub(r"limit(\3, \1=\2)", s)
    return _RE_LIMIT.sub(r"limit(\3, \1, \2)", s)


def _convert_sums(s: str) -> str:
    """Convert LaTeX summations into backend-appropriate sum calls."""
    if SAGE_AVAILABLE:
        return _RE_SUM.sub(r"sum(\4, \1, \2, \3)", s)
    return _RE_SUM.sub(r"summation(\4, (\1, \2, \3))", s)


def _strip_thin_spaces(s: str) -> str:
    """Strip thin-space markers after calculus conversions."""
    return s.replace(r"\,", "").replace(r"\;", "")


def _convert_fractions(s: str) -> str:
    """Convert nested \\frac{a}{b} forms into ((a)/(b))."""
    for _ in range(10):
        new = _RE_FRAC.sub(r"((\1)/(\2))", s)
        if new == s:
            break
        s = new
    return s


def _convert_roots(s: str) -> str:
    """Convert square roots and n-th roots to power notation."""
    s = _RE_SQRT_INDEXED.sub(_replace_sqrt, s)
    s = _RE_SQRT.sub(lambda m: _sqrt_to_power(m.group(1)), s)
    return s


def _convert_superscripts(s: str) -> str:
    """Convert LaTeX superscripts into Python exponent syntax."""
    s = _RE_SUPERSCRIPT_BRACED.sub(r"**(\1)", s)
    return s.replace("^", "**")


def _convert_subscripts(s: str) -> str:
    """Drop subscript wrappers by unwrapping _{...} to ..."""
    return _RE_SUBSCRIPT_BRACED.sub(r"\1", s)


def _convert_functions(s: str) -> str:
    """Convert LaTeX function commands, including function-power notation."""
    for tex, py in _FN_MAP.items():
        esc = re.escape(tex)
        s = re.sub(esc + r"\*\*\(([^()]*)\)\{([^{}]*)\}", py + r"(\2)**(\1)", s)
        s = re.sub(esc + r"\*\*\(([^()]*)\)\s*([a-zA-Z0-9])", py + r"(\2)**(\1)", s)
        s = re.sub(esc + r"\*\*([0-9]+)\s*([a-zA-Z0-9])", py + r"(\2)**\1", s)

    for tex, py in _FN_MAP.items():
        s = re.sub(re.escape(tex) + r"\{([^{}]*)\}", py + r"(\1)", s)
        s = re.sub(re.escape(tex) + r"\(", py + "(", s)
        s = re.sub(re.escape(tex) + r"\s*(\\[a-zA-Z]+)", py + r"(\1)", s)
        s = re.sub(re.escape(tex) + r"\s*([a-zA-Z0-9])", py + r"(\1)", s)
        s = s.replace(tex, py)
    return s


def _convert_constants(s: str) -> str:
    """Convert selected LaTeX constants into CAS-friendly names."""
    return s.replace(r"\infty", "oo").replace(r"\pi", "pi")


def _apply_implicit_multiplication(s: str) -> str:
    """Apply early implicit multiplication rules before matrix conversion."""
    s = _RE_NUM_TIMES_SYMBOL.sub(r"\1*\2", s)
    return _RE_PAREN_TIMES_WORD.sub(r")*\1", s)


def _convert_matrices(s: str) -> str:
    """Convert matrix LaTeX environments to matrix()/Matrix() expressions."""
    s = _RE_MATRIX_BLOCK.sub(_replace_matrix, s)
    return _RE_ADJACENT_MATRIX.sub(r")*\1(", s)


def _cleanup(s: str) -> str:
    """Finalize brace normalization, whitespace cleanup, and implicit multiplication."""
    s = s.replace("{", "(").replace("}", ")")
    s = _RE_WHITESPACE.sub(" ", s).strip()

    s = _RE_FINAL_NUM_TIMES.sub(r"\1*\2", s)
    s = _RE_FINAL_ADJACENT_PARENS.sub(r")*(", s)
    s = _RE_FINAL_KNOWN_FN.sub(r"\1*\2(", s)
    s = _RE_FINAL_SCT_FN.sub(r"\1*\2", s)
    s = _RE_FINAL_LETTER_PAREN.sub(r"\1*(", s)
    return s


def parse_latex_to_expr(latex_str: str) -> str:
    """Parse a LaTeX math string into a CAS-compatible expression string.

    Uses ** for exponents (works with both SageMath and SymPy).

    Processing order matters:
    0. Normalize bare function names (sin to backslash-sin) so all downstream steps work
    1. Strip display wrappers (NOT thin spaces for integrals)
    2. Derivatives (specific frac d/dx before general fractions)
    3. Integrals, Limits, Sums (need raw subscripts, superscripts for dx)
    4. Strip thin spaces
    5. General fractions, roots
    6. Superscripts, subscripts
    7. Function names (backslash-sin to sin), including function^power notation
    8. Constants (backslash-pi to pi)
    9. Implicit multiplication, cleanup
    """
    s = latex_str.strip()
    if not s:
        return ""

    # 0a. Convert \operatorname{fn} → \fn (MathLive sometimes uses this form)
    s = _RE_OPERATORNAME.sub(r"\\\1", s)

    s = _normalize_bare_functions(s)
    s = _strip_display_wrappers(s)
    s = _convert_derivatives(s)
    s = _convert_integrals(s)
    s = _convert_limits(s)
    s = _convert_sums(s)
    s = _strip_thin_spaces(s)
    s = _convert_fractions(s)
    s = _convert_roots(s)
    s = _convert_superscripts(s)
    s = _convert_subscripts(s)
    s = _convert_functions(s)
    s = _convert_constants(s)
    s = _apply_implicit_multiplication(s)
    s = _convert_matrices(s)
    s = _cleanup(s)
    return s


# ── Operation implementations ────────────────────────────────────────────────


def _op_solve(parsed, variable):
    var = _get_var(variable or "x")

    if SAGE_AVAILABLE:
        expr = _to_expr(parsed)
        if "==" in parsed:
            parts = parsed.split("==")
            lhs = _to_expr(parts[0].strip())
            rhs = _to_expr(parts[1].strip())
            expr = lhs - rhs
        elif "=" in parsed:
            parts = parsed.split("=", 1)
            lhs = _to_expr(parts[0].strip())
            rhs = _to_expr(parts[1].strip())
            expr = lhs - rhs
        solutions = sage_all.solve(expr, var)
        result_latex = _latex_safe(solutions)
        steps = [
            {"description": "Original equation", "latex": _latex_safe(expr) + " = 0"},
            {"description": f"Solve for {variable or 'x'}", "latex": result_latex},
        ]
    else:
        if "==" in parsed:
            parts = parsed.split("==")
            lhs = _to_expr(parts[0].strip())
            rhs = _to_expr(parts[1].strip())
            expr = Eq(lhs, rhs)
        elif "=" in parsed:
            parts = parsed.split("=", 1)
            lhs = _to_expr(parts[0].strip())
            rhs = _to_expr(parts[1].strip())
            expr = Eq(lhs, rhs)
        else:
            expr = _to_expr(parsed)
        solutions = solve(expr, var)
        result_latex = _latex_safe(solutions)
        steps = [
            {
                "description": "Original equation",
                "latex": _latex_safe(expr)
                + (" = 0" if not isinstance(expr, Eq) else ""),
            },
            {"description": f"Solve for {variable or 'x'}", "latex": result_latex},
        ]

    return result_latex, steps


def _op_differentiate(parsed, variable):
    var = _get_var(variable or "x")
    expr = _to_expr(parsed)
    var_name = variable or "x"

    if SAGE_AVAILABLE:
        deriv_held = sage_all.diff(expr, var, hold=True)
        result = sage_all.diff(expr, var)
        result_latex = _latex_safe(result)
        steps = [
            {"description": "Original expression", "latex": _latex_safe(expr)},
            {
                "description": f"Differentiate with respect to {var_name}",
                "latex": _latex_safe(deriv_held),
            },
            {"description": "Result", "latex": result_latex},
        ]
    else:
        result = diff(expr, var)
        result_latex = _latex_safe(result)
        steps = [
            {"description": "Original expression", "latex": _latex_safe(expr)},
            {
                "description": f"Differentiate with respect to {var_name}",
                "latex": f"\\frac{{d}}{{d{var_name}}}\\left({_latex_safe(expr)}\\right)",
            },
            {"description": "Result", "latex": result_latex},
        ]

    return result_latex, steps


def _op_integrate(parsed, variable):
    var = _get_var(variable or "x")
    expr = _to_expr(parsed)
    var_name = variable or "x"

    if SAGE_AVAILABLE:
        int_held = sage_all.integral(expr, var, hold=True)
        result = sage_all.integral(expr, var)
        result_latex = _latex_safe(result)
        steps = [
            {"description": "Original expression", "latex": _latex_safe(expr)},
            {
                "description": f"Integrate with respect to {var_name}",
                "latex": _latex_safe(int_held),
            },
            {"description": "Result", "latex": result_latex},
        ]
    else:
        result = integrate(expr, var)
        result_latex = _latex_safe(result)
        steps = [
            {"description": "Original expression", "latex": _latex_safe(expr)},
            {
                "description": f"Integrate with respect to {var_name}",
                "latex": f"\\int {_latex_safe(expr)} \\, d{var_name}",
            },
            {"description": "Result", "latex": result_latex},
        ]

    return result_latex, steps


def _op_simplify(parsed, variable):
    expr = _to_expr(parsed)

    if SAGE_AVAILABLE:
        try:
            result = expr.full_simplify()
        except (AttributeError, TypeError):
            # Matrices and other types lack full_simplify(); already evaluated
            result = expr
    else:
        result = simplify(expr)

    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": _latex_safe(expr)},
        {"description": "Simplify", "latex": result_latex},
    ]
    return result_latex, steps


def _op_factor(parsed, variable):
    expr = _to_expr(parsed)

    if SAGE_AVAILABLE:
        result = sage_all.factor(expr)
    else:
        result = factor(expr)

    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": _latex_safe(expr)},
        {"description": "Factor", "latex": result_latex},
    ]
    return result_latex, steps


def _op_expand(parsed, variable):
    expr = _to_expr(parsed)

    if SAGE_AVAILABLE:
        result = sage_all.expand(expr)
    else:
        result = expand(expr)

    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": _latex_safe(expr)},
        {"description": "Expand", "latex": result_latex},
    ]
    return result_latex, steps


def _op_limit(parsed, variable):
    var = _get_var(variable or "x")
    expr = _to_expr(parsed)
    var_name = variable or "x"

    # Limit has a special parsed form from the LaTeX parser, but if a plain
    # expression is passed we default to x→0
    if SAGE_AVAILABLE:
        lim_held = sage_all.limit(expr, var, 0, hold=True)
        result = sage_all.limit(expr, var, 0)
        result_latex = _latex_safe(result)
        steps = [
            {"description": "Original expression", "latex": _latex_safe(expr)},
            {
                "description": f"Take limit as {var_name} → 0",
                "latex": _latex_safe(lim_held),
            },
            {"description": "Result", "latex": result_latex},
        ]
    else:
        result = limit(expr, var, 0)
        result_latex = _latex_safe(result)
        steps = [
            {"description": "Original expression", "latex": _latex_safe(expr)},
            {
                "description": f"Take limit as {var_name} → 0",
                "latex": f"\\lim_{{{var_name} \\to 0}} {_latex_safe(expr)}",
            },
            {"description": "Result", "latex": result_latex},
        ]

    return result_latex, steps


def _op_evaluate(parsed, variable):
    expr = _to_expr(parsed)

    if SAGE_AVAILABLE:
        result = sage_all.N(expr)
    else:
        result = N(expr)

    result_latex = _latex_safe(result)
    steps = [
        {"description": "Original expression", "latex": _latex_safe(expr)},
        {"description": "Numerical evaluation", "latex": result_latex},
    ]
    return result_latex, steps


# ── Operation dispatch ───────────────────────────────────────────────────────

OPERATIONS = {
    "solve": _op_solve,
    "differentiate": _op_differentiate,
    "integrate": _op_integrate,
    "simplify": _op_simplify,
    "factor": _op_factor,
    "expand": _op_expand,
    "limit": _op_limit,
    "evaluate": _op_evaluate,
}

# ── Request processing ───────────────────────────────────────────────────────


def process_request(request: dict) -> dict:
    """Process a single JSON request and return a JSON response."""
    if not SAGE_AVAILABLE and not SYMPY_AVAILABLE:
        return {
            "success": False,
            "error": "No math backend available. "
            f"SageMath: {SAGE_IMPORT_ERROR}. SymPy: {SYMPY_IMPORT_ERROR}",
            "result_latex": None,
            "steps": [],
        }

    latex_input = request.get("latex", "")
    operation = request.get("operation", "simplify")
    variable = request.get("variable")

    op_fn = OPERATIONS.get(operation)
    if op_fn is None:
        return {
            "success": False,
            "error": f"Unknown operation: {operation}",
            "result_latex": None,
            "steps": [],
        }

    try:
        parsed = parse_latex_to_expr(latex_input)
        print(
            f"[BRIDGE DEBUG] latex={latex_input!r}  op={operation}  parsed={parsed!r}",
            file=sys.stderr,
        )
        if not parsed:
            return {
                "success": False,
                "error": "Empty expression after parsing",
                "result_latex": None,
                "steps": [],
            }

        with computation_timeout(30):
            result_latex, steps = op_fn(parsed, variable)

        print(f"[BRIDGE DEBUG] result_latex={result_latex!r}", file=sys.stderr)
        return {
            "success": True,
            "result_latex": result_latex,
            "steps": steps,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "result_latex": None,
            "steps": [],
        }


# ── Main loop ────────────────────────────────────────────────────────────────


def main():
    # Report readiness
    version = None
    if SAGE_AVAILABLE:
        try:
            version = str(sage_all.version())
        except Exception:
            version = "sage-unknown"
    elif SYMPY_AVAILABLE:
        try:
            version = sympy.__version__
        except Exception:
            version = "sympy-unknown"

    ready_msg = {
        "type": "ready",
        "version": version,
        "sage_available": SAGE_AVAILABLE,
        "sympy_available": SYMPY_AVAILABLE,
        "backend": BACKEND,
        "sage_import_error": SAGE_IMPORT_ERROR,
        "sympy_import_error": SYMPY_IMPORT_ERROR,
    }
    sys.stdout.write(json.dumps(ready_msg) + "\n")
    sys.stdout.flush()

    # Process requests
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = process_request(request)
        except json.JSONDecodeError as e:
            response = {
                "success": False,
                "error": f"Invalid JSON: {e}",
                "result_latex": None,
                "steps": [],
            }
        except Exception as e:
            response = {
                "success": False,
                "error": f"Internal error: {traceback.format_exc()}",
                "result_latex": None,
                "steps": [],
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
