"""Domain rules and constants for Korean import-duty estimation.

Every constant carries a source URL and a verification status in its comment.
Rules confirmed against official / government sources are marked VERIFIED;
values taken from practitioner guides but not confirmed against the primary
legal text (관세법 시행령 별표2 full table) are marked UNVERIFIED and the tool
output must carry the "예상치" disclaimer.

Model choice (see SPEC.md): for personal-use direct purchases customs applies
the simplified consolidated rate (간이세율), which bundles 관세 + 부가세 into a
single rate. We therefore do NOT fabricate a separate 관세/부가세 split. Items
whose basic duty is 0% (phones, laptops, tablets, books) are not in a 간이세율
bracket and pay VAT 10% only (books: VAT-exempt).
"""

from __future__ import annotations

# --- 목록통관 면세 한도 (list-clearance de-minimis) ---------------------------
# 일반 국가: 물품가격 미화 150달러 이하 면세.
# 미국발 + 특송(express): 한미FTA로 200달러 이하 면세. 우편(postal)은 미국도 150.
# 목록통관 배제 품목(수입신고 대상)은 국가 무관 150달러.
# 판정 기준은 "물품가격"이며 국제운임/보험료는 포함하지 않는다.
# VERIFIED: 관세청/한국세정신문 Q&A, 찾기쉬운 생활법령정보
#   https://www.taxtimes.co.kr/news/article.html?no=264638
#   https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=3&cciNo=1&cnpClsNo=2
DE_MINIMIS_DEFAULT_USD = 150.0
DE_MINIMIS_US_EXPRESS_USD = 200.0

# 한도 초과 시 초과분이 아니라 "전액"이 과세 대상.
# VERIFIED: 관세청 안내, 다수 실무 가이드
#   https://jimscanner.co.kr/blog/overseas-customs-duty-guide-150-200-usd
TAX_ON_FULL_AMOUNT_WHEN_OVER_LIMIT = True

# 부가가치세율.
# VERIFIED: 부가가치세법 (표준세율 10%)
VAT_RATE = 0.10


# --- 간이세율 (simplified consolidated rate, 관세+부가세 통합) ------------------
# 자가사용 목적 소액 수입물품에 적용. 값은 과세가격(CIF, KRW) 대비 통합 세율.
# 각 항목: (효과세율, 세율모형, 출처, 검증상태)
#   세율모형: "SIMPLIFIED" = 간이세율 통합, "VAT_ONLY" = 관세0%+부가세10%,
#             "VAT_EXEMPT" = 관세0%+부가세면세
CATEGORY_RATES: dict[str, dict] = {
    # 가죽/방직 섬유 의류·신발: 18%
    # VERIFIED: 관세법 제81조·시행령 제96조 별표2 (가죽제 의류, 방직용 섬유제품, 신발류 18%)
    #   https://www.law.go.kr/법령/관세법시행규칙
    "clothing": {"rate": 0.18, "model": "SIMPLIFIED", "verified": True,
                 "note": "간이세율 18% (관세법 시행령 별표2)"},
    "shoes": {"rate": 0.18, "model": "SIMPLIFIED", "verified": True,
              "note": "간이세율 18% (관세법 시행령 별표2)"},
    # 그 밖의 소비재: 실무상 간이세율 15% catch-all.
    # UNVERIFIED: 별표2 원문 전체 표를 직접 인용하지 못함. 실무 가이드 기준.
    #   https://jimscanner.co.kr/blog/overseas-customs-duty-guide-150-200-usd
    "bags": {"rate": 0.15, "model": "SIMPLIFIED", "verified": False,
             "note": "간이세율 15% (실무 catch-all, 별표2 원문 미확인)"},
    "cosmetics": {"rate": 0.15, "model": "SIMPLIFIED", "verified": False,
                  "note": "간이세율 15% (일반 화장품 기준, 별표2 원문 미확인)"},
    "health_supplements": {"rate": 0.15, "model": "SIMPLIFIED", "verified": False,
                           "note": "간이세율 15% (별표2 원문 미확인)"},
    "food": {"rate": 0.15, "model": "SIMPLIFIED", "verified": False,
             "note": "간이세율 15% (일부 농축수산물은 세율 상이, 별표2 원문 미확인)"},
    "toys": {"rate": 0.15, "model": "SIMPLIFIED", "verified": False,
             "note": "간이세율 15% (별표2 원문 미확인)"},
    "general": {"rate": 0.15, "model": "SIMPLIFIED", "verified": False,
                "note": "간이세율 15% (기타 품목 catch-all, 별표2 원문 미확인)"},
    # 관세 0% 품목: 부가세 10%만.
    # UNVERIFIED: 스마트폰·노트북·태블릿 등 기본관세율 0% 가정. 이어폰·카메라 등
    #   일부 전자 액세서리는 관세가 붙어 세율이 다를 수 있음.
    #   https://www.2fasts.com/page/info_tax.asp (스마트폰/노트북 관세 0%)
    "electronics": {"rate": VAT_RATE, "model": "VAT_ONLY", "verified": False,
                    "note": "관세 0% 가정(스마트폰·노트북·태블릿) → 부가세 10%만. "
                            "이어폰·카메라 등 액세서리는 관세가 붙을 수 있음"},
    # 도서: 관세 0% + 부가세 면세.
    # UNVERIFIED: 도서 부가세 면세(부가가치세법) 통용되나 수입 도서 처리는 확인 필요.
    "books": {"rate": 0.0, "model": "VAT_EXEMPT", "verified": False,
              "note": "관세 0% + 도서 부가세 면세 → 세액 0 (확인 필요)"},
}

CATEGORIES = tuple(CATEGORY_RATES.keys())


# --- 목록통관 배제 (list-clearance exclusion) ---------------------------------
# 배제 품목은 목록통관 불가 → 정식 수입신고(일반통관). 국가 무관 150달러 면세.
# VERIFIED: 찾기쉬운 생활법령정보, 관세청 안내
#   https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=2&cciNo=2&cnpClsNo=3
#   https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=2&cciNo=2&cnpClsNo=4
LIST_CLEARANCE_EXCLUDED: dict[str, str] = {
    "health_supplements": "건강기능식품(비타민·오메가3·프로폴리스 등)은 목록통관 배제 대상. "
                          "자가사용 목적 6병까지 수입요건 생략 가능",
    "food": "식품·주류·담배류, 농림축수산물 등 검역대상 물품은 목록통관 배제 대상",
}

# 조건부 배제: 카테고리만으로는 배제 여부가 갈리는 품목.
LIST_CLEARANCE_CONDITIONAL: dict[str, str] = {
    "cosmetics": "일반 화장품은 목록통관 가능하나, 기능성화장품·태반함유·스테로이드 함유·"
                 "성분미상 유해화장품은 목록통관 배제 대상(수입신고 필요)",
}

# 카테고리 enum에 없지만 대표적으로 배제되는 품목(안내용).
KNOWN_EXCLUDED_KEYWORDS: dict[str, str] = {
    "의약품": "의약품(감기약·해열제·소화제·파스 등)은 목록통관 배제. 자가사용 6병까지 요건 생략",
    "의료기기": "의료기기는 목록통관 배제(수입신고 필요)",
    "한약재": "한약재는 목록통관 배제(검역·수입요건 확인 필요)",
}


# --- 합산과세 (combined taxation) ---------------------------------------------
# 2022-11-17 개정 이후: 같은 해외공급자 + 같은 구매일 + 같은 입항일 + 동일 수령인
# 조건이 모두 맞는 2건 이상을 면세범위로 분할한 경우에만 합산과세.
# 다른 공급자이거나 구매일이 다르면 입항일이 같아도 합산 제외.
# 하나의 B/L·AWB로 묶여 반입된 물품을 분할신고하는 경우도 합산 대상.
# VERIFIED: 관세청 보도자료(입항일 같아도 합산과세 면제), KDI 경제교육정보센터
#   https://www.customs.go.kr/kcs/na/ntt/selectNttInfo.do?mi=2891&nttSn=10069842
#   https://eiec.kdi.re.kr/policy/materialView.do?num=232110
COMBINED_TAXATION_THRESHOLD_USD = 150.0
COMBINED_TAXATION_EFFECTIVE_DATE = "2022-11-17"


# --- 과세가격 (customs value / CIF) -------------------------------------------
# 한도 초과로 과세되는 경우 과세가격 = 물품가격 + 국제운임 + 보험료(CIF).
# 면세 판정 기준액(물품가격)에는 국제운임을 포함하지 않는다.
# VERIFIED: 찾기쉬운 생활법령정보(관·부가세 계산하기)
#   https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=3&cciNo=1&cnpClsNo=2

DISCLAIMER = (
    "본 결과는 공개된 관세 규정을 근거로 한 **예상치**이며, 실제 부과 세액은 HS 코드·"
    "품목 상세·환율·통관 시점에 따라 다를 수 있습니다. 정확한 세액은 관세청 "
    "'해외직구물품 예상세액 조회'(customs.go.kr) 또는 관세청 콜센터(125)로 확인하세요."
)
