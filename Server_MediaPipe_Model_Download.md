# Server MediaPipe Model Download

## 개요

서버 자세 분석 기능은 MediaPipe 포즈 모델 파일을 사용합니다.

이 모델 파일은 현재 저장소에 고정 커밋하지 않고, **서버 실행 중 필요할 때 로컬에 다운로드**되도록 구성되어 있습니다.

---

## 다운로드 대상

- 파일명: `pose_landmarker_lite.task`
- 용도: 서버 MediaPipe 자세 분석 모델

---

## 저장 위치

모델은 아래 경로에 저장됩니다.

```text
backend/models/pose_landmarker_lite.task
```

이 경로는 `.gitignore`에 포함되어 있으므로 Git 추적 대상이 아닙니다.

---

## 다운로드 시점

서버에서 MediaPipe 포즈 분석기가 처음 필요해질 때 다운로드됩니다.

즉, 예를 들면:

- 서버 분석 모드에서 첫 자세 분석 요청이 들어올 때
- 로컬에 모델 파일이 아직 없을 때

이미 파일이 존재하면 다시 다운로드하지 않습니다.

---

## 다운로드를 수행하는 코드 위치

현재 다운로드 로직은 아래 파일에 있습니다.

- [posture_service.py](/D:/dev/pythonapp/ai_interview_new/backend/app/services/posture_service.py)

핵심 동작:

1. `backend/models/pose_landmarker_lite.task` 파일 존재 여부 확인
2. 없으면 모델 디렉터리 생성
3. MediaPipe 모델 URL에서 파일 다운로드
4. 이후 서버 분석기 초기화에 사용

---

## 왜 Git에서 제외하는가

이 파일은 다음 이유로 생성 산출물로 취급합니다.

- 파일 크기가 비교적 큼
- 코드가 아니라 런타임 의존 산출물임
- 필요 시 자동 다운로드 가능
- 저장소 이력을 불필요하게 무겁게 만들 수 있음

---

## 운영 시 참고

- 서버를 처음 실행한 직후 첫 분석 요청에서는 모델 다운로드 때문에 초기 지연이 생길 수 있습니다.
- 네트워크가 막혀 있으면 첫 다운로드에 실패할 수 있습니다.
- 오프라인 배포가 필요하면 이 파일을 사전에 해당 경로에 배치하면 됩니다.

---

## 한 줄 정리

서버 MediaPipe 모델은 `backend/models/pose_landmarker_lite.task`에 런타임 중 자동 다운로드되며, 생성 산출물이므로 Git에는 포함하지 않습니다.
