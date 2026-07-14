# SPEC — 직구 관세 비서 도메인 규칙

해외직구 예상 세액·통관 판정 규칙과 출처. 규칙 상수의 실제 값은
`jikgu/rules.py`에 주석과 함께 있으며, 검증 상태를 **VERIFIED / UNVERIFIED**로
표기한다. UNVERIFIED 값은 툴 출력의 면책 문구로 커버한다.

## 세액 계산 모형 — 간이세율(bundled) 채택

핵심 결정: 자가사용 목적 해외직구 물품에는 관세청이 **간이세율**(관세+부가세를 하나로
묶은 단일 세율)을 적용한다. 따라서 관세/부가세를 인위적으로 쪼개 표기하지 않는다.

- 일반 관세율 + 부가세를 따로 계산하면 세액이 과대평가된다.
  예) 의류: 관세 13% + 부가세 (113×10%) = 24.3% vs 실제 간이세율 18%.
- 기본관세율 0% 품목(스마트폰·노트북·태블릿, 도서)은 간이세율 구간이 없어
  **부가세 10%만**(도서는 부가세 면세 → 세액 0)으로 처리한다.

> 원 작업 지시는 "관세·부가세 breakdown"과 "관세율(의류 13%)을 간이세율표 기준"이라고
> 표현했으나, 13%는 기본 **관세율**이고 의류의 **간이세율**은 18%(전액 통합)이다.
> 지시의 "최신 여부 확인 후 반영" 요구에 따라 간이세율 모형으로 구현했다.
> breakdown은 duty/VAT 분해 대신 물품가격→국제배송비→과세가격(CIF)→적용세율→예상세액의
> 항목형 마크다운 표로 제공한다.

## 1. 면세 한도 (목록통관 de-minimis)

- 일반 국가: 물품가격 **150 USD 이하** 면세.
- 미국발 **특송**(DHL·FedEx·UPS): 한미FTA로 **200 USD 이하** 면세.
- 미국발 **우편**: 200이 아니라 **150 USD**.
- 목록통관 배제 품목: 국가 무관 **150 USD**.
- **한도 초과 시 초과분이 아니라 전액 과세.** (VERIFIED)
- 판정 기준액(물품가격)에는 국제운임·보험료를 **포함하지 않는다.** 과세 시
  과세가격 = 물품가격 + 국제운임 + 보험료(CIF). (VERIFIED)

출처:
- 한국세정신문 Q&A — https://www.taxtimes.co.kr/news/article.html?no=264638
- 찾기쉬운 생활법령정보(관·부가세 계산) — https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=3&cciNo=1&cnpClsNo=2
- 짐스캐너(전액 과세·CIF) — https://jimscanner.co.kr/blog/overseas-customs-duty-guide-150-200-usd

## 2. 품목별 간이세율

| 카테고리 | 세율/모형 | 검증 |
| --- | --- | --- |
| clothing(의류) | 18% 통합 | VERIFIED — 관세법 시행령 별표2(가죽/섬유 의류 18%) |
| shoes(신발) | 18% 통합 | VERIFIED — 별표2(신발류 18%) |
| bags, cosmetics, health_supplements, food, toys, general | 15% 통합 | UNVERIFIED — 실무 catch-all, 별표2 전체 표 원문 미인용 |
| electronics(전자) | 부가세 10%만 | UNVERIFIED — 스마트폰·노트북·태블릿 관세 0% 가정. 이어폰·카메라 등 액세서리는 관세가 붙을 수 있음 |
| books(도서) | 세액 0 | UNVERIFIED — 관세 0% + 도서 부가세 면세(확인 필요) |

출처:
- 관세법 시행규칙/시행령 별표2 — https://www.law.go.kr/법령/관세법시행규칙
- 별표2 인용(모피 19%, 가죽/섬유 의류·신발 18%) — 찾기쉬운 생활법령정보(세금납부) https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=715&ccfNo=3&cciNo=1&cnpClsNo=2
- 실무 세율 요약 — https://jimscanner.co.kr/blog/overseas-customs-duty-guide-150-200-usd
- 관세 0% 전자(스마트폰/노트북) — https://www.2fasts.com/page/info_tax.asp

부가세율 10%: 부가가치세법 표준세율. (VERIFIED)

## 3. 목록통관 배제 대상

정식 수입신고(일반통관) 대상. 국가 무관 150 USD 면세.

- **건강기능식품**(비타민·오메가3·프로폴리스 등) — 자가사용 6병까지 요건 생략.
- **식품·주류·담배·농림축수산물** 등 검역대상.
- **의약품·의료기기·한약재**(카테고리 enum 밖, 안내 텍스트로 커버).
- **화장품**은 조건부: 일반 화장품은 목록통관 가능, 기능성·태반·스테로이드·성분미상
  유해화장품은 배제. (카테고리만으로 확정 불가 → 경고 표기)

출처:
- 찾기쉬운 생활법령정보(의약품·건강기능식품) — https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=2&cciNo=2&cnpClsNo=3
- 찾기쉬운 생활법령정보(식품·화장품) — https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1504&ccfNo=2&cciNo=2&cnpClsNo=4

## 4. 합산과세 (2022-11-17 개정)

- **합산**: 같은 해외공급자 + 같은 구매일 + 같은 입항일 건을 면세범위로 분할한 경우.
  그룹 합계가 150 USD 초과 + 그룹 내 2건 이상이면 위험.
- **제외**: 공급자가 다르거나 구매일이 다르면 입항일이 같아도 합산하지 않음.
- 하나의 운송장(B/L·AWB)으로 묶여 반입된 물품을 분할신고하면 합산 가능(배대지 합배송).

> 원 지시는 "같은 날 입항 + 같은 국가 발송 합산"으로 표현했으나, 2022-11-17 개정으로
> 현행 기준은 **국가가 아니라 공급자+구매일**이다. 이를 반영해 `check_combined_taxation`
> 입력에 선택 필드 `seller`, `purchase_date`를 추가했다. 두 값이 없으면 발송국+입항일로
> 보수적으로 그룹화하고 "공급자·구매일 확인 필요" 경고를 단다.

출처:
- 관세청 보도자료(입항일 같아도 합산과세 면제) — https://www.customs.go.kr/kcs/na/ntt/selectNttInfo.do?mi=2891&nttSn=10069842
- KDI 경제교육·정보센터 — https://eiec.kdi.re.kr/policy/materialView.do?num=232110

## 검증 기준선

가장 강한 검증은 관세청 '해외직구물품 예상세액 조회'(customs.go.kr/kcs/ad/tax/BuyTaxCalculation.do)
결과와 대조하는 것. 해당 페이지는 JS 렌더라 자동 조회가 어려워 이번 구현에서는 대조하지
못했다(수동 확인 권장). 그 외 규칙은 위 출처로 교차 확인.

## 다음 단계 (공모전 다음 회차 대비 — 2026-07-14 세션에서 결정)

우선순위 순. 현재는 "계산기" 수준 — 심사 기준(창의성·편의성)을 겨냥하려면 "결정 도우미"로 진화 필요.

1. **절세 시뮬레이션 (킬러 기능)**: 한도 초과 시 "얼마를 낮추면 면세인지 / 나눠 사면 얼마 절약"을 자동 제시. 합산과세도 "B 주문을 입항일 다르게 하면 회피" 식 행동 제안으로.
2. **장바구니 최적화**: 여러 품목을 어떻게 나눠 주문해야 총 세액 최소인지 조합 비교.
3. **관세청 고시환율 자동 적용** (주간 고시, 캐시하면 100ms 유지 가능).
4. **유니패스 HS코드 API 연동** → UNVERIFIED 세율 6종 해소 + 정확도.
5. 관세청 예상세액조회(BuyTaxCalculation.do)와 수동 대조 1건 이상 (15% catch-all 검증).
6. 본선 진출 시: Kakao Tools 위젯 스펙 대응.

### 재배포 절차 (다음에 이어서 할 때)
- 로컬: `.venv/bin/python server.py` (포트 8000) + `cloudflared tunnel --url http://localhost:8000`
- KC(공모전 기간만): playmcp.kakaocloud.io → Git 소스 빌드 → 이 레포(https://github.com/elinysh/jikgu-customs-mcp), container_port 8000
- PlayMCP 콘솔에서 endpoint 갱신 후 "정보 불러오기" 재실행 필수 (스키마 캐시 갱신)
- 주의: MCP 업데이트 시 KC는 기존 서버 삭제 후 같은 이름으로 재생성 → PlayMCP 재심사 요청
