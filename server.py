"""Jikgu Customs Assistant (직구 관세 비서) — MCP server.

Streamable HTTP, stateless. Pure-calculation tools (no external API at runtime),
so responses stay well under the 100ms target. All tools are read-only,
non-destructive, closed-world, and idempotent.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from mcp.types import ToolAnnotations

from fastmcp import FastMCP

from jikgu import calculator, knowledge, rules

mcp = FastMCP(
    name="jikgu-customs-assistant",
    instructions=(
        "Estimates Korean import duty/VAT and clearance rules for overseas "
        "direct-purchase (해외직구) orders. All results are estimates."
    ),
)

# Category / topic literals kept in sync with the core modules.
Category = Literal[
    "clothing", "shoes", "bags", "electronics", "cosmetics",
    "health_supplements", "food", "toys", "books", "general",
]
ShippingMethod = Literal["express", "postal"]
Topic = Literal[
    "overview", "clearance_types", "combined_taxation",
    "duty_free_limit", "common_pitfalls",
]

_READONLY = dict(readOnlyHint=True, destructiveHint=False,
                 openWorldHint=False, idempotentHint=True)


# --- formatting helpers --------------------------------------------------------

def _usd(v: float) -> str:
    return f"${v:,.2f}"


def _krw(v: float) -> str:
    return f"{round(v):,}원"


def _pct(v: float) -> str:
    return f"{v * 100:.0f}%"


def _duty_markdown(e: calculator.DutyEstimate) -> str:
    lines: list[str] = ["## 직구 관세 비서 — 예상 관세 계산"]

    verdict = "면세 (관세·부가세 없음)" if e.duty_free else "과세 대상"
    lines.append(f"- **판정**: {verdict}")
    lines.append(f"- **통관 방식**: {e.clearance_type}")
    lines.append(
        f"- **면세 한도**: {_usd(e.limit_usd)} "
        f"(물품가격 {_usd(e.goods_price_usd)} 기준)"
    )

    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("| --- | --- |")
    lines.append(f"| 물품가격 | {_usd(e.goods_price_usd)} |")
    lines.append(f"| 국제배송비 | {_usd(e.intl_shipping_usd)} |")
    if not e.duty_free:
        lines.append(
            f"| 과세가격(CIF) | {_usd(e.customs_value_usd)}"
            + (f" = {_krw(e.customs_value_krw)}" if e.customs_value_krw is not None else "")
            + " |"
        )
        model_label = {
            "SIMPLIFIED": f"간이세율 {_pct(e.effective_rate)} (관세+부가세 통합)",
            "VAT_ONLY": f"부가세 {_pct(e.effective_rate)}만 (관세 0%)",
            "VAT_EXEMPT": "세액 0 (관세 0% + 부가세 면세)",
        }[e.rate_model]
        lines.append(f"| 적용 세율 | {model_label} |")
        if e.estimated_tax_krw is not None:
            lines.append(f"| **예상 세액** | **{_krw(e.estimated_tax_krw)}** |")
        else:
            lines.append(
                f"| **예상 세액** | **{_usd(e.estimated_tax_usd)}** "
                f"(= 과세가격 {_usd(e.customs_value_usd)} × {_pct(e.effective_rate)}, "
                f"환율 미지정 → × 환율(KRW/USD) 하면 원화 세액) |"
            )
    else:
        lines.append("| 예상 세액 | 0원 (면세) |")

    if e.warnings:
        lines.append("")
        lines.append("### 주의")
        for w in e.warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append(f"> {rules.DISCLAIMER}")
    return "\n".join(lines)


# --- tools ---------------------------------------------------------------------

@mcp.tool(
    annotations=ToolAnnotations(title="Estimate Korean import duty", **_READONLY),
    description=(
        "Estimates the expected Korean import duty and VAT for one overseas "
        "direct-purchase (해외직구) order, from Jikgu Customs Assistant(직구 관세 비서). "
        "Judges list-clearance vs formal-import and duty-free eligibility (150 USD "
        "default, 200 USD for US express shipments), then estimates tax using the "
        "personal-use simplified rate (간이세율, duty+VAT combined). Returns a compact "
        "markdown table. Pure calculation, no external lookup. Amounts are estimates."
    ),
)
def calculate_import_duty(
    goods_price_usd: float,
    intl_shipping_usd: float,
    country: Annotated[str, Field(description=(
        "Origin country the package ships FROM (the seller's country), "
        "e.g. 'US', 'CN', 'JP', 'DE'. NOT the buyer's country — the "
        "destination is always Korea. '미국에서 샀다' → 'US'."
    ))],
    category: Category,
    exchange_rate_krw_per_usd: float | None = None,
    shipping_method: ShippingMethod = "express",
) -> str:
    """물품가격/국제배송비/발송국/카테고리로 예상 관세를 계산한다."""
    est = calculator.calculate_import_duty(
        goods_price_usd=goods_price_usd,
        intl_shipping_usd=intl_shipping_usd,
        country=country,
        category=category,
        exchange_rate_krw_per_usd=exchange_rate_krw_per_usd,
        express=(shipping_method == "express"),
    )
    return _duty_markdown(est)


@mcp.tool(
    annotations=ToolAnnotations(title="Check list-clearance eligibility", **_READONLY),
    description=(
        "Checks whether an item category can use Korea's simplified list-clearance "
        "(목록통관) or is excluded and needs a formal import declaration, from Jikgu "
        "Customs Assistant(직구 관세 비서). Excluded categories include health "
        "supplements, food, and functional cosmetics. Returns the verdict, reason, "
        "and a suggested alternative as markdown. Pure calculation."
    ),
)
def check_clearance_eligibility(category: Category) -> str:
    """품목이 목록통관 배제 대상인지 판정한다."""
    r = calculator.check_clearance_eligibility(category)
    status = "목록통관 가능" if r.eligible else "목록통관 배제 (수입신고 필요)"
    if r.conditional:
        status += " — 단, 조건부"
    lines = [
        "## 직구 관세 비서 — 목록통관 가능 여부",
        f"- **품목**: {r.category}",
        f"- **판정**: {status}",
        f"- **이유**: {r.reason}",
        f"- **대안/안내**: {r.alternative}",
        "",
        f"> {rules.DISCLAIMER}",
    ]
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(title="Check combined-taxation risk", **_READONLY),
    description=(
        "Assesses combined-taxation (합산과세) risk across several overseas orders, "
        "from Jikgu Customs Assistant(직구 관세 비서). Under the rule effective "
        "2022-11-17, orders are combined only when the same seller, same purchase "
        "date, and same arrival date coincide; a group over 150 USD is flagged. "
        "Each order takes amount_usd, country, arrival_date, and optional seller and "
        "purchase_date. Returns a markdown summary. Pure calculation."
    ),
)
def check_combined_taxation(
    orders: list[dict],
) -> str:
    """여러 주문의 합산과세 위험을 판정한다. 각 주문: amount_usd, country, arrival_date, (선택) seller, purchase_date."""
    if not isinstance(orders, list) or not orders:
        raise ValueError("orders는 최소 1건 이상의 주문 목록이어야 합니다.")
    parsed: list[calculator.Order] = []
    for i, o in enumerate(orders):
        if not isinstance(o, dict):
            raise ValueError(f"주문 {i + 1}은(는) 객체여야 합니다.")
        if "amount_usd" not in o:
            raise ValueError(f"주문 {i + 1}에 amount_usd가 없습니다.")
        parsed.append(calculator.Order(
            amount_usd=o.get("amount_usd"),
            country=str(o.get("country", "")),
            arrival_date=str(o.get("arrival_date", "")),
            seller=str(o.get("seller", "")),
            purchase_date=str(o.get("purchase_date", "")),
        ))
    res = calculator.check_combined_taxation(parsed)

    headline = "합산과세 위험 있음" if res.any_risk else "합산과세 위험 낮음"
    lines = [
        "## 직구 관세 비서 — 합산과세 판정",
        f"- **결과**: {headline} (기준 {_usd(res.threshold_usd)}, "
        f"{rules.COMBINED_TAXATION_EFFECTIVE_DATE} 개정 규칙)",
        "",
        "| 그룹(공급자/구매일/입항일/발송국) | 주문 건수 | 합계 | 위험 |",
        "| --- | --- | --- | --- |",
    ]
    for g in res.groups:
        grp = f"{g.seller} / {g.purchase_date} / {g.arrival_date} / {g.country}"
        flag = "⚠️ 합산" if g.at_risk else "해당 없음"
        lines.append(f"| {grp} | {len(g.order_indices)}건 | {_usd(g.total_usd)} | {flag} |")
    if res.notes:
        lines.append("")
        lines.append("### 참고")
        for n in res.notes:
            lines.append(f"- {n}")
    lines.append("")
    lines.append(f"> {rules.DISCLAIMER}")
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(title="Explain the customs process", **_READONLY),
    description=(
        "Explains the Korean overseas direct-purchase customs process and common "
        "pitfalls, from Jikgu Customs Assistant(직구 관세 비서). Topics: overview, "
        "clearance_types, combined_taxation, duty_free_limit, common_pitfalls. "
        "Returns static markdown guidance. Pure calculation, no external lookup."
    ),
)
def explain_customs_process(topic: Topic = "overview") -> str:
    """통관 절차·함정을 topic 별로 설명한다."""
    return knowledge.explain(topic)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, stateless_http=True)
