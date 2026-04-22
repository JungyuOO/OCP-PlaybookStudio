---
status: active
doc_type: product_charter
audience:
  - codex
  - engineer
  - product
precedence: 2
supersedes:
  - PROJECT.md (legacy version)
  - README.md
  - P0_ARCHITECTURE_FREEZE_ADDENDUM.md (product naming portions)
last_updated: 2026-04-18
---

# PROJECT

## Product One-Liner

Playbook Studio 는 `공식 문서, 운영 가이드, 트러블슈팅 자료를 연결된 위키 대백과와 grounded chat runtime 으로 바꾸는 제품`이다.

핵심은 문서를 저장하는 것이 아니라 아래를 자동으로 만드는 것이다.

- `reader-grade technical library`
- `connected wiki navigation`
- `grounded chat corpus`
- `precise citation landing`
- `buyer/demo/release packet evidence`

## Playbook Definition

`Playbook` 은 PBS 가 최신 고정 파이프라인으로 문서를 재구성해 만든 `위키 대백과 단위` 다.

Playbook 자격은 아래 두 축을 동시에 만족할 때만 부여한다.

1. `source fidelity`
   - 원문 의미, 절차, 코드, 표, 그림, 맥락을 reader-grade 로 보존해야 한다.
2. `chat interaction quality`
   - retrieval, citation landing, follow-up interaction 에서 같은 진실 소스를 안정적으로 써야 한다.

reader-grade 실패, 구조 붕괴, 절차 붕괴 산출물은 pipeline output 일 수는 있어도 `Playbook` 이라고 부르지 않는다.

영어 본문이 발견된 문서는 `버릴 대상` 이 아니라 `번역 완료 대상` 이다.

- 공식 source lane 에서 영어 본문이 발견되면 기본 처리 순서는 `translate -> verify -> publish` 다.
- 제품 기본 행위는 제거, 퇴출, 포기가 아니라 `한국어 완성본 생산` 이다.

## Renewal Frame

PBS 는 이미 `award-winning enterprise product` 이고 `2026 best product` 중 하나로 선정된 상태다.

현재 단계는 `reinvention` 이 아니라 아래 기준의 `renewal` 이다.

- `refinement`
- `hardening`
- `validation`
- `customer order execution`

현재 주문은 `OCP operators` 를 위한 `OpenShift playbook package delivery` 이며,
이 작업은 `기존 PBS architecture 안에서 수행` 해야 한다.

## Current Renewal Scope

현재 운영 기준선은 아래다.

- `renewal_hardening_validation stage`
- `OpenShift 4.20 official source-first validated pack`
- `customer order: OCP operator playbook package delivery`
- `customer/private pack lane when explicitly ordered`

## Product Surfaces

제품 표면은 아래 세 가지로 고정한다.

1. `Playbook Library`
   - library index
   - runtime / candidate / signal state
   - control-tower style status view
2. `Wiki Runtime Viewer`
   - 본문 읽기
   - related books / sections / figures / entities 탐색
   - 정확한 anchor jump
3. `Chat Workspace`
   - grounded answer
   - citation
   - next play
   - related navigation

`Control Tower` 는 별도 최상위 surface 가 아니라 `Playbook Library` 안의 운영 view 로 취급한다.

## What Must Beat Vendor Docs

최종 문서는 최소한 vendor official docs 보다 아래 항목에서 더 나아야 한다.

1. `findability`
   - 필요한 절차/개념/트러블슈팅을 더 빨리 찾을 수 있어야 한다.
2. `readability`
   - 긴 문서를 더 적은 피로도로 읽을 수 있어야 한다.
3. `grounded jump`
   - 챗봇 citation 이 문서의 정확한 문단/표/그림으로 점프해야 한다.
4. `figure-aware learning`
   - 그림, 표, 캡션, 절차가 끊기지 않아야 한다.
5. `connected navigation`
   - 문서, 엔터티, 절차, 관련 그림이 자연스럽게 이어져야 한다.

vendor docs 는 reference surface 이기도 하다.

- `repo/AsciiDoc` 는 raw truth 기준선이다.
- `Red Hat multi-page / single-page / PDF` 는 reader benchmark, verification, fallback 기준선이다.
- PBS 는 이 기준선을 따라잡고, 가능하면 더 나은 reading + chat interaction 으로 넘어가야 한다.

## Product Promises

이 제품은 아래를 약속한다.

1. 공식 source 와 허용된 fallback source 를 수집해 재현 가능한 corpus 를 만든다.
2. raw 문서를 사람이 읽을 수 있는 technical library 로 재구성한다.
3. 같은 기준선에서 library 와 chatbot 이 동작하게 만든다.
4. 챗봇 답변은 library anchor 로 되돌아갈 수 있어야 한다.
5. customer/private 문서는 같은 아키텍처 안에서 `pack boundary labeled runtime` 으로 다룬다.
6. 고객 주문용 package output 도 기존 PBS shared truth 와 surface model 안에서 파생한다.
7. 공식 문서 lane 에서 영어 본문이 발견되면, 삭제보다 번역 완료를 우선한다.

## Non-Promises

현재 단계에서 아래는 아직 약속하지 않는다.

- 모든 포맷 완벽 지원
- 임의 문서의 zero-touch product-grade 승격
- full-sale stage
- 완전 자동 semantic parsing for every diagram
- renewal 기간 중 무근거한 product reinvention

## Source Authority

진실 계층은 아래로 고정한다.

1. `Vendor Official Repo Source`
2. `Reviewed Translation`
3. `Verified Operational Evidence`
4. `Playbook Synthesis`
5. `Model Prose`

하위 tier 는 상위 tier 를 보강할 수는 있어도 뒤집을 수 없다.

### Official Source Priority

공식 문서 lane 의 우선순위는 아래로 고정한다.

1. `official repository source such as AsciiDoc`
2. `official rendered HTML for benchmark, anchor verification, and fallback`
3. `official rendered PDF for reader verification and fallback`

즉 `published HTML` 은 official truth 자체가 아니라, `repo source first` 계약 아래의 verification/fallback lane 이다.
`published HTML/PDF` fallback 은 사용자 승인 전에는 자동으로 실행하지 않는다.

`official repository source` 가 영어이거나, rendered HTML/PDF 에서 영어 본문이 확인되면
기본 다음 단계는 `translated_ko_draft` 또는 동등한 번역 완료 lane 이다.

## Locked Product Doctrine

- 이 제품은 `markdown viewer` 가 아니다.
- 이 제품은 `connected technical wiki + grounded chat` 다.
- chat 은 library 와 다른 진실을 말하면 안 된다.
- library 는 corpus 와 다른 원천을 가지면 안 된다.
- official raw truth 는 `repo/AsciiDoc first` 로 본다.
- published HTML/PDF 는 canonical truth 가 아니라 `reader benchmark / verification / fallback` 으로만 쓴다.
- 같은 source family 에서 여러 파생본을 만들 수는 있어도, default release/runtime surface 는 `선택된 최종 Playbook` 을 우선한다.
- 영어 본문 발견 시 기본 제품 행위는 `translate and complete`, not `drop and forget` 다.
- overlay 는 본문을 덮지 않고 보조 레이어로 남는다.
- buyer/demo/release packet 은 제품 증거 surface 이지, core reader surface 를 대체하지 않는다.
- commercial packet 이나 rehearsal score 는 supporting evidence 일 뿐이며, core runtime/retrieval/citation quality gate 를 대체하지 않는다.
- 현재 주문은 PBS 자체를 다시 정의하는 작업이 아니라, 기존 PBS architecture 위에서 deliverable 을 실행하는 작업이다.

## Current Focus

현재 우선순위는 아래다.

1. `renewal hardening and validation`
2. `OCP operator playbook package delivery`
3. `corpus 와 citation 정합성 고정`
4. `official source-first operator coverage`
5. `reader / runtime hardening`
6. `customer/private pack lane stability when ordered`
