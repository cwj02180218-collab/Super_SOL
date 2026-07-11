# Super SOL visual guide design

## Goal

Create two Korean infographic assets that explain how to use Super SOL at a glance. The assets
must be suitable for the repository README and social sharing without claiming that the harness
changes a model's intrinsic capability.

## Deliverables

- `docs/assets/super-sol-guide-wide.png`: 1600 x 900 landscape image for the README.
- `docs/assets/super-sol-guide-portrait.png`: 1080 x 1350 portrait image for Threads and other
  social posts.
- A README reference to the landscape image.

Both images use the same information hierarchy and wording. The portrait version reflows the
layout rather than cropping the landscape version.

## Visual direction

- Clean recommendation-table layout inspired by the supplied reference image.
- White background, near-black text, pale gray dividers, and a restrained warm orange accent.
- Large title and short subtitle followed by a six-row table.
- High contrast and generous spacing so the image remains legible when GitHub scales it down.
- No product screenshots, model-provider logos, decorative characters, or unverifiable badges.
- No watermark.

## Copy

Title:

> Super SOL - 상황별 사용 가이드

Subtitle:

> 모델을 바꾸지 않고, 작업 뒤 검증을 놓치지 않게 만드는 Codex 하네스

Table columns:

| 상황 | 추천 방식 | 판단 |
| --- | --- | --- |
| 일상 코딩 | Super SOL 플러그인 | 변경 후 검증 누락을 자동으로 확인 |
| 버그 수정 | 디버그 절차 | 재현하고 고친 뒤 같은 실패 경로를 다시 검사 |
| 배포 전 | 릴리즈 점검 | 테스트, 보안, 공급망, 재현성을 함께 확인 |
| 무료 비교 | dry-run | 모델 호출과 API 과금 없이 실행 계획만 점검 |
| 실제 벤치마크 | 명시적 승인 후 live | 고정된 컨테이너와 기록된 조건으로만 실행 |
| 자동 과금, 모델 전환 | 사용하지 않음 | 과금과 모델 선택은 사용자가 직접 결정 |

Footer:

> 모델이 아니라, 일을 끝까지 검증하게 만드는 하네스

Evidence chips:

- 198 tests passed
- 93% coverage
- digest-pinned verifier
- no automatic billable calls

The evidence chips describe the reviewed `v0.3.0` release snapshot and must not be phrased as a
permanent guarantee.

## Layout

### Landscape

The title and subtitle occupy the upper-left area. The table fills the center. Evidence chips form
a single compact row above the footer. The design should remain readable at approximately 800
pixels wide in the GitHub README.

### Portrait

The title and subtitle sit above a vertically relaxed table. Each row may wrap the judgment into
two lines. Evidence chips use a two-by-two grid above the footer. The final image must fit a 4:5
social feed without requiring a screenshot frame or large empty margins.

## Accuracy and safety constraints

- Describe Super SOL as a harness and Codex plugin, not a model or ontology.
- Do not claim Fable parity, superior model intelligence, guaranteed security, zero total cost, or
  automatic performance improvement.
- Distinguish the plugin's lack of automatic billable calls from ordinary Codex usage.
- Keep all Korean text verbatim and inspect the rasterized result for corrupted characters.
- If generated text is inaccurate, rebuild the final layout with deterministic typography while
  preserving the approved visual direction.

## Repository integration and verification

1. Save both final PNG files under `docs/assets/`.
2. Inspect both images at full size for wording, clipping, contrast, and spacing.
3. Verify their exact pixel dimensions.
4. Add the landscape asset near the introduction in `README.md` using a relative path.
5. Run `git diff --check` and verify the README link resolves to a tracked file.
6. Commit the assets and README update together after verification.
