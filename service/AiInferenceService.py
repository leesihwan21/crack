import cv2
import os
from ultralytics import YOLO

def process_video_ai(video_path, user_id, analysis_status):
    """
    비디오 파일을 (영상) 분서가여 도로 결함을 탐지하고 실시간 상태를 업데이트 하는 로직.
    :param video_path:
    :param user_id:
    :param analysis_status:
    :return:
    """
    try:
        # 1. 모델 로드
        model_path = r'C:\Users\lsh8389\Desktop\ITS-Guard_Project\best.pt'
        model = YOLO(model_path)

        # 2. 비디오 캡쳐 객체 생성
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            analysis_status[user_id] = {'percent': 0,
                                        'message': '오류: 영상을 열 수 없다.'}

            return

        # 3. 영상 정보 추출
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps if fps > 0 else 0

        current_sec = 0
        total_detections = 0
        all_results = [] # 탐지된 상세 데이터 저장용

        # 4. 1초에 1프레임씩 점프하며 분석 루프
        while current_sec < duration_sec:
            # 밀리초(ms) 단위로 이동 (1초 = 1000ms)
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_sec * 1000)
            success, frame = cap.read()

            if not success:
                break

            # 고해상도 정제 모델로 추론 실행 (conf 설정으로 정확도 조절)
            results = model.predict(source=frame, conf=0.5, verbose=False)

            # 탐지 결과 처리
            for box in results[0].boxes:
                total_detections += 1
                cls_id = int(box.cls[0].item())
                label = model.names[cls_id]
                conf = float(box.conf[0].item())

                # 상세 결과 기록 (나중에 DB 저장시 활용)
                all_results.append({
                    'time':current_sec,
                    'label':label,
                    'confidence':conf
                })

            # 5. [중요] 실시간 상태 업데이트 (50~100% 구간)
            progress = 50 + int((current_sec / duration_sec) * 50)
            analysis_status[user_id] = {
                'percent': progress,
                'message':f'{int(current_sec)}초 지점 분석 중... (탐지 : {total_detections}건'
            }

            # 다음 1초 단위로 점프 로직.
            current_sec += 1

        # 6. 분석 종료 및 최종 상태 업데이트
        cap.release()
        analysis_status[user_id] = {
            'percent': 100,
            'message':f'분석완료! 총 {total_detections}개의 결함이 탐지되었습니다.'
        }

        # 여기서 DB 업데이트 함수를 호출하거나 결과를 반환할 수 있음.
        print(f"---[User:{user_id}] 분석 종료: 총 {total_detections}건 탐지---")
        return all_results

    except Exception as e:
        print(f"AI 분석 중 에러 발생 : {e}")
        analysis_status[user_id] = {'percent': 0,
                                    'message':f'에러발생:{str(e)}'}
        return None
    finally:
        cv2.destroyAllWindows()