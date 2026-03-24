# 나라장터 입찰공고 Slack 알림

나라장터(g2b.go.kr) 입찰공고 중 지정한 키워드(AND 조건)와 매칭되는 공고를 **매일 오전 10시** Slack으로 알림 전송하는 자동화 시스템입니다.

## 초기 설정

### 1. GitHub Secrets 등록

저장소 → Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 설명 |
|-------------|------|
| `G2B_API_KEY` | [data.go.kr](https://www.data.go.kr)에서 발급받은 나라장터 입찰공고정보서비스 인증키 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

### 2. `seen-bids` 라벨 생성

저장소 → Issues → Labels → New label → Name: `seen-bids` → Create label

### 3. 키워드 설정

`keywords.txt` 파일을 수정하세요. 한 줄에 키워드 하나, `#`은 주석입니다.

```
# 원하는 키워드를 입력하세요
제주
AI
```

**AND 조건:** 모든 키워드가 공고명에 포함된 경우에만 알림이 전송됩니다.

## 사용 방법

### 자동 실행

매일 오전 10시(KST)에 자동으로 실행됩니다.

### 수동 실행 (테스트)

Actions 탭 → 나라장터 입찰공고 알림 → Run workflow

### 키워드 변경

`keywords.txt` 파일을 GitHub에서 직접 수정하면 다음 실행부터 반영됩니다.

## Slack 알림 예시

```
🔔 나라장터 입찰공고 알림 [2026-03-24]

📌 제주 AI 시스템 구축 용역 (제주특별자치도)
   • 공고번호: 20260324001
   • 입찰방식: 일반경쟁
   • 마감일: 2026-04-07
   • 🔗 공고 바로가기

총 1건 새 공고 매칭
```

## 파일 구조

```
├── checker.py          # 메인 실행 스크립트
├── keywords.py         # 키워드 로드 및 AND 매칭
├── g2b_api.py          # 나라장터 Open API 클라이언트
├── github_issue.py     # seen 목록 관리 (중복 방지)
├── slack_notifier.py   # Slack 알림 전송
├── keywords.txt        # 키워드 목록 (수정 가능)
└── .github/workflows/
    └── check_bids.yml  # GitHub Actions 워크플로우
```
