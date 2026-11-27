---
arxiv_id: "2611.01234"            # 버전 제외, 파일명과 같아야 함
title: "Paper title as on arXiv"
authors: ["First Author", "Second Author"]
affiliation: ["Company or University A", "University B"]   # 모르면 ["?"]
venue: "arXiv preprint"           # 예: "IEEE TWC (accepted)", "IEEE GLOBECOM 2026", "Submitted to IEEE WCL"
date: 2026-11-03                  # arXiv v1 제출일
link: https://arxiv.org/abs/2611.01234
tags: [compression, AI, NR]       # compression|prediction (둘 다 가능), AI|non-AI, NR|6G
read_level: full                  # full | abstract-only
ran1_meeting: "RAN1#127"          # config/ran1_agenda/ 스냅샷의 회의 이름
ran1_agenda: ["9.1.1"]            # 대응 안건 항목 ID. standard=7이면 []
reviewed: 2026-11-26
score: 0                          # = score_breakdown 합계
score_breakdown:
  standard: 7         # /15  3GPP 관련성: 15 | 11 | 7 (0이면 요약하지 않음)
  venue: 0            # /10
  channel: 0          # /15
  assumptions: 0      # /15
  baselines: 0        # /10
  reproducibility: 0  # /5
  complexity: 0       # /10
  industry: 0         # /5
  tr38843: 0          # /15
# 비교 표용 한 줄 요약 (≈ 규칙 동일)
metrics: [SGCS, NMSE]
channel_model: "3GPP CDL-C, 32T, 13 subbands"
compression_ratio: "1/16–1/64 (48–192 bits)"   # 예측 논문은 "N/A (horizon 5 ms)" 처럼
headline_result: "eType II 대비 동일 payload에서 SGCS +0.05 (Table III)"
---

<!-- read_level이 abstract-only이면 아래 줄을 남긴다. full이면 지운다. -->
> ⚠️ **abstract only** — 전문을 확인하지 못해 초록만으로 작성. 수치·점수는 잠정치.

## Key idea

- 핵심 아이디어 2–4줄. 무엇을 새로 했고 왜 효과가 있는지.

## System model

- 안테나 구성(gNB Tx × UE Rx), 대역폭/서브캐리어/서브밴드, FDD/TDD, 피드백 대상(채널 행렬 vs 고유벡터/precoder), 양자화 방식.

## Simulation setup

| 항목 | 값 |
|---|---|
| 채널 모델 / 시나리오 | |
| 반송파 · 대역폭 | |
| 안테나 | |
| UE 속도 | |
| 학습 / 시험 데이터 | |
| 지표 | |
| Payload / 압축률 | |
| 코드·데이터 공개 | |

## Results (baseline 대비)

- baseline 이름 대비 **차이**로 적는다. 예: "eType II(PC=4) 대비 같은 48 bits에서 SGCS 0.81 → 0.88 (Table III)".
- 그래프에서 읽은 값은 `≈` + 그림 번호. 예: "NMSE ≈ −18 dB vs CRNet ≈ −14 dB (Fig. 5, CR=1/16)".
- 복잡도: FLOPs / 파라미터 수 / 지연 (있으면).

## Limitations

- 저자가 밝힌 한계 + 리뷰어가 본 한계(가정, 비교 조건, 일반화 미검증 등).

## 우리 업무 관점 코멘트

- **RAN1#127 안건 대응: 9.1.1 (Case 0, 공간·주파수 CSI 압축).** 한 줄 결론 1–2문장. 첫 문장은 홈·비교 표에 그대로 나오므로 그것만 읽어도 통하게 (예: "payload별 모델 수를 줄이는 구조라 Case 0 평가에 바로 쓸 수 있다."). 직접 해당이 없으면 `**RAN1#127 안건 대응: 직접 해당 없음.**` + 이유.
- 이어서 재현 난이도, 우리 평가 체계(TR 38.843 가정)와의 차이를 1–3줄.

## 점수 근거

| 항목 | 점수 | 근거 |
|---|---:|---|
| 3GPP 관련성 | 0/15 | 안건 항목과 대응 근거 |
| 게재처 | 0/10 | |
| 채널 모델 | 0/15 | |
| 가정 현실성 | 0/15 | 15에서 감점 항목 나열 |
| Baseline 공정성 | 0/10 | |
| 재현성 | 0/5 | |
| 복잡도 분석 | 0/10 | |
| 산업체 저자 | 0/5 | |
| TR 38.843 준수 | 0/15 | |
| **합계** | **0** | |
