---
name: csi-paper-review
description: >
  Find new NR/6G CSI compression·feedback·prediction papers on arXiv (last N weeks),
  skip ones already in papers/, score each for reliability/usefulness, summarize the
  top 5 into papers/<arxiv-id>.md, and open a PR. Use on /csi-paper-review, or when
  asked to "새 CSI 논문 찾아줘", "CSI paper review 돌려줘", "update the paper tracker".
argument-hint: "[weeks=2] [top=5] [--dry-run] [--ids 2511.01234,2511.05678]"
---

# CSI paper review

매 실행마다 **검색 → 중복 제거 → 1차 선별 → 전문 읽기·채점 → 상위 K편 요약 → 검증 → 브랜치/PR** 순서로 진행한다.
절대 `main`에 직접 push하지 않는다.

## 0. 인자

| 인자 | 기본값 | 의미 |
|---|---|---|
| `weeks` | 2 | 오늘 기준 최근 N주 안에 **처음 제출(v1)** 된 논문 |
| `top` | 5 | 요약해서 파일로 남길 편수 |
| `--dry-run` | off | 후보·점수표만 출력, 파일/브랜치/PR 생성 안 함 |
| `--ids` | – | 검색 대신 지정한 arXiv ID만 처리 (검증·재처리용) |

## 1. 검색 (arXiv)

```bash
python scripts/arxiv_search.py --weeks <N> --out /tmp/csi_candidates.json
```

- 스크립트가 arXiv API(`export.arxiv.org/api/query`)로 아래 조건을 조회한다.
  - 카테고리: `eess.SP OR cs.IT OR cs.LG` (cross-list 포함)
  - 키워드(제목/초록, OR): `"CSI compression"`, `"CSI feedback"`, `CsiNet`,
    `"CSI prediction"`, `"channel prediction"`, `"channel aging"`, `"AI/ML CSI"`,
    `"AI-based CSI"`, `"Type II codebook"`, `"eType II"`, `"6G CSI"`,
    `"implicit feedback"`, `"CSI reporting"`, `"two-sided model"`
  - 기간: `submittedDate:[today-N주 TO today]`
- `papers/*.md` 파일명(=arXiv ID, 버전 제외)에 이미 있는 논문은 스크립트가 제외한다.
- 출력: `[{id, title, authors, affiliations?, abstract, categories, comment, journal_ref, published}]`
- arXiv 접근이 막히면(403/타임아웃): WebSearch로 `site:arxiv.org` 검색하여 같은 조건을 수동 적용하고,
  PR 본문에 "API fallback 사용"이라고 적는다.

## 2. 1차 선별 (초록 기준)

후보마다 초록을 읽고 **관련성**을 판정한다. 관련 = 다음 중 하나가 주 기여:
CSI 압축/피드백, CSI·채널 예측(channel aging 포함), 코드북 기반 CSI 보고 개선, AI/ML CSI 평가 방법론.
(단순 channel estimation, sensing, beam management만 다루는 논문은 제외.)

관련 논문에 대해 초록·`comment`·`journal_ref`만으로 **예비 점수**(아래 rubric, 모르는 항목은 0)를 매기고,
상위 `2×top`편(최대 10편)을 2단계로 넘긴다.

## 3. 전문 읽기와 채점

- 순서: `https://arxiv.org/html/<id>` → 실패 시 `https://arxiv.org/pdf/<id>`.
- 둘 다 실패하면 초록만으로 채점하고 **`read_level: abstract-only`**, 본문 맨 위에
  `> ⚠️ abstract only — 전문 미확인` 표시. 근거 없는 항목은 0점 + `?`.
- 각 항목 점수에는 **근거 1줄**(섹션/표/그림 번호)을 남긴다.

### 신뢰도/효용 Rubric (합계 100)

| # | 항목 | 배점 | 기준 |
|---|---|---|---|
| 1 | 게재처 `venue` | 20 | IEEE JSAC / TWC / TCOM / TSP / TIT = 20 · 기타 IEEE/ACM Trans, IEEE WCL/CL = 14 · ICC / Globecom / VTC / PIMRC / WCNC = 12 · 기타 학회·저널 = 8 · arXiv 프리프린트만 = 4 (`comment`/`journal_ref`의 "accepted" 표기 확인) |
| 2 | 채널 모델 `channel` | 15 | 3GPP TR 38.901 CDL/TDL/UMa/UMi (QuaDRiGa, Sionna, SLS 등) = 15 · 실측 데이터 = 13 · 레이트레이싱/DeepMIMO = 10 · COST2100 = 8 · i.i.d. Rayleigh/단순 기하 모델 = 3 |
| 3 | 가정의 현실성 `assumptions` | 15 | 15에서 감점: UE perfect CSI(추정 오차 없음) −4 · 피드백 비트 양자화 없음(float latent) −4 · 이상적 피드백 채널/지연 없음 −2 · 단일 SNR·단일 속도만 −2 · 학습/시험 동일 분포만 −3. 최저 0 |
| 4 | Baseline 공정성 `baselines` | 10 | 3GPP Type I/II/eType II 코드북 비교 +4 · 최신 AI baseline(CsiNet+, CRNet, TransNet 등) +3 · 동일 payload(bits)·동일 데이터셋에서 비교 +3 |
| 5 | 재현성 `reproducibility` | 10 | 시뮬레이션 파라미터 표 +5 · 코드 또는 데이터셋 공개 링크 +5 |
| 6 | 복잡도 분석 `complexity` | 10 | FLOPs/파라미터 수 +5 · UE 측 지연·메모리 또는 encoder/decoder 분리 분석 +5 |
| 7 | 산업체 저자 `industry` | 5 | 통신 장비/칩/사업자 소속 저자(Huawei, Ericsson, Nokia, Samsung, Qualcomm, ZTE, MediaTek, Intel, Apple, NTT DOCOMO, LG 등) 포함 = 5 |
| 8 | TR 38.843 평가 가정 `tr38843` | 15 | SGCS 보고 +4 · NMSE 보고 +2 · payload(bits)별 성능 곡선 +2 · 일반화/스케일러빌리티(시나리오·안테나·대역폭 변경) +3 · 최종 KPI(throughput, SLS/LLS) +2 · 학습 협업 타입(Type 1/2/3)이나 two-sided 모델 배포 논의 +2 |

예측(prediction) 논문은 8번에서 "payload" 대신 **예측 horizon/UE 속도별 성능**을 +2로 본다.

순위: `total` 내림차순, 동점이면 `tr38843` → `channel` 순.

## 4. 요약 파일 작성 (상위 `top`편)

`papers/<arxiv-id>.md` (버전 제외, 예: `papers/2511.01234.md`), 템플릿: `template.md` (이 skill 폴더).

작성 규칙:
- 본문은 **한국어**, 기술 용어·지표명은 영어 그대로.
- **수치 표기**: 표/본문에 적힌 값은 그대로 + 출처 (`Table III`), **그래프에서 읽은 값은 `≈`** + 출처 (`≈ −18 dB, Fig. 5`).
- Results는 반드시 **baseline 대비** 형태 (예: "eType II 대비 동일 payload에서 SGCS +0.06").
- 논문에 없는 정보는 추측하지 말고 `N/A` 또는 `?`.
- "우리 업무 관점 코멘트"는 표준화(Rel-19/20 AI/ML CSI, 6G study) 적용 가능성, 재현 난이도, 우리 평가 체계와의 차이를 2–4줄.

## 5. 검증

```bash
python scripts/validate_papers.py      # front matter 스키마, 점수 합계, ID↔파일명 일치
mkdocs build --strict                  # 사이트 빌드 깨짐 확인
```

둘 다 통과해야 다음 단계로 간다.

## 6. 브랜치 · 커밋 · PR

```bash
git fetch origin main
git switch -c papers/<YYYY-MM-DD> origin/main
git add papers/
git commit -m "papers: add <K> CSI papers (<YYYY-MM-DD>, last <N> weeks)"
git push -u origin papers/<YYYY-MM-DD>
```

PR 제목: `papers: <YYYY-MM-DD> CSI review (<K> papers)`
PR 본문:
1. 실행 조건(weeks, 검색 날짜, 후보 수 / 관련 수 / 중복 제외 수)
2. **전체 후보 점수표** (요약하지 않은 논문 포함: ID, 제목, 예비/최종 점수, 탈락 사유)
3. 추가된 논문 목록과 각 `read_level`
4. 검증 결과

`--dry-run`이면 6단계를 건너뛰고 2번 점수표만 출력한다.
