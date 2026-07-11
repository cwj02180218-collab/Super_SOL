# Super SOL Day 1-3 검증

이 3일 gate는 벤치마크 배관과 증거 경계를 검증합니다. 작은 파일럿을 Fable parity나 모델
우월성의 증거로 해석하지 않습니다.

## Day 1: 비교 가능한 실험 셀

작은 표본에서는 모든 작업을 두 모델과 두 arm에서 실행하는 crossover를 사용합니다. 기본
조합은 `gpt-5.6-terra/medium` 대 `gpt-5.6-sol/medium`이며, 모델과 effort가 각 이벤트에
함께 기록됩니다.

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/day1 \
  --run-id day1-crossover \
  --arm-design crossover \
  --product-effort medium \
  --reference-effort medium \
  --dry-run
```

네 작업 파일럿은 16개의 격리된 세션을 계획합니다. 더 긴 운영 표본에는 기본 holdout design을
쓸 수 있지만, 네 셀을 모두 갖추지 않은 결과를 crossover 보고서로 승격할 수 없습니다.

## Day 2: 독립 grader와 공급망

모델이 호출할 수 있는 verifier에는 공개 workspace 검사만 넣습니다. 별도 grader는
`/opt/grader/tests`의 root-only 검사로 모델 턴 뒤 한 번 실행됩니다. stdout/stderr는 모델에게
돌아가지 않고 boolean만 shadow stream에 기록됩니다.

live 전에 다음을 모두 확인합니다.

- verifier와 grader가 서로 다른 immutable digest를 가짐
- 두 이미지의 base가 저장소 정책과 정확히 일치함
- Docker Scout Critical/High scan이 fail-closed로 통과함
- 각 이미지의 SPDX 2.3 SBOM이 생성됨
- buggy fixture는 실패하고 local reference control은 통과함
- 컨테이너 network, parent environment, writable root, privilege escalation이 차단됨

```bash
uv run super-sol-container-audit \
  --repo-root . \
  --sbom-dir security/sbom
```

공개 grader는 배관 검증용입니다. 모델 또는 Fable 관련 성능 주장을 하려면 미공개 grader build
context를 별도로 사용해야 합니다.

## Day 3: 명시적 live 실행과 보고서

live는 자동 호출되지 않습니다. 로컬 API 키, 두 digest-pinned 이미지와 함께 사용자가
`--confirm-billable`을 직접 입력해야 합니다.

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day3-live \
  --arm-design crossover \
  --product-effort medium \
  --reference-effort medium \
  --verification-image "$VERIFICATION_IMAGE" \
  --grader-image "$GRADER_IMAGE" \
  --confirm-billable
```

평가자는 모델 context 밖에서 세션마다 최종 결함 라벨 하나를 작성합니다.

```json
{
  "grades": [
    {"session_id": "sha256-session-id", "final_defect_found": false}
  ]
}
```

```bash
uv run super-sol-report \
  --events .fablized/live/day3-live/events.jsonl \
  --grades .fablized/live/day3-live/grades.json \
  --output .fablized/live/day3-live/report.json
```

보고서는 모든 계획 세션의 plan/start/finish와 외부 grade가 정확히 하나씩 있을 때만 생성됩니다.
모델 또는 effort 불일치, 빠진 셀, 중복 terminal event, 빠진 grade는 fail-closed입니다. 결과에는
결함 없는 비율, token, 시간, 도구 호출, 검증 실패, gate block, paired effect, 95% 구간과
Terra-first lazy cascade의 품질·escalation rate·token 절감 proxy가 포함됩니다.

token volume은 비용 proxy이지 실제 달러 비용이 아닙니다. 비용 주장은 해당 실행의 실제 청구
사용량과 당시 계정 가격으로 계산해야 합니다.

## 승격 기준

네 작업 파일럿으로 parity를 주장하지 않습니다. 최소 50개 completed crossover 작업 그룹,
미공개 versioned grader pack, 고정 이미지 digest, 외부 grade, paired effect와 불확실성, 실제
청구 비용, 튜닝되지 않은 사전등록 재실행을 모두 갖추기 전까지 결과는 하네스 공학 증거입니다.
