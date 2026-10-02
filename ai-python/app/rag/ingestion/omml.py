"""把 Word 公式（OMML）转成 LaTeX。

只覆盖医学资料里常见的结构。遇到不认识的节点时，退回拼接原始文字，
并由调用方在元数据里标出，方便质量报告提示人工核对。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_SKIP_PROPERTIES = {
    "rPr",
    "ctrlPr",
    "argPr",
    "sSupPr",
    "sSubPr",
    "sSubSupPr",
    "sPrePr",
    "fPr",
    "radPr",
    "dPr",
    "naryPr",
    "funcPr",
    "mPr",
    "mcPr",
    "mcs",
    "mc",
    "accPr",
    "groupChrPr",
    "barPr",
    "borderBoxPr",
    "boxPr",
    "eqArrPr",
    "limLowPr",
    "limUppPr",
    "phantPr",
}
_TRANSPARENT = {
    "oMath",
    "oMathPara",
    "e",
    "box",
    "borderBox",
    "phant",
    "num",
    "den",
    "sup",
    "sub",
    "fName",
    "lim",
    "deg",
}
_NARY_SYMBOLS = {
    "∑": r"\sum",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "∏": r"\prod",
    "∐": r"\coprod",
    "⋃": r"\bigcup",
    "⋂": r"\bigcap",
}
_FUNCTIONS = {
    "sin": r"\sin",
    "cos": r"\cos",
    "tan": r"\tan",
    "log": r"\log",
    "ln": r"\ln",
    "exp": r"\exp",
    "lim": r"\lim",
}
_LATEX_COMMAND = re.compile(r"\\[a-zA-Z]+")
_LATEX_SYMBOLS = re.compile(r"[{}_^\\]")
_WHITESPACE = re.compile(r"\s+")


def omml_to_latex(element: ET.Element) -> tuple[str, bool]:
    """返回 LaTeX 和是否使用了拼接退回。"""

    latex, fallback = _convert(element)
    return latex.strip(), fallback


def latex_search_text(latex: str) -> str:
    """去掉 LaTeX 命令，留下变量名和数字，便于关键词检索。"""

    text = _LATEX_COMMAND.sub(" ", latex)
    text = _LATEX_SYMBOLS.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def formula_texts(element: ET.Element) -> tuple[str, str, bool]:
    """返回展示文本、检索文本，以及是否退回拼接。"""

    latex, fallback = omml_to_latex(element)
    projection = "".join(element.itertext()).strip()
    if not latex:
        return projection, projection, True
    return latex, latex_search_text(latex), fallback


def _local(element: ET.Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    for child in list(element):
        if _local(child) == name:
            return child
    return None


def _attr(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    for key, value in element.attrib.items():
        if key.rsplit("}", 1)[-1] == name:
            return value
    return None


def _escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("_", r"\_")
        .replace("^", r"\^{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("$", r"\$")
    )


def _convert_sequence(nodes: list[ET.Element]) -> tuple[str, bool]:
    parts: list[str] = []
    fallback = False
    for node in nodes:
        if _local(node) in _SKIP_PROPERTIES:
            continue
        text, child_fallback = _convert(node)
        fallback = fallback or child_fallback
        if text:
            parts.append(text)
    return "".join(parts), fallback


def _convert(element: ET.Element) -> tuple[str, bool]:
    name = _local(element)
    if name == "t":
        return _escape(element.text or ""), False
    if name in _SKIP_PROPERTIES:
        return "", False
    if name in _TRANSPARENT:
        return _convert_sequence(list(element))
    handler = _HANDLERS.get(name)
    if handler is None:
        return _escape("".join(element.itertext())), True
    return handler(element)


def _run(element: ET.Element) -> tuple[str, bool]:
    return _convert_sequence(
        [child for child in list(element) if _local(child) != "rPr"]
    )


def _require(element: ET.Element, name: str) -> tuple[str, bool]:
    child = _child(element, name)
    if child is None:
        return "", False
    return _convert(child)


def _superscript(element: ET.Element) -> tuple[str, bool]:
    base, base_fallback = _require(element, "e")
    sup, sup_fallback = _require(element, "sup")
    return f"{{{base}}}^{{{sup}}}", base_fallback or sup_fallback


def _subscript(element: ET.Element) -> tuple[str, bool]:
    base, base_fallback = _require(element, "e")
    sub, sub_fallback = _require(element, "sub")
    return f"{{{base}}}_{{{sub}}}", base_fallback or sub_fallback


def _subsup(element: ET.Element) -> tuple[str, bool]:
    base, base_fallback = _require(element, "e")
    sub, sub_fallback = _require(element, "sub")
    sup, sup_fallback = _require(element, "sup")
    return f"{{{base}}}_{{{sub}}}^{{{sup}}}", base_fallback or sub_fallback or sup_fallback


def _prescript(element: ET.Element) -> tuple[str, bool]:
    sub, sub_fallback = _require(element, "sub")
    sup, sup_fallback = _require(element, "sup")
    base, base_fallback = _require(element, "e")
    fallback = sub_fallback or sup_fallback or base_fallback
    return f"{{}}^{{{sup}}}_{{{sub}}}{{{base}}}", fallback


def _fraction(element: ET.Element) -> tuple[str, bool]:
    numerator, numerator_fallback = _require(element, "num")
    denominator, denominator_fallback = _require(element, "den")
    return f"\\frac{{{numerator}}}{{{denominator}}}", numerator_fallback or denominator_fallback


def _radical(element: ET.Element) -> tuple[str, bool]:
    base, base_fallback = _require(element, "e")
    degree_node = _child(element, "deg")
    properties = _child(element, "radPr")
    hide_node = _child(properties, "degHide") if properties is not None else None
    hidden = (_attr(hide_node, "val") or "").casefold() in {"1", "on", "true"}
    degree_text = "".join(degree_node.itertext()).strip() if degree_node is not None else ""
    if hidden or not degree_text:
        return f"\\sqrt{{{base}}}", base_fallback
    degree, degree_fallback = _convert(degree_node) if degree_node is not None else ("", False)
    return f"\\sqrt[{degree}]{{{base}}}", base_fallback or degree_fallback


def _delimiter_char(properties: ET.Element | None, name: str, default: str) -> str:
    if properties is None:
        return default
    node = _child(properties, name)
    if node is None or not any(key.rsplit("}", 1)[-1] == "val" for key in node.attrib):
        return default
    return _attr(node, "val") or ""


def _delimiter(element: ET.Element) -> tuple[str, bool]:
    properties = _child(element, "dPr")
    begin = _delimiter_char(properties, "begChr", "(")
    end = _delimiter_char(properties, "endChr", ")")
    separator = _delimiter_char(properties, "sepChr", "|")
    parts: list[str] = []
    fallback = False
    for child in list(element):
        if _local(child) != "e":
            continue
        text, child_fallback = _convert(child)
        fallback = fallback or child_fallback
        parts.append(text)
    return f"{begin}{separator.join(parts)}{end}", fallback


def _nary(element: ET.Element) -> tuple[str, bool]:
    properties = _child(element, "naryPr")
    char_node = _child(properties, "chr") if properties is not None else None
    raw = _attr(char_node, "val") if char_node is not None else None
    symbol = _NARY_SYMBOLS.get(raw or "", r"\sum" if not raw else raw)
    lower, lower_fallback = _require(element, "sub")
    upper, upper_fallback = _require(element, "sup")
    body, body_fallback = _require(element, "e")
    fallback = lower_fallback or upper_fallback or body_fallback
    return f"{symbol}_{{{lower}}}^{{{upper}}}{body}", fallback


def _function(element: ET.Element) -> tuple[str, bool]:
    name_node = _child(element, "fName")
    name, name_fallback = _convert(name_node) if name_node is not None else ("", False)
    body, body_fallback = _require(element, "e")
    command = _FUNCTIONS.get(name.strip(), name.strip())
    return f"{command} {body}".strip(), name_fallback or body_fallback


def _matrix(element: ET.Element) -> tuple[str, bool]:
    rows: list[str] = []
    fallback = False
    for row in list(element):
        if _local(row) != "mr":
            continue
        cells: list[str] = []
        for cell in list(row):
            if _local(cell) != "e":
                continue
            text, cell_fallback = _convert(cell)
            fallback = fallback or cell_fallback
            cells.append(text)
        rows.append(" & ".join(cells))
    return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}", fallback


def _limit_low(element: ET.Element) -> tuple[str, bool]:
    base, base_fallback = _require(element, "e")
    limit, limit_fallback = _require(element, "lim")
    return f"{{{base}}}_{{{limit}}}", base_fallback or limit_fallback


def _limit_up(element: ET.Element) -> tuple[str, bool]:
    base, base_fallback = _require(element, "e")
    limit, limit_fallback = _require(element, "lim")
    return f"{{{base}}}^{{{limit}}}", base_fallback or limit_fallback


def _equation_array(element: ET.Element) -> tuple[str, bool]:
    rows: list[str] = []
    fallback = False
    for child in list(element):
        if _local(child) != "e":
            continue
        text, child_fallback = _convert(child)
        fallback = fallback or child_fallback
        rows.append(text)
    return r" \\ ".join(rows), fallback


_HANDLERS = {
    "r": _run,
    "sSup": _superscript,
    "sSub": _subscript,
    "sSubSup": _subsup,
    "sPre": _prescript,
    "f": _fraction,
    "rad": _radical,
    "d": _delimiter,
    "nary": _nary,
    "func": _function,
    "m": _matrix,
    "limLow": _limit_low,
    "limUpp": _limit_up,
    "eqArr": _equation_array,
}
