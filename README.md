# 직구 관세 비서 (Jikgu Customs Assistant) — MCP Server

해외직구 예상 관세·부가세와 통관 규칙을 계산하는 MCP 서버. 외부 API 호출 없이
순수 계산으로 동작해 응답이 빠르고(로컬 왕복 ~7ms), 모든 툴이 read-only입니다.

- Transport: **Streamable HTTP**, **stateless**, 포트 `8000`, 경로 `/mcp`
- FastMCP 3.x (MCP 프로토콜 `2025-06-18`)
- 결과는 정제된 마크다운 텍스트(raw JSON 덤프 아님)

> 모든 결과는 공개된 관세 규정 기반 **예상치**입니다. 실제 부과 세액은 HS 코드·품목
> 상세·환율·통관 시점에 따라 다를 수 있습니다. 정확한 값은 관세청
> '해외직구물품 예상세액 조회'(customs.go.kr) 또는 콜센터(125)로 확인하세요.

## 툴 (4개)

| 툴 | 설명 |
| --- | --- |
| `calculate_import_duty` | 물품가격·국제배송비·발송국·품목으로 목록통관/일반통관 판정 + 면세 여부 + 예상 세액(간이세율) |
| `check_clearance_eligibility` | 품목이 목록통관 배제 대상인지 판정 + 이유 + 대안 |
| `check_combined_taxation` | 여러 주문의 합산과세 위험 판정(2022-11-17 개정 규칙) |
| `explain_customs_process` | 통관 절차·함정 설명(정적 지식) |

모든 툴 annotations: `readOnlyHint=true`, `destructiveHint=false`,
`openWorldHint=false`, `idempotentHint=true`, `title` 지정.

## 로컬 실행

```bash
# uv (권장)
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python server.py

# 또는 venv + pip
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

서버는 `http://0.0.0.0:8000/mcp` 에서 Streamable HTTP로 대기합니다.

## 테스트

```bash
.venv/bin/python -m pytest -q
```

## MCP Inspector로 테스트

```bash
npx @modelcontextprotocol/inspector
```

Inspector에서 Transport `Streamable HTTP`, URL `http://127.0.0.1:8000/mcp` 로 연결 →
`tools/list`로 4개 툴 확인 → `calculate_import_duty` 등을 호출.

## curl로 핸드셰이크 확인

```bash
BASE=http://127.0.0.1:8000/mcp
# initialize
curl -sS -L -X POST "$BASE" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'

# tools/list
curl -sS -L -X POST "$BASE" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# tools/call
curl -sS -L -X POST "$BASE" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"calculate_import_duty","arguments":{"goods_price_usd":250,"intl_shipping_usd":30,"country":"US","category":"clothing","exchange_rate_krw_per_usd":1400}}}'
```

`Accept` 헤더에 `text/event-stream` 이 없으면 406이 납니다. 응답은 SSE(`data: {...}`)로 옵니다.

## Docker

```bash
docker build -t jikgu-customs-mcp .
docker run -p 8000:8000 jikgu-customs-mcp
```

## 도메인 규칙·출처

`SPEC.md` 참고. 관세 규칙은 관세청/찾기쉬운 생활법령정보/관세법 시행령 기준으로
검증했으며, 코드 상수마다 출처 URL과 검증 상태(VERIFIED/UNVERIFIED)를 주석으로 표기.
