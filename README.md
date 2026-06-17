# ⚡ CRACK — Smart Road Safety Platform

> AI 기반 도로 위험 요소(포트홀·균열·씽크홀) 시민 신고 및 자동 분석 플랫폼
> YOLOv8 객체 탐지 + Flask/SocketIO 실시간 알림 + 관리자 대시보드 + 카카오맵 연동

---

## 📌 프로젝트 소개

시민이 도로 위험 요소(포트홀, 균열, 씽크홀, 도로 시설물 파손)를 사진/동영상으로 신고하면, YOLOv8 AI가 자동으로 분석하여 위험도를 판정하고, 관리자에게 실시간으로 전달되는 **도로 안전 신고-관리 플랫폼**입니다. 단순 이미지 탐지 데모가 아니라, 신고 접수부터 AI 검증, 중복신고 그룹화, 관리자 처리, 시민 피드백까지 이어지는 전체 워크플로우를 구현했습니다.

**핵심 특징:**
- YOLOv8 기반 5종 클래스 탐지: `Pothole_Damage`, `Major_Crack`, `Minor_Crack`, `Road_Asset`, `Sinkhole`
- AI-Hub 공공 도로손상 데이터(21.5만 장) 기반 학습 + Roboflow 씽크홀 데이터 추가 파인튜닝(전이학습)
- 이미지뿐 아니라 **동영상 프레임 단위 분석**(자동차 주행 영상에서 프레임별 탐지 후 결과 영상 재생성)
- AI 신뢰도 기반 **자동 신고 검증/반려 로직** (포트홀 신뢰도 60% 이상 / 단일 프레임 3개 이상 / 씽크홀 1개 이상 시에만 관리자 검토 단계로 승격)
- 위치(GPS)·시간 기반 **중복 신고 자동 그룹화** 및 우선순위(긴급/주의/일반) 산정
- Flask-SocketIO 기반 **관리자 실시간 신규 신고 알림**
- 카카오맵 연동 좌표→주소 역지오코딩
- 관리자 대시보드(신고관리/회원관리/통계), 포인트(크래커 포인트) 시스템, 커뮤니티 게시판(크랙톡, 비속어 자동 필터링), PWA 설치 지원

---

## 👥 Team

**5인 팀 프로젝트** (MBC AIX 2026 미니프로젝트)

| 이름 | 담당 역할 |
|---|---|
| 김수빈 | 프로젝트 제안 배경 및 기대효과 발표 |
| **이시환 (본인)** | 회원가입·로그인·로그아웃 + 마이페이지(회원정보 조회·수정, 활동 포인트 합계 표시) 백엔드 개발 + YOLOv8 모델 학습(씽크홀 데이터셋 추가 파인튜닝) |
| 노형래 | 추후 보완 |
| 이지건 | 관리자/사용자 화면 분리, 위치 기반 사건 조회, 위험도·신고 수 기반 필터링, 주소 검색(지오코딩) 시스템 |
| 김지영 | EXIF 메타데이터 파싱 및 좌표 저장, 위치 기반 중복 제보 클러스터링, YOLOv8 탐지 결과 연동 및 자동 판정 로직, REST API |

---

## 🙋 My Contribution

**1. 회원 인증 및 마이페이지 백엔드**
- 회원가입 / 로그인 / 로그아웃 기능 구현
- 사용자가 본인의 활동(포트홀 제보 내역)을 시각적으로 확인하고 개인정보를 수정할 수 있는 통합 대시보드(마이페이지) 구현
- 세션(Session) 기반 사용자 인증 관리
- Jinja2 템플릿의 조건부 렌더링을 활용해 **조회/수정 모드를 별도 페이지 분리 없이 마이페이지 하나로 통합** — `show_edit` 플래그로 입력창 노출 여부를 제어해 페이지 전환 비용을 줄이고 사용자가 하나의 대시보드 안에서 정보 수정을 끝낼 수 있도록 설계
- 제보(Report) 테이블과 연동해 회원정보 조회 시 **제보 내역과 누적 포인트 합계를 실시간 DB 연동으로 함께 계산·표시**
- 비밀번호 미입력 시 기존 비밀번호를 유지하도록 **조건부 UPDATE 쿼리 분기 처리** — 비밀번호 변경을 원치 않는 사용자가 매번 재입력해야 하는 불편을 제거
- 정보 수정 후 상단 네비게이션 바의 표시 이름이 즉시 갱신되도록 `session['user_name']` 동기화 처리

**2. YOLOv8 모델 학습**
- 백엔드(회원 인증/마이페이지) 개발을 먼저 마친 뒤, 이어서 YOLOv8 모델 학습 작업에 집중
- 초기 학습 결과의 정확도가 만족스럽지 않아, 이후 팀원 전체가 함께 추가 데이터셋을 수집하는 방향으로 전환
- AI-Hub 공공 도로손상 데이터셋(약 21.5만 장)으로 학습된 v5(YOLOv8s, 100 epoch) 모델을 베이스로, Roboflow에서 수집한 씽크홀(Sinkhole) 데이터셋을 추가(팀원 전원이 분담 수집 후 씽크홀이 아닌 이미지는 육안으로 검수해 필터링)하여 v6 파인튜닝(18 epoch, AdamW, batch 32) 진행
- 18종 세부 클래스를 5종 핵심 클래스(Pothole, Major/Minor Crack, Asset, Sinkhole)로 재매핑·단순화
- 팀원들이 각자 학습시킨 여러 모델 버전의 정확도를 비교하여 최종 적용 모델을 선정 (`static/best.pt`, `static/best_merge_v2.pt`는 이 비교 과정에서 나온 서로 다른 실험 결과물)
- 학습 완료된 모델을 산출하여 전달 (Flask 추론 파이프라인 연동 및 자동 판정 로직은 팀원 담당)

---

## 📊 Model Performance

### 버전별 비교 (팀 자체 학습 분석 기록 기준)

| Version | 모델 | 데이터셋 | Epochs | mAP50 | mAP50-95 | Recall | Precision |
|---|---|---|---|---|---|---|---|
| v5 | YOLOv8s | AI-Hub 도로손상 (full_dataset4) | 100 | 0.8688 | 0.6504 | 0.8075 | 0.8296 |
| **v6 (씽크홀 통합)** | YOLOv8s | +Roboflow Sinkhole | 18 (파인튜닝) | **0.9017** | 0.6528 | **0.8484** | 0.8355 |

> v6은 v5 가중치에서 시작한 파인튜닝으로, 21.5만 장 규모의 데이터를 거의 그대로 유지하면서 씽크홀 클래스만 추가 학습했습니다. mAP50 +3.8%p, Recall +4.1%p 개선되어, 미검출(False Negative) 위험을 줄이는 방향으로 개선되었습니다.

### 데이터셋 분할

- 전체 215,278장 (train 193,848장 / val 21,430장, 약 9:1)

### 실제 배포 체크포인트(`static/best.pt`) 확인 수치

| Metric | Score |
|---|---|
| Precision | 0.824 |
| Recall | 0.843 |
| mAP50 | 0.888 |
| mAP50-95 | 0.667 |

> 위 표는 실제 운영 서버가 로드하는 `static/best.pt` 체크포인트에 기록된 최종 학습 메타데이터 기준이며, 팀 분석 자료의 v6 수치와 근소하게 다른 것은 평가에 사용된 체크포인트 시점(epoch) 차이로 보입니다.

---

## 📂 Dataset

- **베이스 데이터셋**: AI-Hub(한국지능정보사회진흥원) 공개 도로손상 데이터. JSON 라벨을 YOLO TXT 포맷으로 정규화 변환, 640×640 리사이즈 전처리
- **추가 데이터셋**: Roboflow에서 수집한 씽크홀(Sinkhole) 이미지. 팀원 전원이 분담 수집 후, 씽크홀이 아닌 이미지는 직접 육안으로 검수하여 제외
- **클래스**: `Pothole_Damage`, `Major_Crack`, `Minor_Crack`, `Road_Asset`, `Sinkhole` (18종 세부 클래스를 5종으로 재매핑)
- **규모**: 총 215,278장 (train 193,848 / val 21,430)
- **학습 환경**: Google Colab (GPU)

---

## 🏗️ Architecture

```
[시민 사용자]
  │ 이미지/동영상 업로드 (포트홀·균열·씽크홀 제보)
  ▼
Flask 웹 서버 (app.py)
  │  ├─ EXIF/비디오 GPS 추출 → 카카오맵 역지오코딩(주소 변환)
  │  └─ 백그라운드 스레드로 YOLOv8 추론 실행
  ▼
YOLOv8 추론 (static/best.pt, 5-class)
  │  ├─ 이미지: 단일 프레임 탐지
  │  └─ 동영상: 프레임 단위 탐지 + 바운딩박스 오버레이 재인코딩
  ▼
AI 자동 검증 로직
  │  (포트홀 신뢰도 ≥60% OR 단일 프레임 포트홀 ≥3개 OR 씽크홀 ≥1개 → 승인)
  ▼
위치·시간 기반 중복 신고 그룹화 + 우선순위(긴급/주의/일반) 산정
  ▼
Flask-SocketIO 실시간 알림 → 관리자 대시보드
  ▼
관리자 처리 (상태 변경/반려/일괄처리) ──▶ 시민에게 처리 현황 피드백

[회원 인증 모듈]               [DB]
사용자 ↔ Flask(세션 인증)  ↔  TiDB Cloud (MySQL 호환, PyMySQL)
```

---

## ✨ 주요 기능 | Key Features

### 인증 / 회원
- 회원가입(이메일·닉네임 검증, 비속어 필터링, 실시간 중복확인) / 로그인 / 로그아웃
- 아이디 찾기 / 비밀번호 찾기·재설정
- 마이페이지(프로필 수정, 알림 설정, 회원탈퇴)
- 크래커 포인트(활동 포인트) 시스템

### 신고(Report) / AI 분석
- 이미지(PNG/JPG/HEIC 등) 및 동영상(MP4/MOV/AVI 등) 업로드, HEIC→JPG·MOV→MP4 자동 변환
- EXIF/비디오 메타데이터 기반 GPS 자동 추출 + 카카오맵 역지오코딩
- YOLOv8 기반 자동 탐지(이미지/동영상 프레임 단위) 및 신뢰도 기반 자동 승인·반려
- 신고 상태 조회 API

### 알림(Alert) / 현황
- 전체 신고 피드(지도/리스트), 신고 상세보기, 본인 신고 수정
- 위치·시간 기반 중복 신고 그룹화 표시(반복 신고 건수)
- 관리자 공지(Notice) 등록, 읽음 처리

### 관리자(Admin)
- 대시보드: 긴급/오늘 접수/미처리/처리중/반려 현황 요약, 우선순위 기준 긴급 신고 리스트
- 신고관리: 목록/그룹 상세/상태 변경/일괄 처리/AI 재분석 요청
- 회원관리: 회원 목록/상세/권한 변경/정지·정지해제
- 통계: 지역별 집계(시/구 단위 정규화)
- 실시간 신규 신고 알림(SocketIO)

### 커뮤니티
- 크랙톡(CrackTalk) 게시판, 부적절 게시물 비속어 필터링(blind 처리)

### 기타
- PWA 설치 지원(manifest.json, Service Worker)
- 자체 발표자료(PPT)를 Flask 라우트로 임베드하여 앱 내에서 직접 열람 가능

---

## 🛠 기술 스택 | Tech Stack

```
Backend     : Python, Flask, Flask-SQLAlchemy, Flask-SocketIO + eventlet
AI/Detection: YOLOv8 (Ultralytics), OpenCV(영상 처리)
Database    : TiDB Cloud (MySQL 호환) via PyMySQL
Auth        : Flask Session 기반, werkzeug.security(비밀번호 해싱)
Media       : Pillow, piexif, exifread, pillow_heif(HEIC), imageio-ffmpeg(영상 변환)
Map         : Kakao Maps JS SDK, 역지오코딩
Realtime    : Flask-SocketIO (관리자 실시간 알림)
Frontend    : Jinja2 Templates, Vanilla JS, PWA(manifest.json, Service Worker)
Training Env: Google Colab (GPU)
```

---

## 📂 프로젝트 구조 | Project Structure

```
crack-main/
├── app.py                  # Flask 메인 앱, AI 분석 스레드, 신고 그룹화/우선순위 로직
├── models.py                # Member, Report, AiResult, VideoDetection, PointLog, Notice, CrackTalk 등
├── database.py / extensions.py
├── utils.py                  # GPS 추출, 역지오코딩, 비속어 필터 등 공통 유틸
├── services/
│   ├── auth_service.py      # 회원가입/로그인/아이디·비밀번호 찾기 (본인 담당)
│   ├── report_service.py    # 신고 업로드, 영상 변환, GPS 추출
│   ├── alert_service.py     # 신고 피드, 그룹 상세, 공지, 읽음 처리
│   ├── status_service.py    # 크랙톡 커뮤니티, 신고 수정/삭제
│   ├── my_service.py        # 마이페이지, 알림 설정, 탈퇴
│   ├── admin_service.py     # 관리자 대시보드/신고관리/회원관리/통계
│   └── region_service.py    # 행정구역 주소 정규화/파싱
├── templates/                # HTML 템플릿 (회원/신고/알림/관리자/PPT 등)
├── static/
│   ├── best.pt               # 실제 운영 로드 모델 (5-class, mAP50 0.888)
│   ├── best_merge_v2.pt      # 추가 실험 모델 (2-class 병합 버전)
│   └── training_analysis.json # 팀 자체 학습 비교 분석 기록
├── secrets.example/          # .env, 카카오 키, 비속어 사전 예시 파일
└── requirements.txt
```

---

## ⚙️ 설치 및 실행 | Installation & Run

```bash
pip install -r requirements.txt

# secrets.example 참고하여 secrets/ 폴더에 .env, kakao_js_key.txt, profanity.json 구성

python app.py
# → http://127.0.0.1:9100
```

---

## 🖼️ Demo

### 신고 피드 (Alert)
![alert](screenshots/screenshot_alert_framed.png)

### 관리자 대시보드 (Admin)
![admin](screenshots/screenshot_admin_framed.png)

### 신고하기 (Report)
![report](screenshots/screenshot_report_framed.png)

### 마이페이지 (My)
![mypage](screenshots/screenshot_mypage_framed.png)

### 처리 현황 (Status)
![status](screenshots/screenshot_status_framed.png)

---

## ⚠️ 면책조항 | Disclaimer

본 프로젝트는 **교육·포트폴리오 목적**으로 제작되었으며, 실제 지자체 도로 관리 시스템으로 사용된 사례는 아닙니다.

---

## 👤 개발자 | Developer

**이시환 (Sihwan Lee)**
GitHub: [@leesihwan21](https://github.com/leesihwan21)
