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


def _replace_sqrt(m):
    """Replace \\sqrt[n]{...} or \\sqrt{...} with (expr)**(1/n) or (expr)**(1/2)."""
    idx = m.group(1)
    radicand = m.group(2)
    if idx:
        return f"(({radicand})**(1/({idx})))"
    return f"(({radicand})**(1/2))"


def _replace_matrix(m):
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


def parse_latex_to_expr(latex_str):
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

    # 0. Normalize bare function names: sin → \sin, cos → \cos, etc.
    #    MathLive sometimes outputs bare names without backslash.
    #    Sorted longest-first so "sinh" matches before "sin", "arcsin" before "sin".
    _BARE_FN_NAMES = sorted(
        [
            "sinh",
            "cosh",
            "tanh",
            "arcsin",
            "arccos",
            "arctan",
            "sin",
            "cos",
            "tan",
            "cot",
            "sec",
            "csc",
            "log",
            "exp",
            "ln",
        ],
        key=len,
        reverse=True,
    )
    _BARE_FN_PAT = "|".join(re.escape(fn) for fn in _BARE_FN_NAMES)

    # First, protect existing \-prefixed function names so "sin" inside "\arcsin"
    # isn't matched as a bare function. Process longest-first to avoid
    # "\arcsin" being partially replaced by "\sin" protection.
    _placeholders = {}
    for i, fn in enumerate(_BARE_FN_NAMES):
        ph = f"__FN{i}__"
        _placeholders[ph] = "\\" + fn
        s = s.replace("\\" + fn, ph)

    # Now match truly bare function names (no backslash prefix)
    s = re.sub(r"(" + _BARE_FN_PAT + r")", r"\\\1", s)

    # Restore protected names
    for ph, original in _placeholders.items():
        s = s.replace(ph, original)

    # 1. Remove display wrappers (keep \, and \; for integral dx detection)
    for wrap in [r"\displaystyle", r"\left", r"\right", r"\!", r"\quad", r"\qquad"]:
        s = s.replace(wrap, "")
    s = s.replace(r"\cdot", "*").replace(r"\times", "*")
    s = s.replace(r"\pm", "+")

    # 2. Derivatives: \frac{d}{dx} expr (BEFORE general fractions)
    s = re.sub(r"\\frac\{d\}\{d([a-zA-Z])\}\s*(.+)", r"diff(\2, \1)", s)
    s = re.sub(
        r"\\frac\{d\^\{?(\d+)\}?\}\{d([a-zA-Z])\^\{?\d+\}?\}\s*(.+)",
        r"diff(\3, \2, \1)",
        s,
    )

    # 3. Integrals (BEFORE functions — need raw \sin, \, and dx boundary)
    # Definite integral: \int_{a}^{b} expr \, dx
    if SAGE_AVAILABLE:
        s = re.sub(
            r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.+?)\\?[,;]?\s*d([a-zA-Z])",
            r"integral(\3, \4, \1, \2)",
            s,
        )
    else:
        s = re.sub(
            r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.+?)\\?[,;]?\s*d([a-zA-Z])",
            r"integrate(\3, (\4, \1, \2))",
            s,
        )
    # Indefinite integral: \int expr \, dx (allow \s* after \int)
    if SAGE_AVAILABLE:
        s = re.sub(r"\\int\s*(.+?)\\?[,;]?\s*d([a-zA-Z])", r"integral(\1, \2)", s)
    else:
        s = re.sub(r"\\int\s*(.+?)\\?[,;]?\s*d([a-zA-Z])", r"integrate(\1, \2)", s)

    # Limit: \lim_{x \to a} expr
    if SAGE_AVAILABLE:
        s = re.sub(
            r"\\lim_\{([a-zA-Z])\s*\\to\s*([^{}]+)\}\s*(.+)", r"limit(\3, \1=\2)", s
        )
    else:
        s = re.sub(
            r"\\lim_\{([a-zA-Z])\s*\\to\s*([^{}]+)\}\s*(.+)", r"limit(\3, \1, \2)", s
        )

    # Sum: \sum_{i=a}^{b} expr
    if SAGE_AVAILABLE:
        s = re.sub(
            r"\\sum_\{([a-zA-Z])=([^{}]+)\}\^\{([^{}]+)\}\s*(.+)",
            r"sum(\4, \1, \2, \3)",
            s,
        )
    else:
        s = re.sub(
            r"\\sum_\{([a-zA-Z])=([^{}]+)\}\^\{([^{}]+)\}\s*(.+)",
            r"summation(\4, (\1, \2, \3))",
            s,
        )

    # 4. Strip thin spaces (no longer needed after integral matching)
    s = s.replace(r"\,", "").replace(r"\;", "")

    # 5. General fractions: \frac{a}{b} → ((a)/(b))
    frac_re = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
    for _ in range(10):
        new = frac_re.sub(r"((\1)/(\2))", s)
        if new == s:
            break
        s = new

    # Roots: \sqrt[n]{...} and \sqrt{...}
    s = re.sub(r"\\sqrt\[([^\]]+)\]\{([^{}]+)\}", _replace_sqrt, s)
    s = re.sub(
        r"\\sqrt\{([^{}]+)\}",
        lambda m: _replace_sqrt(
            type("M", (), {"group": lambda self, i: {1: None, 2: m.group(1)}[i]})()
        ),
        s,
    )

    # 6. Superscripts: ^{...} → **(...) and bare ^ → **
    s = re.sub(r"\^\{([^{}]+)\}", r"**(\1)", s)
    s = s.replace("^", "**")

    # Subscripts: just remove _{...}
    s = re.sub(r"_\{([^{}]+)\}", r"\1", s)

    # 7. Function names — ORDERED LONGEST-FIRST so \sinh is processed before \sin
    fn_map = {
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

    # 7a. Function^power notation: \sin**{2}x → sin(x)**(2), \sin**2x → sin(x)**2
    #     By this point, ^{n} is already **(n) and ^n is already **n (step 6).
    for tex, py in fn_map.items():
        esc = re.escape(tex)
        # \sin**(n){x} or \sin**(n) x  → sin(x)**(n)
        s = re.sub(
            esc + r"\*\*\(([^()]*)\)\{([^{}]*)\}",
            py + r"(\2)**(\1)",
            s,
        )
        s = re.sub(
            esc + r"\*\*\(([^()]*)\)\s*([a-zA-Z0-9])",
            py + r"(\2)**(\1)",
            s,
        )
        # \sin**2x → sin(x)**2  (bare single-char/digit exponent)
        s = re.sub(
            esc + r"\*\*([0-9]+)\s*([a-zA-Z0-9])",
            py + r"(\2)**\1",
            s,
        )

    # 7b. Standard function processing
    for tex, py in fn_map.items():
        # \sin{...} → sin(...)
        s = re.sub(re.escape(tex) + r"\{([^{}]*)\}", py + r"(\1)", s)
        # \sin(...) → sin(...)
        s = re.sub(re.escape(tex) + r"\(", py + "(", s)
        # \sin\pi, \sin\alpha → sin(\pi), sin(\alpha) (function + LaTeX command)
        s = re.sub(re.escape(tex) + r"\s*(\\[a-zA-Z]+)", py + r"(\1)", s)
        # \sin x or \sinx → sin(x) (allow optional space — MathLive may omit it)
        s = re.sub(re.escape(tex) + r"\s*([a-zA-Z0-9])", py + r"(\1)", s)
        # bare \sin → sin
        s = s.replace(tex, py)

    # 8. Constants — AFTER function processing to avoid \sin\pi → sinpi
    s = s.replace(r"\infty", "oo")
    s = s.replace(r"\pi", "pi")

    # 9. Implicit multiplication
    s = re.sub(r"(\d)(pi|oo|[a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"\)\s*(\w)", r")*\1", s)

    # 9b. Matrices: \begin{pmatrix}...\end{pmatrix} → matrix([[...]])
    #     \begin{vmatrix}...\end{vmatrix} → matrix([[...]]).det()
    #     Must be BEFORE brace cleanup (step 10) which would destroy \begin{...}
    s = re.sub(
        r"\\begin\{([pbvBV]?)matrix\}(.+?)\\end\{[pbvBV]?matrix\}",
        _replace_matrix,
        s,
    )
    # Implicit multiplication between adjacent matrices: )matrix( → )*matrix(
    s = re.sub(r"\)(matrix|Matrix)\(", r")*\1(", s)

    # 10. Clean braces and whitespace
    s = s.replace("{", "(").replace("}", ")")
    s = re.sub(r"\s+", " ", s).strip()

    # Final implicit multiplication
    s = re.sub(r"(\d)([a-zA-Z(])", r"\1*\2", s)
    s = re.sub(r"\)\(", ")*(", s)
    # Variable/digit before KNOWN function call: xsin( → x*sin(, 2cos( → 2*cos(
    # Split sin/cos/tan out with (?<!arc) lookbehind so arcsin( doesn't become arc*sin(
    _KFN_NO_SCT = (
        "integrate|integral|summation|limit|diff|sqrt|"
        "arcsin|arccos|arctan|sinh|cosh|tanh|"
        "cot|sec|csc|log|exp|abs"
    )
    s = re.sub(r"([a-zA-Z0-9])(" + _KFN_NO_SCT + r")\(", r"\1*\2(", s)
    # sin/cos/tan: only insert * if NOT preceded by "arc"
    s = re.sub(r"([a-zA-Z0-9])(?<!arc)((?:sin|cos|tan)\()", r"\1*\2", s)
    # Single letter before ( when not part of function name: x( → x*(
    s = re.sub(r"(?<![a-zA-Z])([a-zA-Z])\(", r"\1*(", s)

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


def process_request(request):
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
