"""Pure calculation functions for Korean import-duty estimation.

No I/O, no MCP dependency. Every function is deterministic and unit-testable.
Amounts in USD unless the field name ends with `_krw`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules


# --- input validation ---------------------------------------------------------

_US_NAMES = {"us", "usa", "united states", "united states of america",
             "미국", "america"}


def is_us(country: str) -> bool:
    """True if the shipping origin is the United States (accepts code or name)."""
    return country.strip().lower() in _US_NAMES


def _require_non_negative(value: float, label: str) -> float:
    if value is None:
        raise ValueError(f"{label}은(는) 필수 입력값입니다.")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}은(는) 숫자여야 합니다. 받은 값: {value!r}")
    if num < 0:
        raise ValueError(f"{label}은(는) 0 이상이어야 합니다. 받은 값: {num}")
    return num


def _normalize_category(category: str) -> str:
    key = (category or "").strip().lower()
    if key not in rules.CATEGORY_RATES:
        allowed = ", ".join(rules.CATEGORIES)
        raise ValueError(
            f"지원하지 않는 품목 카테고리입니다: {category!r}. "
            f"허용 값: {allowed}"
        )
    return key


# --- clearance limit -----------------------------------------------------------

def clearance_limit_usd(category: str, country: str, express: bool) -> float:
    """면세 한도(물품가격 기준, USD). 배제품목은 국가 무관 150."""
    if category in rules.LIST_CLEARANCE_EXCLUDED:
        return rules.DE_MINIMIS_DEFAULT_USD
    if is_us(country) and express:
        return rules.DE_MINIMIS_US_EXPRESS_USD
    return rules.DE_MINIMIS_DEFAULT_USD


# --- import duty estimate ------------------------------------------------------

@dataclass
class DutyEstimate:
    category: str
    country: str
    express: bool
    goods_price_usd: float
    intl_shipping_usd: float
    limit_usd: float
    duty_free: bool
    excluded_from_list_clearance: bool
    clearance_type: str            # "목록통관" | "일반통관(수입신고)"
    customs_value_usd: float       # 과세가격 CIF (USD)
    effective_rate: float          # 적용 간이세율 (과세 시)
    rate_model: str
    rate_note: str
    rate_verified: bool
    exchange_rate: float | None
    customs_value_krw: float | None
    estimated_tax_krw: float | None
    estimated_tax_usd: float        # 항상 계산(환율 없어도 USD 기준 참고치)
    warnings: list[str] = field(default_factory=list)


def calculate_import_duty(
    goods_price_usd: float,
    intl_shipping_usd: float,
    country: str,
    category: str,
    exchange_rate_krw_per_usd: float | None = None,
    express: bool = True,
) -> DutyEstimate:
    """해외직구 1건의 예상 통관 판정·세액을 계산한다.

    면세 판정은 물품가격(국제운임 제외) 기준. 과세 시 과세가격 = 물품가격 + 국제운임(CIF).
    자가사용 물품 간이세율(관세+부가세 통합)로 예상세액 산출. 한도 초과 시 전액 과세.
    """
    cat = _normalize_category(category)
    goods = _require_non_negative(goods_price_usd, "물품가격(USD)")
    shipping = _require_non_negative(intl_shipping_usd, "국제배송비(USD)")
    rate = None
    if exchange_rate_krw_per_usd is not None:
        rate = _require_non_negative(exchange_rate_krw_per_usd, "환율(KRW/USD)")
        if rate == 0:
            raise ValueError("환율(KRW/USD)은 0보다 커야 합니다.")

    excluded = cat in rules.LIST_CLEARANCE_EXCLUDED
    limit = clearance_limit_usd(cat, country, express)
    duty_free = goods <= limit

    rate_info = rules.CATEGORY_RATES[cat]
    eff_rate = float(rate_info["rate"])

    customs_value_usd = goods + shipping  # CIF, 과세 시 사용
    if duty_free:
        est_usd = 0.0
    else:
        est_usd = customs_value_usd * eff_rate

    est_krw = None
    cv_krw = None
    if rate is not None:
        cv_krw = customs_value_usd * rate
        est_krw = est_usd * rate

    # 배제 품목뿐 아니라 면세 한도 초과 건도 목록통관에서 배제되어 수입신고 대상.
    clearance_type = "일반통관(수입신고)" if (excluded or not duty_free) else "목록통관"

    warnings: list[str] = []
    if not rate_info["verified"]:
        warnings.append(f"적용 세율 미검증: {rate_info['note']}")
    if cat in rules.LIST_CLEARANCE_CONDITIONAL:
        warnings.append(rules.LIST_CLEARANCE_CONDITIONAL[cat])
    if is_us(country) and not express:
        warnings.append(
            "미국발이라도 우편(postal) 배송은 200달러가 아닌 150달러 한도가 적용됩니다."
        )
    if rate is None and not duty_free:
        warnings.append("환율 미지정 — 세액은 USD 기준 참고치이며 수식으로 함께 표기했습니다.")

    return DutyEstimate(
        category=cat,
        country=country,
        express=express,
        goods_price_usd=goods,
        intl_shipping_usd=shipping,
        limit_usd=limit,
        duty_free=duty_free,
        excluded_from_list_clearance=excluded,
        clearance_type=clearance_type,
        customs_value_usd=customs_value_usd,
        effective_rate=eff_rate,
        rate_model=str(rate_info["model"]),
        rate_note=str(rate_info["note"]),
        rate_verified=bool(rate_info["verified"]),
        exchange_rate=rate,
        customs_value_krw=cv_krw,
        estimated_tax_krw=est_krw,
        estimated_tax_usd=est_usd,
        warnings=warnings,
    )


# --- list-clearance eligibility ------------------------------------------------

@dataclass
class ClearanceEligibility:
    category: str
    eligible: bool                 # 목록통관 가능 여부
    conditional: bool              # 카테고리만으로 확정 불가(기능성 여부 등)
    reason: str
    alternative: str


def check_clearance_eligibility(category: str) -> ClearanceEligibility:
    """품목이 목록통관 가능한지 판정하고 사유·대안을 반환."""
    cat = _normalize_category(category)
    if cat in rules.LIST_CLEARANCE_EXCLUDED:
        return ClearanceEligibility(
            category=cat,
            eligible=False,
            conditional=False,
            reason=rules.LIST_CLEARANCE_EXCLUDED[cat],
            alternative="정식 수입신고(일반통관)로 진행. 국가 무관 150달러까지 면세, "
                        "초과 시 과세. 자가사용 수량 제한·수입요건을 확인하세요.",
        )
    if cat in rules.LIST_CLEARANCE_CONDITIONAL:
        return ClearanceEligibility(
            category=cat,
            eligible=True,
            conditional=True,
            reason=rules.LIST_CLEARANCE_CONDITIONAL[cat],
            alternative="기능성·태반·스테로이드·성분미상 제품이면 수입신고 필요. "
                        "제품 성분을 확인하세요.",
        )
    return ClearanceEligibility(
        category=cat,
        eligible=True,
        conditional=False,
        reason="목록통관 배제 대상이 아니므로 목록통관 가능(간이 절차).",
        alternative="추가 조치 불필요. 단 한도 초과 시 과세 대상.",
    )


# --- combined taxation ---------------------------------------------------------

@dataclass
class Order:
    amount_usd: float
    country: str
    arrival_date: str
    seller: str = ""
    purchase_date: str = ""


@dataclass
class CombinedGroup:
    seller: str
    purchase_date: str
    arrival_date: str
    country: str
    order_indices: list[int]
    total_usd: float
    at_risk: bool


@dataclass
class CombinedResult:
    groups: list[CombinedGroup]
    any_risk: bool
    threshold_usd: float
    notes: list[str] = field(default_factory=list)


def check_combined_taxation(orders: list[Order]) -> CombinedResult:
    """합산과세 위험 판정.

    2022-11-17 개정 규칙: 같은 해외공급자 + 같은 구매일 + 같은 입항일 건만 합산.
    한 그룹 합계가 150달러를 초과하고 그 그룹에 2건 이상이 있으면 위험.
    seller/purchase_date 미입력 시 보수적으로 발송국+입항일로 그룹핑하고
    "공급자·구매일 확인 필요" 경고를 단다.
    """
    if not orders:
        raise ValueError("주문이 최소 1건 이상 필요합니다.")

    notes: list[str] = []
    missing_key = any(not (o.seller and o.purchase_date) for o in orders)
    if missing_key:
        notes.append(
            "일부 주문에 공급자(seller)/구매일(purchase_date)이 없어 발송국+입항일로 "
            "보수적으로 그룹화했습니다. 현행 규칙은 '같은 공급자+같은 구매일+같은 입항일'만 "
            "합산하므로, 공급자나 구매일이 다르면 실제로는 합산 제외될 수 있습니다."
        )

    groups: dict[tuple, list[int]] = {}
    for i, o in enumerate(orders):
        amt = _require_non_negative(o.amount_usd, f"주문 {i + 1} 금액(USD)")
        o.amount_usd = amt
        if o.seller and o.purchase_date:
            key = (o.seller.strip(), o.purchase_date.strip(),
                   o.arrival_date.strip(), o.country.strip().lower())
        else:
            key = ("(미상)", "(미상)", o.arrival_date.strip(),
                   o.country.strip().lower())
        groups.setdefault(key, []).append(i)

    result_groups: list[CombinedGroup] = []
    any_risk = False
    for key, idxs in groups.items():
        total = sum(orders[i].amount_usd for i in idxs)
        at_risk = len(idxs) >= 2 and total > rules.COMBINED_TAXATION_THRESHOLD_USD
        if at_risk:
            any_risk = True
        result_groups.append(CombinedGroup(
            seller=key[0],
            purchase_date=key[1],
            arrival_date=key[2],
            country=key[3],
            order_indices=idxs,
            total_usd=total,
            at_risk=at_risk,
        ))

    notes.append(
        "하나의 운송장(B/L·AWB)으로 묶여 반입된 물품을 면세범위로 분할신고하면, "
        "공급자·구매일이 달라도 합산과세될 수 있습니다."
    )
    return CombinedResult(
        groups=result_groups,
        any_risk=any_risk,
        threshold_usd=rules.COMBINED_TAXATION_THRESHOLD_USD,
        notes=notes,
    )
