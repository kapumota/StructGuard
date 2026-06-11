from __future__ import annotations

from html import escape

from structguard.findings.guarantee import GuaranteeInfo, GuaranteeLevel, guarantee_info

_BADGE_TEXT = {
    GuaranteeLevel.G1_HEURISTIC: "[G1 Heurístico]",
    GuaranteeLevel.G2_STRUCTURAL: "[G2 Estructural]",
    GuaranteeLevel.G3_BOUNDED: "[G3 Acotado]",
    GuaranteeLevel.G4_EXECUTED: "[G4 Ejecutado]",
    GuaranteeLevel.G5_FORMALLY_VERIFIED: "[G5 Formal]",
}


def guarantee_badge_text(guarantee: GuaranteeInfo | GuaranteeLevel | str) -> str:
    info = _coerce_info(guarantee)
    return _BADGE_TEXT[info.level]


def guarantee_badge_class(guarantee: GuaranteeInfo | GuaranteeLevel | str) -> str:
    info = _coerce_info(guarantee)
    return f"guarantee-{info.level.value.lower().replace('_', '-')}"


def guarantee_badge_html(guarantee: GuaranteeInfo | GuaranteeLevel | str) -> str:
    info = _coerce_info(guarantee)
    css_class = escape(guarantee_badge_class(info))
    text = escape(guarantee_badge_text(info))
    title = escape(info.description)
    return f"<span class='guarantee-badge {css_class}' title='{title}'>{text}</span>"


def _coerce_info(guarantee: GuaranteeInfo | GuaranteeLevel | str) -> GuaranteeInfo:
    if isinstance(guarantee, GuaranteeInfo):
        return guarantee
    return guarantee_info(guarantee)
