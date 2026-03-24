# 프로젝트 회고: 나라장터 Slack 알림 봇

**날짜:** 2026-03-24

---

## 진행한 내용
1차 아이디어: 나라장터 API를 사용해서 키워드에 매칭되는 공고들을 슬랙으로 받기 
Incoming Webhook 이용해 단방향으로 슬랙에 전송

수정: 슬랙 개별 DM으로 테스트 해보려고 하니 Incoming Webhook 로는 안되고 봇을 만들어야 함 

2차 아이디어: 봇을 만든김에 단방향이 아닌 양방향으로 원하는 키워드를 입력해서 자료를 받을 수 있게 함 
서비스 플로우: Slack → Cloudflare → GitHub Actions → Python → G2B API → Slack

문제: 서비스들에 익숙치 않아서 메뉴 위치 부터 api key를 어떻게 발행해야하는지도 몰라 화면을 캡쳐하면서 진행함
계속해서 오류가 발생하는데 그냥 다 물어봄.. 시간이 좀 걸리긴 하지만 완성이 되긴 하는 것 같음 


이후 진행: 슬랙은 관리자에 봇 승인을 받아야해서 아직 제대로 나오는지 확인은 못함 
그리고 뭔가 더 간단하고 쉬운 방법이 있을 것 같아서 코드를 새 채팅이나 다른 AI로 다시 확인을 해보려고 함 
Cloudflare를 꼭 사용해서 진행해야하는건가?? 



### 1단계: G2B API 디버깅
- 나라장터 API 호출 시 HTTP 404 오류 발생
- GitHub Actions에서 `checker.py` 실행 실패

### 2단계: Slack 슬래시 커맨드 설계 및 구현
- `/나라장터 [키워드]` 기능 설계
- `slack_notifier.py` — 10건 제한, 헤더 분기, 더보기 링크
- `checker.py` — 수동/스케줄 모드 분기
- `check_bids.yml` — workflow_dispatch inputs 추가
- `cloudflare-worker/worker.js` — Slack 서명 검증, GitHub 트리거

### 3단계: Cloudflare Worker 배포 및 설정
- Worker 생성, 코드 배포, Secrets 등록 (GH_PAT, SLACK_SIGNING_SECRET)

---

## 발생한 문제들

| 문제 | 원인 | 해결 |
|------|------|------|
| G2B API 404 | 오퍼레이션명 오타 (`getBidPblancListInfoServc01`) | 올바른 엔드포인트로 수정 |
| G2B API 404 (2차) | `inqryDiv=1` 파라미터 누락 + API키 이중인코딩 | 파라미터 추가, `unquote()` 처리 |
| Python 실행 안됨 | Windows Microsoft Store 스텁 충돌 | `uv.exe` 직접 경로 사용 |
| 한글 출력 깨짐 | Windows cp949 인코딩 | `PYTHONIOENCODING=utf-8` 설정 |
| Cloudflare Worker 생성 실패 | 이메일 인증(verify) 미완료 | 이메일 인증 후 해결 |
| Worker 이름 입력 불가 | 인증 미완료로 인한 UI 오작동 | 인증 후 정상화 |

---

## 다음에 같은 실수를 하지 않으려면

**API 연동 시:**
- 공식 문서에서 파라미터 필수값 먼저 확인
- API키 인코딩 상태 확인 (이미 인코딩된 키를 다시 인코딩하지 않기)

**새 서비스 가입 시:**
- 이메일 인증 먼저 완료 후 작업 시작

**배포 전:**
- Cloudflare처럼 외부 서비스는 계정 상태(인증, 플랜) 확인 먼저

**개발 환경:**
- Windows에서 Python 경로 명확히 지정 (`uv.exe` 절대경로)
- 한글 사용 시 `PYTHONIOENCODING=utf-8` 기본 설정
