# NR/6G CSI Tracker

**arXiv 논문 리뷰 · 3GPP RAN1 Tdoc 요약** (저장소 이름: `csi-paper-tracker`)

NR/6G **CSI compression(feedback)·prediction·acquisition** 관련 arXiv 신규 논문을 주기적으로 찾아 key idea와 시뮬레이션 결과를 요약하고,
**현재 3GPP RAN1 안건과의 관련성**과 신뢰도를 점수로 매겨 팀이 함께 보는 트래커입니다.
관련 RAN1 안건은 회의마다 Tdoc(합의 사항, 업체별 입장, 평가 결과)을 안건별로 요약해 논문과 연결합니다.

- 사이트: https://jgunmoon.github.io/csi-paper-tracker/ (main에 병합되면 GitHub Actions가 배포)
- 논문 1편 = `papers/<arxiv-id>.md` 1파일. 사이트의 논문 페이지, 비교 표, 태그 목록은 모두 이 파일에서 만들어집니다.

## Claude와 GitHub는 각각 무엇을 하나

| 누가 | 비유 | 하는 일 |
|---|---|---|
| **Claude** (claude.ai 예약 작업 / Claude Code) | 연구원 | 논문 찾기, **관련성 판단**(3GPP 안건 대응), 읽기, 그래프 수치 읽기, 채점, 요약, 코멘트 → 커밋하고 PR 제출 |
| **GitHub 저장소** | 업무 매뉴얼 + 도구함 + 보관함 | Claude가 따를 지침과 도구, 지금까지의 결과물을 보관 |
| **GitHub Actions / Pages** | 검사·게시 기계 | PR 자동 검사, main 병합 시 사이트 자동 배포 (Claude를 부르지 않음) |
| **사람(팀)** | 팀장 | PR을 보고 **병합** = 승인 |

### Claude가 하는 일

- **매주 자동 수집**: 월요일 08:00(KST)에 claude.ai 예약 작업이 클라우드 세션을 새로 시작합니다. 실행 위치는 Anthropic 클라우드이고 GitHub가 아닙니다.
- **실행 과정**: 저장소를 받아 `.claude/skills/csi-paper-review/SKILL.md` 절차대로 일합니다.
  - 판단이 필요한 부분(관련성, 채점, 요약)은 Claude가 직접 합니다.
  - 반복 작업(검색, 다운로드, 그림 캡처, 형식 검사)은 `scripts/`의 도구를 실행해서 합니다.
- **결과 제출**: 결과는 항상 PR로 냅니다. main에 직접 넣지 않습니다.
- **3GPP Tdoc 요약**: 예약 작업이 아닙니다. RAN1 회의가 끝난 뒤 Claude Code에서 `/ran1-tdoc-review`로 요청할 때만 실행됩니다.

### GitHub 저장소 파일의 역할

예약 작업 세션은 매번 **기억 없이 새로** 시작합니다. 그래서 "어떻게 일할지"와 "지금까지 한 일"을 저장소에 두고, Claude가 매주 저장소를 받아 이어서 일합니다.

| 파일 | 역할 | 비유 |
|---|---|---|
| `.claude/skills/*/SKILL.md` | 작업 절차·채점 기준 | 업무 매뉴얼 |
| `scripts/` | arXiv 검색, 원문·그림 받기, 3GPP 안건·Tdoc 받기, 형식 검사, 사이트 페이지 생성 (판단 없는 반복 작업) | 도구함 |
| `config/` | 검색 키워드, 제외 목록, RAN1 안건 스냅샷 | 설정표 |
| `papers/`, `tdocs/` | 논문 요약, Tdoc 요약 | 결과물 보관함 |
| `docs/`, `mkdocs.yml` | 사이트 틀(메뉴·디자인) | 게시판 양식 |
| `.github/workflows/pages.yml` | Actions의 검사·배포 지시 | 게시 기계 설정 |

이렇게 하면 다음이 가능합니다.
- **같은 방식 유지**: 매주 같은 절차와 기준으로 일합니다.
- **중복 방지**: `papers/`에 이미 있는 논문은 다시 찾지 않습니다.
- **지침 수정 반영**: 팀이 SKILL.md나 `config/search.yaml`을 고치면 다음 실행부터 Claude의 방식이 바뀝니다.

### GitHub가 하는 일 (Claude 없이 자동)

1. **보관**: 모든 변경 이력(누가, 언제, 무엇을)
2. **검토 창구(PR)**: Claude의 결과물이 바로 사이트에 오르지 않고 사람이 병합해야 반영됩니다.
3. **자동 검사(Actions)**: PR마다 `validate_papers.py`와 `mkdocs build --strict`를 실행합니다.
4. **자동 배포(Pages)**: main에 병합되면 사이트를 다시 만들어 게시합니다. 페이지 하단의 "마지막 업데이트" 시각이 이때 찍힙니다.

Actions는 정해진 스크립트만 실행하고 Claude를 호출하지 않으므로 Claude 사용량과 무관합니다.

### 사람이 꼭 해야 하는 일: PR 병합

"병합"은 PR 페이지 아래쪽의 **Merge pull request → Confirm merge** 두 버튼을 차례로 누르는 것입니다. 두 번째 버튼까지 눌러야 완료되고, PR 상태가 보라색 **Merged**로 바뀝니다.
이 저장소는 별도 승인 리뷰(Approve)를 요구하지 않으므로 병합이 곧 승인입니다.

- 병합 전에 확인할 것: PR 본문의 점수표, 추가된 요약, 자동 검사 결과(초록색 체크)
- 빼고 싶은 논문이 있으면 병합 전에 Claude에게 "이 논문 빼 줘"라고 요청합니다. 파일 삭제와 제외 목록 추가를 함께 처리합니다.
- 병합하지 않은 PR의 내용은 사이트에 나타나지 않습니다.

### 매주 흐름

```
[월 08:00] Claude 예약 작업 시작 (claude.ai)
   │  저장소를 받아 SKILL.md(매뉴얼)를 읽음
   │  scripts로 검색·다운로드 → Claude가 판단·채점·요약
   │  papers/에 파일 추가 → PR 제출
   ▼
[GitHub] PR 자동 검사 (Actions)
   ▼
[사람] PR 확인 → Merge pull request → Confirm merge
   ▼
[GitHub] main 반영 → 사이트 자동 재배포 (Pages)
```

## 구조

```
.claude/skills/csi-paper-review/
  SKILL.md          Claude Code skill: 검색 → 선별 → 채점 → 요약 → 검증 → PR 절차와 점수 기준(rubric)
  template.md       papers/<id>.md 양식
config/search.yaml  arXiv 검색 카테고리·키워드, Wi-Fi 센싱 걸러내기, RAN1 안건 선택 용어 (코드 수정 없이 여기서 조정)
config/ran1_agenda/ RAN1 회의별 CSI/MIMO/AI 안건 스냅샷 (scripts/ran1_agenda.py 가 생성)
tdocs/RAN1_<회의>/  RAN1 회의 × 안건별 Tdoc 요약 (합의 흐름, 업체 입장, 평가 결과)
.claude/skills/ran1-tdoc-review/  RAN1 Tdoc 요약 skill
config/excluded.yaml  검토 후 일부러 뺀 논문 ID와 이유 (다음 검색에서 다시 올라오지 않음)
scripts/
  ran1_agenda.py    3GPP FTP에서 최신 RAN1 agenda.csv를 받아 CSI/MIMO/AI 항목을 스냅샷으로 저장
  ran1_tdocs.py     RAN1 Tdoc 목록(xlsx)·Tdoc 다운로드·docx 텍스트 추출·의장 노트·합의 블록 추출
  arxiv_search.py   최근 N주 신규 논문 검색, papers/·제외 목록에 있는 ID 제외 → 후보 JSON
  fetch_fulltext.py arXiv HTML(없으면 PDF) 전문을 텍스트로 저장, 실패 시 exit 2 (= abstract only)
  fetch_figures.js  arXiv HTML의 그림을 PNG로 렌더링 (그래프 수치를 ≈ 로 읽기 위함, Node + Playwright)
  validate_papers.py front matter 스키마·점수 합계·태그·본문 섹션 검사
  paper_schema.py   rubric 배점·태그 목록 (validate와 사이트 생성이 공유)
  gen_pages.py      사이트 빌드 시 논문 페이지·비교 표·점수 기준·내비게이션 생성 (커밋되는 산출물 없음)
papers/             논문 요약 파일
docs/               사이트 고정 페이지(홈, 태그)와 CSS/JS
mkdocs.yml          MkDocs Material 설정
.github/workflows/pages.yml  PR: 검증+빌드 / main: 검증+빌드+Pages 배포
```

## 처음 설정 (한 번)

1. **GitHub Pages 켜기**: 저장소 Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 선택.
2. 로컬에서 사이트를 보려면:
   ```bash
   pip install -r requirements.txt
   mkdocs serve            # http://127.0.0.1:8000
   ```
3. Claude Code 클라우드 세션에서 skill을 돌릴 경우, 환경의 네트워크 허용 목록에 `export.arxiv.org`, `arxiv.org` 가 있어야 합니다.

## 새 논문 추가: Claude Code skill (권장)

저장소를 연 Claude Code에서:

```
/csi-paper-review                     # 기본: 최근 2주, 상위 8편
/csi-paper-review weeks=4 top=3
/csi-paper-review --dry-run           # 후보·점수표만 보고 파일/PR은 만들지 않음
/csi-paper-review --ids 2611.04224    # 특정 논문만 (재처리 포함)
```

자연어로 "최근 2주 CSI 논문 리뷰 돌려줘" 라고 해도 됩니다. skill이 하는 일:

0. 3GPP FTP에서 최신 RAN1 회의 안건을 받아 CSI·MIMO·AI 항목을 이번 실행의 기준으로 삼습니다.
1. `config/search.yaml` 키워드로 arXiv(eess.SP, cs.IT, cs.LG)를 검색하고, `papers/`에 이미 있거나 `config/excluded.yaml`에 있는 arXiv ID는 건너뜁니다.
2. 초록으로 **3GPP 관련성 등급**(안건 항목과 직접 일치 15 / 관련 11 / NR·6G CSI 일반 7 / 셀룰러 아님 0)을 정하고,
   0등급은 제외합니다. 예비 점수 상위 2×top 편의 전문을 읽습니다.
3. rubric(3GPP 관련성 15, 게재처 10, 채널 모델 15, 가정 현실성 15, baseline 공정성 10, 재현성 5, 복잡도 10, 산업체 저자 5, TR 38.843 준수 15; 100점)으로 채점합니다.
4. 상위 top 편만 `papers/<id>.md`로 작성합니다. 그래프에서 읽은 수치는 `≈`, 전문을 못 읽은 논문은 `abstract only`로 표시합니다.
5. `validate_papers.py`와 `mkdocs build --strict`가 통과하면 `papers/<날짜>` 브랜치에 커밋하고 **PR**을 엽니다 (main 직접 push 금지).
   PR 본문에는 요약하지 않은 후보까지 포함한 전체 점수표가 들어갑니다.

PR을 검토(점수·요약 수정 가능)한 뒤 병합하면 사이트가 갱신됩니다.

## 새 논문 추가: 수동 실행 (Claude 없이)

```bash
pip install -r requirements.txt
WORK=$(mktemp -d)

# 0) 현재 RAN1 안건 갱신 (config/ran1_agenda/RAN1_<회의>.json)
python scripts/ran1_agenda.py

# 1) 후보 검색 (최근 2주). papers/에 있는 ID는 자동 제외
python scripts/arxiv_search.py --weeks 2 --out $WORK/candidates.json
#    특정 ID만: python scripts/arxiv_search.py --ids 2611.04224 --out $WORK/candidates.json

# 2) 읽을 논문의 전문 텍스트 받기 (exit 2면 전문 없음 → abstract only로 작성)
python scripts/fetch_fulltext.py 2611.04224 --out-dir $WORK/fulltext

#    결과 그림을 PNG로 받아 그래프 값을 읽기 (Node + Playwright 필요:
#    npm install playwright && npx playwright install chromium)
node scripts/fetch_figures.js 2611.04224 --out-dir $WORK/figs --match "Fig. 3:"

# 3) 양식을 복사해서 작성
cp .claude/skills/csi-paper-review/template.md papers/2611.04224.md
#    점수 기준은 SKILL.md의 rubric 표 (사이트 '점수 기준' 페이지와 같음)

# 4) 검증
python scripts/validate_papers.py
mkdocs build --strict

# 5) 브랜치 → PR
git switch -c papers/$(date +%F) origin/main
git add papers/ config/ran1_agenda/ && git commit -m "papers: add <N> CSI papers ($(date +%F))"
git push -u origin papers/$(date +%F)      # 이후 GitHub에서 PR 생성
```

## 3GPP Tdoc 요약 (RAN1 회의마다)

사이트의 **3GPP Tdoc** 메뉴는 RAN1 회의마다 트래커와 관련된 안건을 정리합니다. 안건마다 파일 1개이며 구성은 이렇습니다.
지금까지의 합의 흐름(이전 회의) → 이번 회의 합의 사항 → 남은 쟁점 → 업체별 입장 표 → 평가 결과 표 → 우리 업무 관점 코멘트.
같은 안건에 대응된 논문의 비교 표·논문 페이지에는 "Tdoc 요약" 링크가 걸립니다.

현재 정리된 것: **RAN1#127** 9.1.1(Case 0 CSI 압축), 9.1.2(업체 간 학습 협업), 9.2(NR MIMO Phase 6), 10.5.3.1(6GR 하향링크 CSI 획득), 10.5.3.2(6GR 상향링크·SRS 기반 CSI 획득). 합의 흐름에는 #125, #126, #126bis를 포함했습니다.

사이트 모든 페이지 아래쪽(footer)에 **마지막 업데이트 일시(KST)**와 논문·Tdoc 요약 개수가 표시됩니다. 값은 사이트를 빌드·배포한 시각입니다.

RAN1 회의가 끝나고 의장 노트(eom)가 올라오면 Claude Code에서:

```
/ran1-tdoc-review meeting=128 agenda=9.1.1,9.1.2,9.2,10.5.3.1,10.5.3.2 history=127
```

수동으로 자료만 모으려면:

```bash
WORK=$(mktemp -d)
python scripts/ran1_tdocs.py list  --meeting 127 --agenda 9.1.1 --cache $WORK --json $WORK/list.json
python scripts/ran1_tdocs.py fetch --meeting 127 --out-dir $WORK/docs R1-2609130 R1-2610445
python scripts/ran1_tdocs.py chair --meeting 127 --out-dir $WORK/chair
python scripts/ran1_tdocs.py agreements $WORK/chair/chair_notes_RAN1_127.txt \
    --start "CSI spatial/frequency compression without temporal aspects" --end "Inter-vendor training collaboration"
```

## 주기 실행

| 방법 | 설정 | 비고 |
|---|---|---|
| **수동 (현재 기본)** | 매주 누군가 `/csi-paper-review` 실행 | PR 검토와 함께 하기 좋음 |
| Claude Code 예약 작업 | Claude Code(클라우드) 세션에서 "매주 월요일 오전에 이 저장소에서 `/csi-paper-review weeks=1` 실행하는 예약 작업 만들어줘" | 해당 클라우드 환경에 arXiv 호스트 허용 필요. 결과는 PR로 옴 |
| GitHub Actions + Claude | 아래 예시 워크플로를 `.github/workflows/weekly-review.yml`로 추가, 저장소 secret `ANTHROPIC_API_KEY` 등록 | API 사용료 발생. 예시는 이 저장소에서 실행 검증하지 않았음 |

GitHub Actions 예시 (Claude Code GitHub Action 사용; 최신 입력 이름은 [action 문서](https://github.com/anthropics/claude-code-action)에서 확인):

```yaml
name: Weekly CSI paper review
on:
  schedule: [{cron: "17 23 * * 0"}]   # 매주 월 08:17 KST
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -r requirements.txt
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "/csi-paper-review weeks=1"
```

## 점수 기준·검색 조건 바꾸기

- **검색 키워드/카테고리**: `config/search.yaml`
- **RAN1 안건 기준**: 매 실행마다 자동 갱신됩니다. 어떤 안건 항목을 고를지는 `config/search.yaml` 의 `ran1_agenda.terms` 로 조정합니다.
- **제외 목록**: `config/excluded.yaml`. PR 검토 중 논문을 빼면 `papers/<id>.md` 를 지우고 여기에 `id`, `reason`, `date` 를 추가합니다.
  다시 검토하고 싶으면 항목을 지우면 됩니다. `validate_papers.py` 는 제외 목록과 `papers/` 가 겹치면 실패합니다.
- **rubric**: `.claude/skills/csi-paper-review/SKILL.md` 의 `rubric:start`–`rubric:end` 구간. 배점을 바꾸면 `scripts/paper_schema.py` 의 `RUBRIC` 도 같이 고칩니다.
  사이트의 '점수 기준' 페이지는 SKILL.md에서 자동으로 가져옵니다.
- **태그 종류**: `scripts/paper_schema.py` 의 `TAG_GROUPS` (현재 compression/prediction, AI/non-AI, NR/6G)

## 논문 파일 형식

front matter 필수 키: `arxiv_id, title, authors, affiliation, venue, date, link, tags, read_level, reviewed, score, score_breakdown, metrics, channel_model, compression_ratio, headline_result, ran1_meeting, ran1_agenda`

본문 필수 섹션: `Key idea / System model / Simulation setup / Results (baseline 대비) / Limitations / 우리 업무 관점 코멘트 / 점수 근거`

사이트에서 논문 페이지 맨 위 **결론 박스**는 따로 적지 않고 기존 내용에서 만들어집니다.

| 박스 줄 | 가져오는 곳 |
|---|---|
| 점수 · 3GPP 관련성 | `score`, `score_breakdown.standard` |
| 3GPP 안건 | `ran1_meeting`, `ran1_agenda` (Tdoc 요약이 있으면 링크) |
| 핵심 결과 | `headline_result` |
| 우리 업무 관점 | "우리 업무 관점 코멘트"의 첫 bullet (굵은 `RAN1#… 안건 대응: …` 머리말 제외). 첫 문장은 홈·비교 표에도 나옴 |

항목별 점수는 본문 `## 점수 근거` 표로 보여 주므로, 표의 `n/배점` 값은 `score_breakdown` 과 같아야 합니다 (`validate_papers.py` 가 확인).

자세한 양식은 `.claude/skills/csi-paper-review/template.md` 를 보세요.
