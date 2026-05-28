# 🔍 Crack Detection Web Application

## 📌 프로젝트 소개
YOLOv8 기반 이미지 균열(Crack) 탐지 웹 애플리케이션입니다.
이미지를 업로드하면 AI가 균열 여부를 자동으로 탐지합니다.

## 🛠 기술 스택
- Python
- Flask
- YOLOv8 (Ultralytics)
- HTML/CSS

## 📂 프로젝트 구조
\```
crack/
├── common/       # 공통 모듈
├── domain/       # 도메인 로직
├── service/      # 서비스 레이어
├── templates/    # HTML 템플릿
├── uploads/      # 업로드 이미지
├── app.py        # Flask 메인 앱
├── main.py       # 실행 파일
└── best.pt       # YOLOv8 학습 모델
\```

## ⚙️ 실행 방법
pip install -r requirements.txt
python app.py

## 📊 주요 기능
- 이미지 업로드
- YOLOv8 모델로 균열 탐지
- 탐지 결과 화면 출력
