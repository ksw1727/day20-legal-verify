# 법률 AI 답변 검증기 (Jev × legalize-kr)

GPT가 한국 법률 질문에 답하면, 그 답변이 의존하는 주장을 실제 법령 조문과 대조해
TypeSafe의 System One 모델 **Jev**가 검증하는 파이프라인입니다.

```
질문 ─▶ GPT 답변 + 주장 목록(법령·조문) ─▶ legalize로 조문 원문 조회
     ─▶ Jev: 주장별 [뒷받침/반박/무관] + 과잉단정 여부
     ─▶ Jev: 답변 전체 [질문 응답도] + [확정적 조언 어조]
     ─▶ 코드가 판정·등급 계산 → 표 출력 + JSON 저장
```

## 설치

```bash
uv sync
cp .env.example .env   # TYPESAFE_API_KEY, OPENAI_API_KEY(또는 GPT_API_KEY) 입력
```

`legalize` CLI(pipx install legalize-cli)가 PATH에 있어야 합니다. GitHub 토큰은 `gh auth token`을 자동으로 사용합니다.

## 실행

```bash
uv run legal-verify "1년 근무한 직원의 연차휴가는 며칠인가요?"
```

질문을 생략하면 대화형으로 입력받습니다. 결과 JSON은 `reports/`에 저장됩니다.

이미 받아 둔 AI 답변을 검증하려면(답변 생성 건너뜀, OpenAI 키 불필요):

```bash
uv run legal-verify "1년 근무한 직원의 연차휴가는 며칠인가요?" --from-json samples/annual_leave.json
```

JSON 형식은 `{"answer": "...", "claims": [{"text": "...", "law": "근로기준법", "article": "제60조 제1항"}]}` 입니다.
`samples/annual_leave.json`은 맞는 주장, 조문과 어긋나는 주장, 존재하지 않는 조문을 섞어 둔 예시입니다.

## 웹앱

```bash
uv run legal-verify-web
```

http://localhost:8000 에서 두 가지 방식으로 검증할 수 있습니다.

- **질문하기**: 질문만 입력하면 GPT가 답변을 생성하고 검증합니다.
- **답변 검토**: 다른 AI에게서 받은 답변을 붙여 넣으면, GPT가 그 답변에서 주장과 인용 조문만 추출하고 Jev가 검증합니다. 답변 원문은 바꾸지 않습니다.

진행 단계(답변 준비 → 조문 조회 → Jev 검증)는 Server-Sent Events로 실시간 표시되고, 결과 JSON은 `reports/`에 저장됩니다. API 키는 서버의 `.env`에서만 읽습니다.

## 배포 (Vercel)

- 프로덕션: https://day20-legal-verify.vercel.app
- 저장소: https://github.com/ksw1727/day20-legal-verify

Vercel이 FastAPI를 네이티브로 인식하며 진입점은 `api/index.py`입니다. 서버리스 파일시스템이 읽기 전용이라
legalize 캐시는 `/tmp`로, 리포트 저장은 비활성화됩니다. `legalize`는 바이너리가 아닌 `python -m legalize_cli`로 호출합니다.

배포 후 Vercel 대시보드 → Settings → Environment Variables 에 아래를 등록하고 재배포하면 동작합니다.

| 이름 | 설명 |
|---|---|
| `TYPESAFE_API_KEY` | Jev 호출 (필수) |
| `GPT_API_KEY` 또는 `OPENAI_API_KEY` | 답변 생성·주장 추출 (필수) |
| `OPENAI_MODEL` | 기본 gpt-5.4 (선택) |
| `GITHUB_TOKEN` | legalize-kr 조회 시 GitHub API 제한 완화 (선택, 권장) |

CLI로는 `vercel env add TYPESAFE_API_KEY production` 처럼 추가할 수 있습니다. `/api/health`에서 조문 조회와 키 설정 여부를 확인할 수 있습니다.

## 판정 규칙 (legal_verify/verdict.py)

| Jev 답 | 판정 |
|---|---|
| relation = supports | 검증됨 |
| relation = contradicts | 반박됨 |
| relation = says_nothing | 근거없음 |
| 조문이 존재하지 않음 (Jev 호출 없음) | 조문없음 |

- relation confidence < 0.8 또는 overclaim > 0.5 → **사람 검토**
- 종합 등급: 반박됨·조문없음이 하나라도 있거나 질문 응답도 < 1.5 → FAIL, 근거없음 또는 확정적 어조 → CAUTION, 그 외 PASS

Jev의 원본 확률은 JSON에 그대로 남기므로, 임계값을 바꿀 때 재추론 없이 재판정할 수 있습니다.

## 테스트

```bash
uv run pytest
```

외부 API 없이 동작하는 단위 테스트(판정 규칙, 조문 파싱·복수 인용·조회 fallback, Jev 질문 구성, GPT 응답 파싱·주장 추출, 파이프라인 단계, 웹 SSE 스트림, 리포트 생성).
