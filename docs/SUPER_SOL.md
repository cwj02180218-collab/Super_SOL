# Super SOL 제품 경계

Super SOL은 `fablized-sol`의 재현 가능한 평가 하네스와 `cuj0218/GPT.C`에서 검토한
실행·검증 원칙을 결합한 Codex 품질관리 하네스입니다. 모델도, 일반 지식 온톨로지도 아닙니다.

저장소에는 서로 분리된 두 표면이 있습니다.

1. **Codex 플러그인**: 현재 Codex 작업의 도구 결과만 관찰해 변경 뒤 검증 누락을 알립니다.
2. **선택형 API 벤치마크**: 사용자가 명시적으로 실행할 때만 모델·effort·ON/OFF arm을
   통제된 조건에서 비교합니다.

## 일상 사용 원칙

- 플러그인은 별도 API 키, SDK 호출, HTTP 요청, MCP 서버, 백그라운드 서비스가 없습니다.
- 프롬프트 원문, 명령, 도구 출력, 모델 출력, 환경변수를 저장하지 않습니다.
- 파일 변경보다 새로운 성공 검증만 완료 증거로 인정합니다.
- 검증 누락은 종료 경고로 알리되 새 모델 continuation을 자동 생성하지 않습니다.
- 모델, reasoning effort, 권한, 서브에이전트를 자동으로 바꾸지 않습니다.
- v0.4 후보는 `SessionStart` context와 암묵적 스킬 호출을 제거합니다.
- 일반 작업과 디버깅에만 154자 contract sweep을 한 번 전달하고 설명 요청에는 context를
  추가하지 않습니다.

따라서 플러그인 자체에는 별도 API 과금 호출이 없습니다. 현재 Codex 작업의 사용량과
사용자가 직접 승인한 외부 명령은 별개입니다. 훅은 품질 가드레일이지 운영체제 보안 경계가
아니므로 Codex 권한·샌드박스·조직 정책을 대체하지 않습니다.

## 현재 모델 기준

[OpenAI의 2026-07-09 GPT-5.6 정식 출시 발표](https://openai.com/index/gpt-5-6/)를 기준으로
일상 기본값은 `gpt-5.6-terra/medium`, 어려운 문제의 통제 비교군은
`gpt-5.6-sol/medium`입니다. 실제 모델 접근 가능 여부는 사용자 플랜과 워크스페이스 정책에
따릅니다.

플러그인은 이 권장안을 안내만 하고 모델을 자동 전환하지 않습니다. API 벤치마크는 모델,
effort, task/fixture 내용, 사전등록, 패키지/SDK 버전, 이미지 digest를 run identity에 묶어
서로 다른 조건과 외부 grade가 섞이지 않게 합니다.

## 채택한 증거 규칙

- 모델이 호출하는 verifier와 사후 grader는 서로 다른 digest-pinned 이미지여야 합니다.
- 로컬 typed tool 결과만 mutation 또는 verification credit을 받습니다.
- holdout label과 shadow measurement는 모델 context 밖에 둡니다.
- grader 오류, 증거 누락, parser 오류는 성공으로 해석하지 않습니다.
- 공급망 검사는 고정 base digest, Critical/High CVE fail-closed scan, SPDX SBOM을 요구합니다.
- Python dependency tree는 version과 hash를 모두 잠급니다.

다음 항목은 충분한 holdout 증거가 생길 때까지 실험으로 둡니다.

- promise-without-action 텍스트 휴리스틱
- 반복 실패 disclosure 휴리스틱
- 작업별 자동 모델/effort escalation
- GPT.C의 큰 온톨로지나 전역 정책 블록

## 무료 smoke와 선택형 live 평가

무료 smoke는 모델이나 API를 호출하지 않습니다.

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/smoke \
  --run-id day0-smoke \
  --dry-run
```

live 평가는 로컬 `OPENAI_API_KEY`, 서로 다른 두 digest-pinned 이미지, 그리고 명령의
`--confirm-billable`이 모두 있어야 시작됩니다. CI나 플러그인은 live 평가를 자동 실행하지
않습니다. 전체 절차는 [README](../README.md)와
[verifier 안내](../eval/verifier/README.md)를 참고하세요.

### stock Codex plugin-only clean-room A/B

v0.4 후보에는 기존 API 하네스와 별도로 stock Codex CLI의 raw/lean arm을 비교하는 명령이
있습니다. 무료 dry-run은 모델과 Docker를 호출하지 않지만, 임시 `CODEX_HOME`, Git revision,
플러그인 설치, 중복 스킬 경로, run/slot identity를 실제 검사합니다.

```bash
uv run super-sol-codex-ab \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/codex-ab \
  --run-id v04-gate0-dry \
  --codex-binary "$(command -v codex)" \
  --model gpt-5.6-sol \
  --effort xhigh \
  --repetitions 2 \
  --plugin-source . \
  --plugin-ref "$(git rev-parse HEAD)" \
  --dry-run
```

live clean-room 실행은 `OPENAI_API_KEY`가 아니라 사용자의 ChatGPT/Codex 인증 파일을 두 임시
홈에 동일하게 복사하며, 인증 내용과 digest는 결과에 쓰지 않고 종료 시 삭제합니다. 실행 전
digest-pinned grader image를 로컬에서 확인하고 `--confirm-billable`을 요구합니다. 추가 모델
retry는 없고 인프라 오류는 결측으로 남습니다.

## 과거 결과와 승격 기준

v0.2.1의 GPT-5.5 대 GPT-5.6 Sol 파일럿은 당시 배관과 routing 가설을 검증한 동결된 역사
자료입니다. 현재 Terra/Sol 조합의 성능이나 Fable parity를 증명하지 않습니다.

v0.3.1 잠정 비교에서는 Super SOL이 raw보다 낮은 품질과 높은 token/time을 보였지만 Codex
설정이 비대칭이어서 플러그인 단독 효과는 식별되지 않았습니다. v0.4는 T105~T108 튜닝 회귀와
T109~T116 unseen holdout을 분리하고 9개 승격 조건을 사용합니다. 자세한 내용은
[v0.3.1 postmortem](BENCHMARK_POSTMORTEM_0.3.1.md),
[clean-room preregistration](CODEX_AB_PREREGISTRATION.md),
[Day 1-3 검증](DAY3_VALIDATION.md)과 [Day 7 검토](DAY7_REVIEW.md)를 참고하세요.
