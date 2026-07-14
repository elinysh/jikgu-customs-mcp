"""Unit tests for the pure calculation layer."""

import pytest

from jikgu import calculator as calc
from jikgu.calculator import Order


# --- 150 USD boundary (default country) ---------------------------------------

def test_under_150_general_is_duty_free():
    e = calc.calculate_import_duty(140, 20, "CN", "general", express=True)
    assert e.duty_free is True
    assert e.estimated_tax_usd == 0.0
    assert e.clearance_type == "목록통관"


def test_exactly_150_is_duty_free():
    # "150달러 이하" → 150 포함.
    e = calc.calculate_import_duty(150, 10, "CN", "clothing")
    assert e.limit_usd == 150
    assert e.duty_free is True


def test_over_150_is_taxed_on_full_customs_value():
    # 초과분이 아니라 전액(CIF) 과세.
    e = calc.calculate_import_duty(151, 9, "CN", "clothing")
    assert e.duty_free is False
    assert e.customs_value_usd == pytest.approx(160.0)  # 151 + 9 (CIF)
    # clothing 간이세율 18% × 과세가격 전액
    assert e.estimated_tax_usd == pytest.approx(160.0 * 0.18)


# --- US 200 USD boundary -------------------------------------------------------

def test_us_express_180_is_duty_free():
    e = calc.calculate_import_duty(180, 30, "US", "clothing", express=True)
    assert e.limit_usd == 200
    assert e.duty_free is True


def test_us_express_exactly_200_is_duty_free():
    e = calc.calculate_import_duty(200, 15, "USA", "shoes", express=True)
    assert e.limit_usd == 200
    assert e.duty_free is True


def test_us_express_over_200_is_taxed():
    e = calc.calculate_import_duty(201, 0, "US", "shoes", express=True)
    assert e.duty_free is False
    assert e.estimated_tax_usd == pytest.approx(201.0 * 0.18)


def test_over_limit_non_excluded_is_formal_import():
    # 배제 품목이 아니어도 한도 초과면 목록통관 배제 → 수입신고 (회귀: 과세인데 목록통관으로 표기되던 버그).
    e = calc.calculate_import_duty(220, 15, "US", "clothing", express=True)
    assert e.duty_free is False
    assert e.clearance_type == "일반통관(수입신고)"


def test_us_postal_falls_back_to_150_limit():
    # 미국이라도 우편은 150 한도.
    e = calc.calculate_import_duty(180, 10, "US", "clothing", express=False)
    assert e.limit_usd == 150
    assert e.duty_free is False
    assert any("우편" in w for w in e.warnings)


def test_non_us_express_still_150():
    e = calc.calculate_import_duty(180, 10, "JP", "clothing", express=True)
    assert e.limit_usd == 150
    assert e.duty_free is False


# --- excluded categories -> formal import, 150 regardless of country ----------

def test_health_supplements_us_express_still_150_limit():
    # 배제 품목은 미국·특송이어도 150 한도, 일반통관.
    e = calc.calculate_import_duty(180, 10, "US", "health_supplements", express=True)
    assert e.limit_usd == 150
    assert e.excluded_from_list_clearance is True
    assert e.clearance_type == "일반통관(수입신고)"
    assert e.duty_free is False


def test_food_us_express_still_150():
    e = calc.calculate_import_duty(160, 0, "US", "food", express=True)
    assert e.limit_usd == 150
    assert e.clearance_type == "일반통관(수입신고)"


def test_eligibility_excluded_and_conditional_and_ok():
    assert calc.check_clearance_eligibility("health_supplements").eligible is False
    assert calc.check_clearance_eligibility("food").eligible is False
    cos = calc.check_clearance_eligibility("cosmetics")
    assert cos.eligible is True and cos.conditional is True
    ok = calc.check_clearance_eligibility("clothing")
    assert ok.eligible is True and ok.conditional is False


# --- rate models: 0% duty electronics / VAT-exempt books ----------------------

def test_electronics_vat_only():
    e = calc.calculate_import_duty(500, 20, "US", "electronics", express=True,
                                   exchange_rate_krw_per_usd=1400)
    assert e.rate_model == "VAT_ONLY"
    assert e.effective_rate == pytest.approx(0.10)
    # CIF = 520, VAT only 10%
    assert e.estimated_tax_usd == pytest.approx(520 * 0.10)


def test_books_vat_exempt_zero_tax():
    e = calc.calculate_import_duty(300, 20, "US", "books", express=True)
    assert e.rate_model == "VAT_EXEMPT"
    assert e.estimated_tax_usd == 0.0


# --- exchange rate handling ----------------------------------------------------

def test_exchange_rate_provided_gives_krw():
    e = calc.calculate_import_duty(200, 0, "CN", "clothing",
                                   exchange_rate_krw_per_usd=1400)
    assert e.customs_value_krw == pytest.approx(200 * 1400)
    assert e.estimated_tax_krw == pytest.approx(200 * 1400 * 0.18)


def test_exchange_rate_missing_leaves_krw_none_and_warns():
    e = calc.calculate_import_duty(200, 0, "CN", "clothing")
    assert e.estimated_tax_krw is None
    assert e.customs_value_krw is None
    assert e.estimated_tax_usd == pytest.approx(200 * 0.18)
    assert any("환율" in w for w in e.warnings)


def test_duty_free_missing_rate_no_warning_needed():
    e = calc.calculate_import_duty(100, 0, "CN", "clothing")
    assert e.duty_free is True
    assert not any("환율" in w for w in e.warnings)


# --- input validation ----------------------------------------------------------

def test_negative_price_raises():
    with pytest.raises(ValueError):
        calc.calculate_import_duty(-1, 0, "CN", "clothing")


def test_unknown_category_raises():
    with pytest.raises(ValueError):
        calc.calculate_import_duty(100, 0, "CN", "spaceship")


def test_zero_exchange_rate_raises():
    with pytest.raises(ValueError):
        calc.calculate_import_duty(100, 0, "CN", "clothing",
                                   exchange_rate_krw_per_usd=0)


# --- combined taxation: fires / does not fire ---------------------------------

def test_combined_fires_same_seller_date_arrival_over_threshold():
    orders = [
        Order(100, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01"),
        Order(80, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01"),
    ]
    res = calc.check_combined_taxation(orders)
    assert res.any_risk is True
    fired = [g for g in res.groups if g.at_risk]
    assert len(fired) == 1
    assert fired[0].total_usd == pytest.approx(180)


def test_combined_not_fired_different_seller():
    # 다른 공급자 → 입항일 같아도 합산 제외.
    orders = [
        Order(100, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01"),
        Order(80, "US", "2026-07-10", seller="ShopB", purchase_date="2026-07-01"),
    ]
    res = calc.check_combined_taxation(orders)
    assert res.any_risk is False


def test_combined_not_fired_different_purchase_date():
    orders = [
        Order(100, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01"),
        Order(80, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-02"),
    ]
    res = calc.check_combined_taxation(orders)
    assert res.any_risk is False


def test_combined_group_at_or_below_threshold_not_fired():
    # 합계가 150 이하면 위험 아님.
    orders = [
        Order(70, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01"),
        Order(80, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01"),
    ]
    res = calc.check_combined_taxation(orders)
    assert res.any_risk is False  # 150 정확히 = 초과 아님


def test_combined_single_order_never_fires():
    orders = [Order(500, "US", "2026-07-10", seller="ShopA", purchase_date="2026-07-01")]
    res = calc.check_combined_taxation(orders)
    assert res.any_risk is False


def test_combined_missing_keys_conservative_grouping_and_note():
    orders = [
        Order(100, "US", "2026-07-10"),
        Order(80, "US", "2026-07-10"),
    ]
    res = calc.check_combined_taxation(orders)
    assert res.any_risk is True  # 보수적으로 발송국+입항일 그룹핑
    assert any("공급자" in n for n in res.notes)


def test_combined_empty_raises():
    with pytest.raises(ValueError):
        calc.check_combined_taxation([])
