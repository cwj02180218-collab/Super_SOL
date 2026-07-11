# Super SOL

[![CI](https://github.com/cuj0218/Super-SOL/actions/workflows/ci.yml/badge.svg)](https://github.com/cuj0218/Super-SOL/actions/workflows/ci.yml)
[![Container security](https://github.com/cuj0218/Super-SOL/actions/workflows/container-security.yml/badge.svg)](https://github.com/cuj0218/Super-SOL/actions/workflows/container-security.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Super SOL은 두 가지를 한 저장소에 담습니다.

1. 평소 Codex 작업에서 검증 누락을 자동으로 챙기는 초보자용 Codex 플러그인
2. 모델과 작업 절차를 통제된 조건에서 비교하는 선택형 벤치마크 하네스

플러그인은 현재 열려 있는 순정 Codex 작업 안에서만 동작합니다. 별도 API 키, MCP 서버,
백그라운드 서비스가 없고 플러그인 자체의 **추가 API 과금 호출 없음**이 기본값입니다. 현재
Codex 작업 자체의 사용량은 그대로 발생하므로 비용 0을 보장한다는 뜻은 아닙니다. Super SOL은
새 모델이나 온톨로지가 아니라, 실제 작업과 검증 누락을 관리하는 품질관리 하네스입니다.

## 초보자용 5분 설치

먼저 macOS/Linux는 `/usr/bin/python3 --version`, Windows는 `py -3 --version`으로 Python
3.9 이상을 확인합니다. 이 명령은 플러그인이 실제로 쓰는 실행기와 같습니다. macOS/Linux에서
`/usr/bin/python3`가 없거나 3.9보다 낮으면 훅을 승인하지 말고 운영체제 Python을 먼저
업데이트합니다. 벤치마크에는 별도로 Python 3.12가 필요합니다.

정식 v0.3.0 배포본은 버전을 고정해 설치합니다.

```bash
codex plugin marketplace add cuj0218/Super-SOL --ref v0.3.0
codex plugin add super-sol@super-sol
codex plugin list
```

태그 전 개발본만 확인할 때는 `--ref main`을 사용합니다. ChatGPT/Codex 데스크톱 앱을 다시
열고 새 작업을 시작한 뒤 `/hooks`를 확인합니다. macOS/Linux에서는 설치된 Super SOL 폴더의
`hooks/super_sol_hook.py`를 `/usr/bin/python3`로 실행하고, Windows에서는 같은 파일을 `py -3`로
실행해야 합니다. 시작·요청 입력·Bash/편집·종료 이벤트 외의 경로나 명령이 보이면 승인하지
마세요. 훅 내용이 업데이트되면 다시 승인하라는 안내가 나올 수 있습니다.
`--dangerously-bypass-hook-trust`는 일반 설치 절차로 권장하지 않습니다.

```text
이 오류를 고치고 테스트까지 해줘.
공개 배포 전에 안정성을 점검해줘.
이 저장소가 무엇을 하는지 초보자 기준으로 설명해줘.
```

플러그인은 요청을 로컬 문자열 규칙으로 `설명`, `일반 작업`, `디버깅`, `배포 점검` 중
하나로 분류합니다. 프롬프트 원문, 명령, 도구 출력, 모델 출력, 환경변수는 저장하지 않습니다.
`apply_patch`, `Edit`, `Write` 변경을 관찰했는데 그 뒤 인식 가능한 성공 검증이 없으면 종료 시
경고합니다. 추가 Codex 사용량을 자동으로 만들지 않도록 추가 모델 응답을 자동 생성하지는 않습니다.

### 새 버전으로 업데이트

```bash
codex plugin remove super-sol@super-sol
codex plugin marketplace remove super-sol
codex plugin marketplace add cuj0218/Super-SOL --ref vX.Y.Z
codex plugin add super-sol@super-sol
codex plugin list
```

`vX.Y.Z`를 설치할 새 태그로 바꿉니다. 앱을 다시 열고 `/hooks`의 경로와 이벤트를 다시 확인한 뒤
신뢰를 승인합니다. 태그로 고정한 설치는 `marketplace upgrade`만으로 다음 태그로 이동하지 않습니다.

### 플러그인만 삭제

```bash
codex plugin remove super-sol@super-sol
```

### 플러그인과 marketplace 모두 삭제

```bash
codex plugin remove super-sol@super-sol
codex plugin marketplace remove super-sol
```

이전 버전으로 돌아갈 때도 업데이트 절차와 같습니다. 단, Codex 플러그인을 포함하는 `v0.3.0`
이후 태그만 선택하고, marketplace 재등록 뒤 `codex plugin add`, `codex plugin list`, 앱 재시작,
`/hooks` 확인까지 마칩니다.
`codex plugin` 명령이 없다면 Codex를 먼저 업데이트하고, Python 실행 오류가 보이면 위 버전 확인부터
다시 합니다.

### 플러그인이 하지 않는 일

- `OPENAI_API_KEY`를 읽거나 요청하지 않습니다.
- OpenAI SDK, HTTP 클라이언트, 원격 MCP를 호출하지 않습니다.
- 모델이나 reasoning effort를 몰래 변경하지 않습니다.
- 일상 작업에서 서브에이전트를 자동 생성하지 않습니다.
- 모델 자체의 지능이나 capability ceiling을 높였다고 주장하지 않습니다.

알려진 단순 live 평가 명령과 `api.openai.com` 직접 호출은 명시적 승인 없이는 로컬 훅이
차단합니다. 다만 Codex 훅은 운영체제 보안 경계가 아니며 모든 미래 도구나 사용자가 직접 작성한
임의 코드를 가로챌 수는 없습니다. 강제 보안은 Codex 권한, 샌드박스, 조직 정책과 함께
구성해야 합니다.

## 모델 선택 안내

이 안내는 [OpenAI의 2026-07-09 GPT-5.6 정식 출시 발표](https://openai.com/index/gpt-5-6/)
기준이며, 실제 선택 가능 모델은 사용자 플랜과 워크스페이스 정책에 따라 다릅니다.

| 용도 | 권장 시작점 | 이유 |
| --- | --- | --- |
| 대부분의 일상 작업 | GPT-5.6 Terra, medium | 성능·속도·비용의 균형 |
| 어렵고 열린 문제 | GPT-5.6 Sol, medium부터 | 가장 높은 단일 모델 성능 |
| 명확하고 반복적인 대량 작업 | GPT-5.6 Luna, 낮은 effort부터 | 가장 빠르고 저렴한 계층 |

가장 낮은 충분한 effort에서 시작하고, 실제 실패나 부족한 결과를 확인한 뒤 올리는 방식을
권합니다. Codex 제품의 `max`는 특히 어려운 단일 작업, `ultra`는 명확히 분리 가능한 병렬
작업에만 적합합니다. Super SOL 플러그인은 이 선택을 자동으로 바꾸지 않습니다.

선택형 API 벤치마크는 고정된 OpenAI SDK가 지원하는 `none`, `minimal`, `low`, `medium`,
`high`, `xhigh`만 받습니다. `max`와 `ultra`는 현재 벤치마크 계약 밖입니다. 특히 `ultra`는
멀티에이전트 토폴로지를 바꾸므로 단일 에이전트 비교와 같은 셀에 섞을 수 없습니다.

## 벤치마크는 선택 사항

일상 플러그인에는 Python 3.9 이상만 필요하며 Docker와 API 키는 필요하지 않습니다. 아래
하네스는 모델별 성능·비용 가설을 실험할 때만 사용합니다.

### 개발 환경

```bash
uv python install 3.12
uv sync --locked --dev
```

### 무료 dry-run

매니페스트, 모델/effort 조합, 세션 ID, 출력 경로만 확인합니다. 모델 호출이 없습니다.

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/smoke \
  --run-id day0-smoke \
  --dry-run
```

기본 비교는 `gpt-5.6-terra/medium` 대 `gpt-5.6-sol/medium`입니다. 다른 조건은
`--product-model`, `--reference-model`, `--product-effort`, `--reference-effort`로 명시합니다.
모델과 effort뿐 아니라 task·fixture 내용, 사전등록 내용 식별값, 하네스 전체 내용, `uv.lock`,
해석기/플랫폼, 실제 설치된 런타임 의존성, 두 이미지 digest가 run/session 식별자와 plan event에
기록됩니다. 리포트는 이 식별자를 다시 계산하며 조건이 하나라도 바뀐 과거 grade를 거부합니다.

### 과금되는 live 평가

live 평가는 명시적으로 실행할 때만 가능합니다. 다음 네 조건을 모두 충족해야 합니다.

1. 로컬 셸에 `OPENAI_API_KEY`가 설정되어 있음
2. 서로 다른 verifier/grader 이미지가 `@sha256:...` digest로 고정됨
3. 실행 명령에 `--confirm-billable`이 있음
4. 사용자가 현재 모델 접근권한과 quota를 확인함

Codex에게 live 실행을 맡길 때는 요청의 별도 한 줄에 `SUPER SOL 유료 실행 승인`을 정확히
적어야 합니다. 설명이나 인용문 속 유사 표현은 승인으로 취급하지 않습니다.

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day0-live \
  --product-effort medium \
  --reference-effort medium \
  --verification-image "$VERIFICATION_IMAGE" \
  --grader-image "$GRADER_IMAGE" \
  --confirm-billable
```

플래그가 없으면 이미지와 API 키가 있어도 실행 디렉터리를 만들기 전에 거부합니다. 실행 전 두
digest가 로컬에 실제로 존재하는지도 확인하므로 grader 누락을 모델 호출 뒤에 발견하지 않습니다.
live 평가는 일상 테스트나 CI에서 자동 실행되지 않습니다.

## 컨테이너 공급망

예제 verifier와 grader는 공식 `python:3.12-alpine`의 멀티플랫폼 digest와 pytest 전체
dependency tree의 hash를 고정합니다. 한 명령으로 두 이미지를 빌드하고 SPDX 2.3 SBOM을 먼저
남긴 뒤 두 이미지의 release gate를 모두 확인합니다.

```bash
uv run super-sol-container-audit \
  --repo-root . \
  --sbom-dir security/sbom
```

2026-07-11 로컬 release audit에서 두 이미지 모두 `0 Critical / 0 High`였고, 각각 58개
패키지를 기록한 SPDX SBOM이 생성됐습니다. GitHub의 container-security workflow도 같은
두 이미지에 대해 build, scan, SBOM을 수행하며 모든 Action을 전체 commit SHA로 고정합니다.

실제 live 실행용 digest는 로컬 레지스트리에서 생성합니다. 자세한 절차는
[`eval/verifier/README.md`](eval/verifier/README.md)를 참고하세요.

## 벤치마크 신뢰 경계

작업 매니페스트의 명령은 셸 문자열이 아니라 argv 배열입니다. fixture는 매니페스트 디렉터리
밖으로 나갈 수 없고 심볼릭 링크를 포함할 수 없습니다. 각 세션은 복사된 독립 workspace와
ledger를 가집니다.

| 증거 | 저장 위치 | 모델에게 보임 |
| --- | --- | --- |
| 분류, 로컬 도구 호출, gate 결과 | 세션 ledger | 필요한 도구 결과만 |
| arm, model, effort, provenance, 시간, token 사용량 | shadow stream | 아니요 |
| machine grader 통과 여부 | shadow stream의 terminal event | 아니요 |
| 외부 최종 결함 라벨 | run digest가 포함된 별도 grade 파일 | 아니요 |

모델이 호출하는 verifier와 사후 grader는 서로 다른 digest-pinned 이미지입니다. 두 컨테이너는
부모 환경변수와 API 키를 받지 않고 네트워크가 꺼집니다. root filesystem은 읽기 전용이며,
Linux capability, privilege escalation, process, memory, CPU가 제한됩니다. grader workspace는
읽기 전용이고 grader 출력은 모델로 돌아가지 않습니다.

작은 직접 비교에는 `--arm-design crossover`를 사용해 모든 작업을 두 모델과 ON/OFF arm에
각각 배정합니다. 더 긴 운영 표본에는 기본 holdout이 적합합니다.

## 과거 결과를 읽는 법

v0.2.1의 contract-v2 파일럿은 GPT-5.5와 GPT-5.6 Sol을 네 작업, 두 arm으로 비교해 16개
세션과 16개 grader 검사를 모두 완료했습니다. GPT-5.5-first 경로는 항상 reference를 쓰는
경로보다 11.2%에서 14.9% 적은 token을 사용했고 두 모델 모두 100%를 기록했습니다.

이 결과는 당시 하네스 배관과 routing 가설의 증거일 뿐입니다. Fable parity, 모델 우월성,
현재 Terra/Sol 성능을 증명하지 않습니다. 원본 집계는
[`benchmarks/day3-contract-v2/`](benchmarks/day3-contract-v2/)에 동결되어 있습니다.

현재 승격 기준은 최소 50개 crossover 작업 그룹, 미공개 versioned grader pack, 고정된
verifier/grader digest, 세션당 외부 결함 라벨 하나, paired effect와 불확실성, 실제 청구 비용,
튜닝에 쓰지 않은 사전등록 재실행입니다.

## 실험 절차와 항상 켜지는 규칙

investigation, grounding, multi-story pack은 실험 항목입니다. 신호가 맞는 harness-ON 세션에만
route되며 OFF 세션에는 들어가지 않습니다. 충분한 holdout 증거 없이 이 pack을 AGENTS.md나
전역 프롬프트에 복사하지 마세요.

항상 켜지는 것은 실행과 검증의 최소 규칙, 엄격한 매니페스트, workspace 경계, typed tool
evidence뿐입니다. 플러그인도 이 원칙을 따라 짧은 기본 지침과 조건부 작업 절차를 분리합니다.

## 품질 게이트

기본 품질 검사는 API 키와 모델 호출이 필요 없습니다.

```bash
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest --cov=fablized_sol --cov-report=term-missing
uv build
```

플러그인 패키지는 공식 validator로 별도 확인합니다.

```bash
uv run --with pyyaml python \
  ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/super-sol
uv run --with pyyaml python \
  ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/super-sol/skills/super-sol
```

## 알려진 한계

- Codex 훅의 변경 추적은 `apply_patch`, `Edit`, `Write`에 한정됩니다. shell, MCP, formatter,
  codegen이 직접 바꾼 파일은 놓칠 수 있으며 운영체제 보안 경계가 아닙니다.
- Stop 훅은 구조화된 zero exit code와 단순 검증 명령을 기준으로 경고만 합니다. shell 연결,
  검색·출력 속 검증 단어, 실패를 가린 명령은 성공 증거로 세지 않습니다.
- API 하네스의 hosted tool은 로컬 function-tool lifecycle을 우회할 수 있어 ledger 증거로
  등록하지 않습니다.
- 외부 `final_defect_found` 라벨은 여전히 평가자가 별도로 제공해야 합니다.
- 저장소의 SBOM과 CVE 결과는 예제 이미지의 release evidence입니다. downstream 이미지나 새
  digest는 다시 스캔해야 합니다.

보안 취약점은 [SECURITY.md](SECURITY.md)의 비공개 신고 절차를 사용하세요. 기여 방법은
[CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.
