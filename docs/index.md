---
title: 홈
hide: [navigation]
---

# CSI Paper Tracker

NR/6G **CSI compression(feedback)** 과 **CSI prediction(channel aging)** 관련 arXiv 신규 논문을 주기적으로 찾아
key idea와 시뮬레이션 결과를 요약하고, 신뢰도/효용 점수를 매겨 모아 두는 팀 트래커입니다.

<div class="grid cards" markdown>

- **[비교 표](compare.md)** — 지표 · 채널 모델 · 압축률 · 성능을 한 표에서 비교, 태그로 필터
- **[태그](tags.md)** — compression / prediction, AI / non-AI, NR / 6G 별 목록
- **[전체 논문](papers/index.md)** — 최근 제출 순 목록
- **[점수 기준](rubric.md)** — 100점 만점 rubric과 읽는 법

</div>

## 읽는 법

- 점수 색: <span class="csi-score csi-score--high">70+</span> 근거가 탄탄하고 바로 참고할 만함 ·
  <span class="csi-score csi-score--mid">50–69</span> 아이디어는 유용하나 가정/비교 확인 필요 ·
  <span class="csi-score csi-score--low">&lt;50</span> 참고용
- `≈` 가 붙은 수치는 논문 **그래프에서 읽은 값**입니다. 표·본문 값은 출처(Table/Fig. 번호)와 함께 그대로 적습니다.
- ⚠️ **abstract only** 표시는 전문을 읽지 못해 초록만으로 요약·채점한 논문입니다.

## 갱신 방법

새 논문은 Claude Code skill `csi-paper-review` 가 찾아서 `papers/<arxiv-id>.md` 로 추가하고 PR을 엽니다.
PR이 main에 병합되면 이 사이트가 자동으로 다시 배포됩니다. 자세한 사용법은 저장소 README를 보세요.
