# Server MediaPipe CPU Delegation

## 요약

현재 이 프로젝트의 서버 환경에서는 GPU 하드웨어가 실제로 존재하더라도, Python 서버에서 사용하는 `mediapipe` 패키지는 GPU delegate를 사용할 수 없습니다.

즉:

- 브라우저(MediaPipe JS)는 GPU 사용 가능성이 있음
- 서버(Python MediaPipe)는 현재 설치된 wheel 기준으로 CPU만 사용 가능

핵심 원인은 GPU가 없어서가 아니라, **설치된 Python용 MediaPipe wheel이 GPU 지원 없이 빌드되어 있기 때문**입니다.

---

## 실제 확인 결과

### 1. 서버 머신에는 GPU가 실제로 존재함

`nvidia-smi` 확인 결과:

- GPU: `NVIDIA GeForce RTX 3060`
- Driver Version: `560.94`
- CUDA Version: `12.6`

즉, 서버 머신 자체에는 GPU가 정상적으로 존재합니다.

### 2. MediaPipe CPU delegate는 정상 동작함

백엔드 가상환경에서 `PoseLandmarker`를 `Delegate.CPU`로 생성했을 때 정상 동작했습니다.

### 3. MediaPipe GPU delegate는 실패함

같은 환경에서 `Delegate.GPU`로 생성했을 때 아래 에러로 실패했습니다.

```text
NotImplementedError
ValidatedGraphConfig Initialization failed.
ImageCloneCalculator: GPU processing is disabled in build flags
ImageCloneCalculator: GPU processing is disabled in build flags
```

이 메시지는 매우 직접적입니다.

의미:

- 현재 설치된 `mediapipe` Python 빌드는 GPU 처리 코드가 포함되지 않음
- 따라서 코드에서 GPU delegate를 요청해도 서버에서는 사용할 수 없음

---

## 왜 이런 일이 발생하는가

서버에서 MediaPipe GPU가 되려면 아래 3가지가 모두 충족되어야 합니다.

1. GPU 하드웨어가 존재해야 함
2. 드라이버/CUDA 등 실행 환경이 맞아야 함
3. **Python용 MediaPipe wheel 자체가 GPU 지원으로 빌드되어 있어야 함**

현재 프로젝트는 1, 2는 충족하지만 3이 충족되지 않습니다.

즉, 다음과 같은 오해가 생기기 쉽습니다.

- "GPU가 있으니 서버 MediaPipe도 당연히 GPU겠지"

하지만 실제로는:

- "GPU가 있어도 Python MediaPipe wheel이 CPU 전용이면 서버 GPU는 불가능"

---

## 기본 설치 wheel은 항상 GPU를 지원하는가

아니요.

실무적으로는 다음처럼 이해하는 것이 안전합니다.

- `pip install mediapipe` 기본 설치 = **우선 CPU 기반이라고 생각하고 시작**
- 특히 Windows + Python 서버 환경에서는 GPU delegate가 빠진 wheel인 경우가 흔함

즉, 기본 설치만으로 서버 GPU까지 자동 지원된다고 보면 안 됩니다.

---

## 이 프로젝트에서의 현재 결론

현재 프로젝트의 서버 분석 모드에서는:

- 서버 MediaPipe CPU: 사용 가능
- 서버 MediaPipe GPU: 사용 불가

따라서 서버 측 `GPU/CPU` 선택 UI를 제공하더라도, 현재 빌드 기준으로는 서버 GPU를 실제 사용하지 못합니다.

---

## 권장 대응

### 단기 대응

사용자 혼란을 줄이기 위해 UI/로그에서 다음을 명확히 표시하는 것이 좋습니다.

- 서버 GPU 버튼 비활성화
- 또는 클릭 시:
  - "현재 서버 MediaPipe 빌드는 GPU를 지원하지 않습니다."
  - "서버는 현재 CPU delegate만 사용 가능합니다."

### 중기 대응

서버 GPU를 정말 사용해야 한다면 아래 중 하나가 필요합니다.

1. GPU 지원이 포함된 MediaPipe Python 빌드 확보
2. MediaPipe를 GPU 지원 옵션으로 직접 재빌드
3. 서버 포즈 추론 엔진을 GPU 친화적인 다른 스택으로 교체
   - 예: ONNX Runtime GPU
   - 예: PyTorch 기반 pose model
   - 예: TensorRT/DirectML 경로를 갖는 별도 추론 파이프라인

---

## 정리 한 줄

**현재 서버에서 MediaPipe GPU가 안 되는 이유는 GPU가 없어서가 아니라, 설치된 Python MediaPipe wheel이 GPU delegate를 포함하지 않은 CPU 중심 빌드이기 때문입니다.**
