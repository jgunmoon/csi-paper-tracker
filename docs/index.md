---
title: 홈
hide: [navigation]
---

# NR/6G CSI Tracker

<p class="csi-subtitle">arXiv 논문 리뷰 · 3GPP RAN1 Tdoc 요약</p>

NR/6G **CSI 압축·예측·획득** 논문과 **3GPP RAN1 논의**를 함께 추적하는 팀 트래커입니다.

<!-- home:latest -->
<!-- 위 줄은 빌드할 때 scripts/gen_pages.py 가 현황·최근 추가 논문·최신 RAN1 요약으로 바꿉니다. -->

## 바로 가기

<div class="grid cards" markdown>

- **[비교 표](compare.md)** — 지표 · 채널 모델 · 압축률 · 성능 · 3GPP 안건을 한 표에서 비교. 태그·안건·기간·점수로 거르고, 고른 조건은 **링크 복사**로 공유
- **[3GPP Tdoc 요약](tdocs/index.md)** — RAN1 안건 × 회의 지도, 합의 흐름, 업체 입장, 평가 결과 ([업체별 입장](tdocs/companies.md))
- **[전체 논문](papers/index.md)** — 최근 제출 순 목록
- **[태그](tags.md)** — compression / prediction, AI / non-AI, NR / 6G 별 목록
- **[점수 기준](rubric.md)** — 3GPP 관련성과 신뢰도 100점 rubric

</div>

## 읽는 법

- 점수 색: <span class="csi-score csi-score--high">70+</span> 근거가 탄탄하고 바로 참고할 만함 ·
  <span class="csi-score csi-score--mid">50–69</span> 아이디어는 유용하나 가정/비교 확인 필요 ·
  <span class="csi-score csi-score--low">&lt;50</span> 참고용
- **3GPP 관련성**: 각 논문을 최신 RAN1 회의 안건(예: Rel-20 NR AI/ML 9.1.1 *Case 0*, 6GR 10.5.3 CSI 획득)에 대응시킵니다. 11–15점은 현재 안건과 직접 관련, 7점은 NR/6G CSI 일반입니다.
- `≈` 가 붙은 수치는 논문 **그래프에서 읽은 값**입니다. 표·본문 값은 출처(Table/Fig. 번호)와 함께 그대로 적습니다.
- ⚠️ **abstract only** 표시는 전문을 읽지 못해 초록만으로 요약·채점한 논문입니다.

## 갱신 방법

- **논문**: 매주 월요일 Claude 예약 작업이 arXiv에서 새 논문을 찾아 요약하고 PR을 엽니다.
- **3GPP Tdoc 요약**: RAN1 회의가 끝난 뒤 Claude Code의 `/ran1-tdoc-review`로 정리합니다.
- PR이 main에 병합되면 이 사이트가 자동으로 다시 배포됩니다. 자세한 내용은 [저장소 README](https://github.com/jgunmoon/csi-paper-tracker#readme)를 보세요.
