import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import sage_bridge


def _parse(latex: str) -> str:
    return sage_bridge.parse_latex_to_expr(latex)


class TestParseLatexArithmetic:
    def test_numbers_add_subtract(self):
        assert _parse("1+2") == "1+2"
        assert _parse("7-3") == "7-3"

    def test_mul_div_pm(self):
        assert _parse(r"2\cdot3") == "2*3"
        assert _parse(r"2\times3") == "2*3"
        assert _parse(r"8\div2") == "8/2"
        assert _parse(r"x\pm y") == "x+ y"

    def test_fraction_and_nested_fraction(self):
        assert _parse(r"\frac{a}{b}") == "((a)/(b))"
        assert _parse(r"\frac{1}{\frac{2}{3}}") == "((1)/(((2)/(3))))"


class TestParseLatexPowers:
    def test_braced_and_unbraced(self):
        assert _parse(r"x^{2}") == "x**(2)"
        assert _parse(r"x^2") == "x**2"

    def test_negative_and_symbolic_exponents(self):
        assert _parse(r"x^{-1}") == "x**(-1)"
        assert _parse(r"x^{2+n}") == "x**(2+n)"


class TestParseLatexFunctions:
    def test_trig_and_log_forms(self):
        assert _parse(r"\sin{x}") == "sin(x)"
        assert _parse(r"\sin(x)") == "sin(x)"
        assert _parse(r"\sin x") == "sin(x)"
        assert _parse(r"\ln x") == "log(x)"
        assert _parse(r"\exp x") == "exp(x)"

    def test_function_power_notation(self):
        assert _parse(r"\sin^{2}x") == "sin(x)**(2)"
        assert _parse(r"\cos^2 x") == "cos(x)**2"

    def test_inverse_hyperbolic_operatorname_and_bare(self):
        assert _parse(r"\arcsin x") == "arcsin(x)"
        assert _parse(r"\sinh x") == "sinh(x)"
        assert _parse(r"\operatorname{sin}(x)") == "sin(x)"
        assert _parse(r"sin(x)") == "sin(x)"


class TestParseLatexConstants:
    def test_constants(self):
        assert _parse(r"\pi") == "pi"
        assert _parse(r"\infty") == "oo"
        assert _parse("e") == "e"

    def test_constant_implicit_mult(self):
        assert _parse(r"2\pi") == "2*pi"
        assert _parse("3e") == "3*e"


class TestParseLatexRoots:
    def test_sqrt_and_nth_root(self):
        assert _parse(r"\sqrt{x}") == "((x)**(1/2))"
        assert _parse(r"\sqrt[3]{x}") == "((x)**(1/(3)))"

    def test_sqrt_with_expression(self):
        assert _parse(r"\sqrt{x^2+1}") == "((x**2+1)**(1/2))"


class TestParseLatexCalculus:
    def test_integrals(self):
        if sage_bridge.BACKEND == "sage":
            assert _parse(r"\int x\,dx") == "integral(x, x)"
            assert _parse(r"\int_{0}^{1} x\,dx") == "integral(x, x, 0, 1)"
        else:
            assert _parse(r"\int x\,dx") == "integrate(x, x)"
            assert _parse(r"\int_{0}^{1} x\,dx") == "integrate(x, (x, 0, 1))"

    def test_derivatives_limit_and_sum(self):
        assert _parse(r"\frac{d}{dx}x^2") == "diff(x**2, x)"
        assert _parse(r"\frac{d^{2}}{dx^{2}}x^3") == "diff(x**3, x, 2)"
        if sage_bridge.BACKEND == "sage":
            assert (
                _parse(r"\lim_{x \to 0} \frac{\sin x}{x}")
                == "limit(((sin(x))/(x)), x=0)"
            )
            assert _parse(r"\sum_{i=1}^{n} i") == "sum(i, i, 1, n)"
        else:
            assert (
                _parse(r"\lim_{x \to 0} \frac{\sin x}{x}")
                == "limit(((sin(x))/(x)), x, 0)"
            )
            assert _parse(r"\sum_{i=1}^{n} i") == "summation(i, (i, 1, n))"


class TestParseLatexMatrices:
    def test_matrix_forms(self):
        fn = "matrix" if sage_bridge.SAGE_AVAILABLE else "Matrix"
        assert (
            _parse(r"\begin{pmatrix}a&b\\c&d\end{pmatrix}") == f"{fn}([[a, b], [c, d]])"
        )
        assert (
            _parse(r"\begin{bmatrix}a&b\\c&d\end{bmatrix}") == f"{fn}([[a, b], [c, d]])"
        )
        assert (
            _parse(r"\begin{vmatrix}a&b\\c&d\end{vmatrix}")
            == f"{fn}([[a, b], [c, d]]).det()"
        )


class TestParseLatexImplicitMult:
    def test_common_implicit_multiplication(self):
        assert _parse("2x") == "2*x"
        assert _parse(r"2\pi") == "2*pi"
        assert _parse(r"(x)(y)") == "(x)*(y)"
        assert _parse(r"x\sin(x)") == "x*sin(x)"
        assert _parse(r"2\cos(x)") == "2*cos(x)"

    def test_function_after_variable(self):
        assert _parse(r"xsin(x)") == "x*sin(x)"


class TestParseLatexDisplayWrappers:
    def test_display_wrappers_removed(self):
        assert _parse(r"\displaystyle x") == "x"
        assert _parse(r"\left(x+1\right)") == "(x+1)"
        assert _parse(r"x\quad+\qquad y") == "x+ y"


class TestParseLatexEdgeCases:
    def test_empty_and_whitespace(self):
        assert _parse("") == ""
        assert _parse("   \t\n") == ""

    def test_single_tokens(self):
        assert _parse("7") == "7"
        assert _parse("x") == "x"

    def test_deeply_nested_fractions(self):
        s = "x"
        for _ in range(10):
            s = rf"\frac{{1}}{{{s}}}"
        parsed = _parse(s)
        assert "\\frac" not in parsed
        assert "((1)/(" in parsed


class TestParseLatexBugFixes:
    def test_div_basic(self):
        parsed = _parse(r"8\div2")
        assert parsed == "8/2"
        assert r"\div" not in parsed

    def test_specific_div_regression_expression(self):
        latex = r"1.13\times10^{-3}\times8.85\times10^{-12}\div2\div(10^{-12})"
        parsed = _parse(latex)
        assert r"\div" not in parsed
        assert "/2/" in parsed

    def test_operatorname_regression(self):
        assert _parse(r"\operatorname{sin}(x)") == "sin(x)"


class TestProcessRequest:
    def test_simplify(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request({"latex": "x+x", "operation": "simplify"})
        assert resp["success"] is True
        assert resp["result_latex"]

    def test_solve(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request({"latex": r"x^{2}-1", "operation": "solve"})
        assert resp["success"] is True
        assert resp["result_latex"]

    def test_differentiate(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request(
            {"latex": r"x^{2}", "operation": "differentiate"}
        )
        assert resp["success"] is True
        assert "2" in resp["result_latex"]

    def test_integrate(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request({"latex": r"2x", "operation": "integrate"})
        assert resp["success"] is True
        assert resp["result_latex"]

    def test_factor(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request({"latex": r"x^{2}-1", "operation": "factor"})
        assert resp["success"] is True
        assert resp["result_latex"]

    def test_expand(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request(
            {"latex": r"\left(x+1\right)\left(x-1\right)", "operation": "expand"}
        )
        assert resp["success"] is True
        assert resp["result_latex"]

    def test_evaluate(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request(
            {"latex": r"\sqrt{2}", "operation": "evaluate"}
        )
        assert resp["success"] is True
        assert "1.41" in resp["result_latex"]

    def test_unknown_operation_error(self):
        resp = sage_bridge.process_request({"latex": "x", "operation": "unknown_op"})
        assert resp["success"] is False
        assert "Unknown operation" in (resp["error"] or "")

    def test_empty_expression_error(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request({"latex": "   ", "operation": "simplify"})
        assert resp["success"] is False
        assert "Empty expression" in (resp["error"] or "")

    def test_steps_shape(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        resp = sage_bridge.process_request({"latex": "x+x", "operation": "simplify"})
        assert resp["success"] is True
        assert isinstance(resp["steps"], list)
        assert resp["steps"]
        for step in resp["steps"]:
            assert "description" in step
            assert "latex" in step

    def test_specific_div_expression_succeeds(self):
        if not sage_bridge.SYMPY_AVAILABLE:
            return
        latex = r"1.13\times10^{-3}\times8.85\times10^{-12}\div2\div(10^{-12})"
        resp = sage_bridge.process_request({"latex": latex, "operation": "evaluate"})
        assert resp["success"] is True


class TestParserStages:
    def test_normalize_bare_functions(self):
        assert sage_bridge._normalize_bare_functions("sin(x)") == r"\sin(x)"
        assert sage_bridge._normalize_bare_functions(r"\sin(x)") == r"\sin(x)"
        assert sage_bridge._normalize_bare_functions("arcsin(x)") == r"\arcsin(x)"

    def test_strip_display_wrappers(self):
        out = sage_bridge._strip_display_wrappers(r"\displaystyle a\div b")
        assert r"\displaystyle" not in out
        assert r"\div" not in out
        assert "/" in out

    def test_convert_fractions(self):
        assert sage_bridge._convert_fractions(r"\frac{a}{b}") == "((a)/(b))"

    def test_convert_roots(self):
        assert sage_bridge._convert_roots(r"\sqrt{x}") == "((x)**(1/2))"
        assert sage_bridge._convert_roots(r"\sqrt[3]{x}") == "((x)**(1/(3)))"

    def test_convert_superscripts(self):
        assert sage_bridge._convert_superscripts(r"x^{2}") == "x**(2)"

    def test_convert_constants(self):
        assert sage_bridge._convert_constants(r"\infty + \pi") == "oo + pi"
