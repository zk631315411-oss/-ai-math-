"""Fixed 300-case Chinese formula benchmark candidate set.

The cases are deterministic and intentionally kept in source form so changes are
reviewable in Git. A human review file is still required before promotion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FormulaCase:
    id: str
    category: str
    description: str
    expected_latex: str
    expected_display: str = "inline"


def _cross_cases(category: str, patterns: list[tuple[str, str]], suffixes: list[tuple[str, str]]) -> list[FormulaCase]:
    cases: list[FormulaCase] = []
    for pattern_index, (description_pattern, latex_pattern) in enumerate(patterns, 1):
        for suffix_index, (description_value, latex_value) in enumerate(suffixes, 1):
            cases.append(FormulaCase(
                id=f"{category}-{pattern_index:02d}-{suffix_index:02d}",
                category=category,
                description=description_pattern.format(v=description_value),
                expected_latex=latex_pattern.format(v=latex_value),
            ))
    return cases


def build_cases() -> list[FormulaCase]:
    cases: list[FormulaCase] = []
    cases += _cross_cases("fraction", [
        ("{v}除以x加1", r"\frac{{{v}}}{{x+1}}"),
        ("x加{v}整体除以y减1", r"\frac{{x+{v}}}{{y-1}}"),
        ("一除以一加{v}分之一", r"\frac{{1}}{{1+\frac{{1}}{{{v}}}}}"),
        ("{v}与x的和除以它们的差", r"\frac{{{v}+x}}{{{v}-x}}"),
        ("负的{v}分之x平方", r"-\frac{{x^2}}{{{v}}}"),
    ], [("二", "2"), ("三", "3"), ("五", "5"), ("n", "n"), ("a平方", "a^2")])
    cases += _cross_cases("radical", [
        ("根号{v}", r"\sqrt{{{v}}}"),
        ("三次根号{v}", r"\sqrt[3]{{{v}}}"),
        ("根号下x加{v}", r"\sqrt{{x+{v}}}"),
        ("根号{v}再加1", r"\sqrt{{{v}}}+1"),
        ("一除以根号{v}", r"\frac{{1}}{{\sqrt{{{v}}}}}"),
    ], [("二", "2"), ("三", "3"), ("x", "x"), ("a平方加b平方", "a^2+b^2"), ("n减1", "n-1")])
    cases += _cross_cases("scripts", [
        ("x的{v}次方", r"x^{{{v}}}"),
        ("a下标{v}", r"a_{{{v}}}"),
        ("x下标{v}的平方", r"x_{{{v}}}^2"),
        ("e的{v}次方", r"e^{{{v}}}"),
        ("以{v}为底x的对数", r"\log_{{{v}}}x"),
    ], [("二", "2"), ("三", "3"), ("n", "n"), ("k加1", "k+1"), ("负x", "-x")])
    cases += _cross_cases("limit", [
        ("x趋于{v}时f(x)的极限", r"\lim_{{x \to {v}}}f(x)"),
        ("n趋于{v}时a下标n的极限", r"\lim_{{n \to {v}}}a_n"),
        ("x从右侧趋于{v}时g(x)的极限", r"\lim_{{x \to {v}^+}}g(x)"),
        ("x从左侧趋于{v}时一除以x", r"\lim_{{x \to {v}^-}}\frac{{1}}{{x}}"),
        ("t趋于{v}时sin t除以t的极限", r"\lim_{{t \to {v}}}\frac{{\sin t}}{{t}}"),
    ], [("0", "0"), ("1", "1"), ("负1", "-1"), ("无穷", r"\infty"), ("a", "a")])
    cases += _cross_cases("derivative", [
        ("f在{v}处的导数", r"f'({v})"),
        ("y对x的{v}阶导数", r"\frac{{d^{{{v}}}y}}{{dx^{{{v}}}}}"),
        ("f关于{v}的偏导数", r"\frac{{\partial f}}{{\partial {v}}}"),
        ("f关于{v}的二阶偏导数", r"\frac{{\partial^2 f}}{{\partial {v}^2}}"),
        ("{v}平方对{v}求导", r"\frac{{d}}{{d{v}}}{v}^2"),
    ], [("x", "x"), ("t", "t"), ("二", "2"), ("三", "3"), ("n", "n")])
    cases += _cross_cases("integral", [
        ("{v}的不定积分", r"\int {v}\,dx"),
        ("从0到1的{v}定积分", r"\int_0^1 {v}\,dx"),
        ("从a到b的{v}积分", r"\int_a^b {v}\,dx"),
        ("{v}关于t的二重积分", r"\iint {v}\,dt"),
        ("闭合曲线上的{v}积分", r"\oint {v}\,ds"),
    ], [("x", "x"), ("x平方", "x^2"), ("sin x", r"\sin x"), ("e的x次方", "e^x"), ("f(x)", "f(x)")])
    cases += _cross_cases("sum", [
        ("k从1到{v}的k求和", r"\sum_{{k=1}}^{{{v}}}k"),
        ("i从0到{v}的x下标i求和", r"\sum_{{i=0}}^{{{v}}}x_i"),
        ("n从1到{v}的一除以n平方求和", r"\sum_{{n=1}}^{{{v}}}\frac{{1}}{{n^2}}"),
        ("j从负{v}到{v}的a下标j求和", r"\sum_{{j=-{v}}}^{{{v}}}a_j"),
        ("k属于{v}时f(k)求和", r"\sum_{{k \in {v}}}f(k)"),
    ], [("3", "3"), ("5", "5"), ("n", "n"), ("m", "m"), ("无穷", r"\infty")])

    matrix_values = [
        ("a b c d", "a & b \\\\ c & d"), ("1 0 0 1", "1 & 0 \\\\ 0 & 1"),
        ("x y z w", "x & y \\\\ z & w"), ("1 2 3 4", "1 & 2 \\\\ 3 & 4"),
        ("p q r s", "p & q \\\\ r & s"),
    ]
    for env_index, (env_name, env) in enumerate((("圆括号", "pmatrix"), ("方括号", "bmatrix"), ("行列式", "vmatrix"), ("大括号", "Bmatrix"), ("双竖线", "Vmatrix")), 1):
        for value_index, (description_values, latex_values) in enumerate(matrix_values, 1):
            cases.append(FormulaCase(
                id=f"matrix-{env_index:02d}-{value_index:02d}", category="matrix",
                description=f"二乘二{env_name}矩阵，按行是{description_values}",
                expected_latex=rf"\begin{{{env}}} {latex_values} \end{{{env}}}", expected_display="block",
            ))

    systems = [("x加y等于1，x减y等于0", "x+y=1", "x-y=0"), ("2x加y等于3，x减y等于1", "2x+y=3", "x-y=1"), ("a加b等于c，a减b等于d", "a+b=c", "a-b=d"), ("x平方加y平方等于1，x等于y", "x^2+y^2=1", "x=y"), ("u加v等于0，2u减v等于3", "u+v=0", "2u-v=3")]
    for style_index, (prefix, suffix) in enumerate((("方程组", "cases"), ("联立", "aligned"), ("求解方程组", "cases"), ("写出联立方程", "aligned"), ("以下两式组成方程组：", "cases")), 1):
        for value_index, (description, first, second) in enumerate(systems, 1):
            cases.append(FormulaCase(
                id=f"system-{style_index:02d}-{value_index:02d}", category="system",
                description=f"{prefix}{description}",
                expected_latex=rf"\begin{{{suffix}}} {first} \\ {second} \end{{{suffix}}}", expected_display="block",
            ))

    cases += _cross_cases("set_logic", [
        ("x属于{v}", r"x \in {v}"), ("A是{v}的子集", r"A \subseteq {v}"),
        ("A与{v}的交集", r"A \cap {v}"), ("A与{v}的并集", r"A \cup {v}"),
        ("对任意x属于{v}，存在y大于x", r"\forall x \in {v},\ \exists y>x"),
    ], [("实数集", r"\mathbb{R}"), ("整数集", r"\mathbb{Z}"), ("自然数集", r"\mathbb{N}"), ("B", "B"), ("空集", r"\varnothing")])
    cases += _cross_cases("mixed_input", [
        ("{v}+y<=3", r"{v}+y \le 3"), ("当{v}!=0时一除以{v}", r"\frac{{1}}{{{v}}},\ {v} \ne 0"),
        ("{v}->无穷", r"{v} \to \infty"), ("{v}约等于3.14", r"{v} \approx 3.14"),
        ("{v}的绝对值>=1", r"\left|{v}\right| \ge 1"),
    ], [("x", "x"), ("t", "t"), ("alpha", r"\alpha"), ("x_1", "x_1"), ("a+b", "a+b")])
    cases += _cross_cases("greek_vector", [
        ("希腊字母{v}", r"{v}"), ("{v}的向量", r"\vec{{{v}}}"),
        ("{v}的单位向量", r"\hat{{{v}}}"), ("{v}的模", r"\left\|{v}\right\|"),
        ("{v}点乘x向量", r"{v} \cdot \vec{{x}}"),
    ], [("阿尔法", r"\alpha"), ("贝塔", r"\beta"), ("伽马", r"\gamma"), ("西塔", r"\theta"), ("拉姆达", r"\lambda")])
    cases += _cross_cases("multiline", [
        ("分段函数：x大于等于0时为{v}，x小于0时为负{v}", r"f(x)=\begin{{cases}} {v}, & x \ge 0 \\ -{v}, & x<0 \end{{cases}}"),
        ("对齐写出：a等于{v}，b等于{v}加1", r"\begin{{aligned}} a&={v} \\ b&={v}+1 \end{{aligned}}"),
        ("两行推导：x等于{v}，所以x平方等于{v}平方", r"\begin{{aligned}} x&={v} \\ x^2&=({v})^2 \end{{aligned}}"),
        ("分段数列：n为偶数时{v}，n为奇数时负{v}", r"a_n=\begin{{cases}} {v}, & n\text{{ 为偶数}} \\ -{v}, & n\text{{ 为奇数}} \end{{cases}}"),
        ("对齐方程：y等于{v}x，z等于{v}y", r"\begin{{aligned}} y&={v}x \\ z&={v}y \end{{aligned}}"),
    ], [("1", "1"), ("2", "2"), ("a", "a"), ("k", "k"), ("n加1", "n+1")])

    if len(cases) < 300 or len({case.id for case in cases}) != len(cases):
        raise AssertionError("formula benchmark must contain at least 300 unique cases")
    return cases


def as_json_records() -> list[dict[str, str]]:
    return [asdict(case) for case in build_cases()]
