import { FormEvent, useEffect, useRef, useState } from "react";
import {
  FilesetResolver,
  PoseLandmarker,
} from "@mediapipe/tasks-vision";

import {
  AdminOverview,
  InterviewQuestion,
  InterviewReportResponse,
  InterviewSession,
  JobCategory,
  LoginResponse,
  PostureEventPayload,
  UserProfile,
  api,
} from "./api";

const DEFAULT_EMAIL = "admin@example.com";
const DEFAULT_PASSWORD = "admin1234!";
const POSTURE_CAPTURE_INTERVAL_MS = 5000;
const POSTURE_SAMPLE_BATCH = 25;
const LOCAL_POSTURE_SAMPLE_FPS = 5;
const LOCAL_INFERENCE_THRESHOLD_MS = 200;
const LOCAL_RECOVERY_THRESHOLD_MS = 140;
const MIN_ANALYSIS_FPS = 4;
const RECOVERY_ANALYSIS_FPS = 5;
const POSTURE_PERF_WINDOW = 12;
const POSE_WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm";
const POSE_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

type LandmarkPoint = {
  x: number;
  y: number;
  visibility?: number;
};

type PoseSnapshot = {
  landmarks: LandmarkPoint[];
  inferenceMs: number;
  timestampMs: number;
  summary: {
    shoulder_asymmetry_score: number;
    gaze_away_ratio: number;
    hand_face_event_count: number;
    upper_body_motion_score: number;
  };
  events: PostureEventPayload[];
};

type CameraState = "idle" | "requesting" | "ready" | "error";
type PostureMode = "local" | "server";
type PostureModePreference = "auto" | "force-local" | "force-server";
type MediaPipeDelegatePreference = "auto" | "gpu" | "cpu";
type MediaPipeRuntime = "gpu" | "cpu" | "loading";
type ServerAnalysisResult = {
  status: string;
  storedEventCount: number;
  syncedAtLabel: string;
  questionSequenceNo: number;
};

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function distance(a?: { x: number; y: number }, b?: { x: number; y: number }): number {
  if (!a || !b) {
    return 0;
  }
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function isVisible(landmark?: LandmarkPoint): landmark is LandmarkPoint {
  return Boolean(landmark && (landmark.visibility === undefined || landmark.visibility > 0.35));
}

export function App() {
  const [email, setEmail] = useState(DEFAULT_EMAIL);
  const [password, setPassword] = useState(DEFAULT_PASSWORD);
  const [categories, setCategories] = useState<JobCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("it");
  const [login, setLogin] = useState<LoginResponse | null>(null);
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [report, setReport] = useState<InterviewReportResponse | null>(null);
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [postureStatus, setPostureStatus] = useState("카메라가 꺼져 있습니다.");
  const [postureSampleCount, setPostureSampleCount] = useState(0);
  const [overlayStatus, setOverlayStatus] = useState("자세 오버레이가 비활성 상태입니다.");
  const [overlayEnabled, setOverlayEnabled] = useState(true);
  const [postureMode, setPostureMode] = useState<PostureMode>("local");
  const [postureModePreference, setPostureModePreference] =
    useState<PostureModePreference>("auto");
  const [mediaPipeDelegatePreference, setMediaPipeDelegatePreference] =
    useState<MediaPipeDelegatePreference>("auto");
  const [mediaPipeRuntime, setMediaPipeRuntime] = useState<MediaPipeRuntime>("cpu");
  const [serverMediaPipeDelegatePreference, setServerMediaPipeDelegatePreference] =
    useState<Exclude<MediaPipeDelegatePreference, "auto">>("cpu");
  const [serverMediaPipeRuntime, setServerMediaPipeRuntime] = useState<MediaPipeRuntime>("cpu");
  const [averageInferenceMs, setAverageInferenceMs] = useState(0);
  const [analysisFps, setAnalysisFps] = useState(0);
  const [serverAnalysisResult, setServerAnalysisResult] = useState<ServerAnalysisResult | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([
    "화면 준비 완료. 백엔드 연결을 기다리는 중입니다.",
  ]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const poseLandmarkerRef = useRef<PoseLandmarker | null>(null);
  const postureSubmittingRef = useRef(false);
  const pendingImmediateServerSyncRef = useRef(false);
  const lastQuestionSyncRef = useRef<string | null>(null);
  const postureSampleCountRef = useRef(0);
  const animationFrameRef = useRef<number | null>(null);
  const lastPoseProcessAtRef = useRef(0);
  const lastVideoTimeRef = useRef(-1);
  const latestPoseSnapshotRef = useRef<PoseSnapshot | null>(null);
  const previousUpperBodyCenterRef = useRef<{ x: number; y: number } | null>(null);
  const postureModeRef = useRef<PostureMode>("local");
  const postureModePreferenceRef = useRef<PostureModePreference>("auto");
  const mediaPipeDelegatePreferenceRef = useRef<MediaPipeDelegatePreference>("auto");
  const serverMediaPipeDelegatePreferenceRef = useRef<Exclude<MediaPipeDelegatePreference, "auto">>("cpu");
  const overlayEnabledRef = useRef(true);
  const inferenceSamplesRef = useRef<number[]>([]);
  const processedAtSamplesRef = useRef<number[]>([]);
  const averageInferenceMsRef = useRef(0);
  const analysisFpsRef = useRef(0);

  useEffect(() => {
    void loadInitialData();
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) {
      return;
    }
    if (streamRef.current) {
      videoElement.srcObject = streamRef.current;
      void videoElement.play().catch(() => {
        setCameraError("카메라 미리보기를 자동으로 시작하지 못했습니다.");
      });
      return;
    }
    videoElement.srcObject = null;
  }, [cameraState]);

  useEffect(() => {
    if (cameraState !== "ready") {
      clearOverlay();
      stopPoseLoop();
      return;
    }

    startPoseLoop();
    return () => {
      stopPoseLoop();
    };
  }, [cameraState]);

  useEffect(() => {
    overlayEnabledRef.current = overlayEnabled;
    if (!overlayEnabled) {
      clearOverlay();
      return;
    }
    drawLatestOverlay();
  }, [overlayEnabled]);

  useEffect(() => {
    if (lastQuestionSyncRef.current !== question?.id) {
      lastQuestionSyncRef.current = question?.id ?? null;
      postureSampleCountRef.current = 0;
      setPostureSampleCount(0);
      setServerAnalysisResult(null);
      if (question) {
        setPostureStatus(
          cameraState === "ready"
            ? "카메라가 연결되었습니다. 현재 질문의 자세 분석을 준비합니다."
            : "이 질문의 자세 샘플을 보내려면 카메라를 켜주세요.",
        );
        setOverlayStatus(
          cameraState === "ready"
            ? "자세 오버레이가 현재 질문을 추적하고 있습니다."
            : "자세 오버레이를 사용하려면 카메라를 켜주세요.",
        );
      } else if (cameraState === "ready") {
        setPostureStatus("카메라가 연결되었습니다. 샘플 수집을 시작하려면 면접 질문을 시작하세요.");
        setOverlayStatus("자세 오버레이가 활성화되었습니다. 요약을 저장하려면 면접 질문을 시작하세요.");
      } else {
        setPostureStatus("카메라가 꺼져 있습니다.");
        setOverlayStatus("자세 오버레이가 비활성 상태입니다.");
      }
    }
  }, [cameraState, question]);

  useEffect(() => {
    if (!session || !question || cameraState !== "ready") {
      return;
    }

    setPostureStatus(
      postureMode === "local"
        ? "카메라가 연결되었습니다. 현재 질문의 로컬 자세 요약을 전송합니다."
        : "카메라가 연결되었습니다. 로컬 분석 성능이 낮아 서버 보조 분석을 사용합니다.",
    );

    const intervalId = window.setInterval(() => {
      void syncPostureSample(session.session_id, question.id, question.sequence_no);
    }, POSTURE_CAPTURE_INTERVAL_MS);

    if (postureModePreferenceRef.current === "force-server" && pendingImmediateServerSyncRef.current) {
      pendingImmediateServerSyncRef.current = false;
      appendLog("현재 질문이 준비되어 보류 중이던 서버 자세 샘플을 지금 전송합니다.");
      void syncPostureSample(session.session_id, question.id, question.sequence_no);
    }

    void syncPostureSample(session.session_id, question.id, question.sequence_no);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [cameraState, postureMode, question, session]);

  async function loadInitialData() {
    setBusyAction("boot");
    setError(null);
    try {
      const [jobCategories, currentUser] = await Promise.all([
        api.getJobCategories(),
        restoreSession(),
      ]);
      setCategories(jobCategories);
      if (jobCategories.length > 0) {
        setSelectedCategory(jobCategories[0].code);
      }
      if (currentUser?.role === "admin") {
        await refreshAdminOverview();
      } else {
        setAdminOverview(null);
      }
      appendLog("직무 카테고리를 불러왔습니다.");
    } catch (loadError) {
      handleError(loadError, "초기 직무 카테고리를 불러오지 못했습니다.");
    } finally {
      setBusyAction(null);
    }
  }

  async function restoreSession(): Promise<UserProfile | null> {
    if (!api.getAccessToken()) {
      setLogin(null);
      return null;
    }

    try {
      const user = await api.me();
      setLogin({
        access_token: api.getAccessToken() ?? "",
        token_type: "bearer",
        user,
      });
      return user;
    } catch {
      api.setAccessToken(null);
      setLogin(null);
      return null;
    }
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setBusyAction("login");
    setError(null);
    try {
      const result = await api.login(email, password);
      api.setAccessToken(result.access_token);
      setLogin(result);
      appendLog(`${result.user.display_name} 계정으로 로그인했습니다.`);
      if (result.user.role === "admin") {
        await refreshAdminOverview();
      } else {
        setAdminOverview(null);
      }
    } catch (loginError) {
      handleError(loginError, "로그인에 실패했습니다.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateSession() {
    setBusyAction("create-session");
    setError(null);
    try {
      const created = await api.createInterview({
        job_category_code: selectedCategory,
        mode: "live",
        question_count: 3,
        answer_time_limit_sec: 60,
        allow_retry: true,
      });
      setSession(created);
      setQuestion(null);
      setReport(null);
      setAnswerText("");
      appendLog(`면접 세션 ${created.session_id.slice(0, 8)}을 생성했습니다.`);
      await refreshAdminOverview();
    } catch (createError) {
      handleError(createError, "면접 세션 생성에 실패했습니다.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleStartInterview() {
    if (!session) {
      return;
    }
    setBusyAction("start-interview");
    setError(null);
    try {
      const started = await api.startInterview(session.session_id);
      setSession((current) =>
        current ? { ...current, status: started.status } : current,
      );
      setQuestion(started.question);
      appendLog(`면접을 시작하고 질문 ${started.question.sequence_no}번을 불러왔습니다.`);
      await refreshAdminOverview();
    } catch (startError) {
      handleError(startError, "면접 시작에 실패했습니다.");
    } finally {
      setBusyAction(null);
    }
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("error");
      setCameraError("이 환경에서는 웹캠 접근을 지원하지 않습니다.");
      setPostureStatus("이 환경에서는 카메라를 사용할 수 없습니다.");
      appendLog("이 환경에서는 카메라를 사용할 수 없습니다.");
      return;
    }

    setCameraState("requesting");
    setCameraError(null);

    try {
      await createOrRefreshPoseLandmarker();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "user",
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setCameraState("ready");
      const initialMode =
        postureModePreferenceRef.current === "force-server" ? "server" : "local";
      postureModeRef.current = initialMode;
      setPostureMode(initialMode);
      setAverageInferenceMs(0);
      setAnalysisFps(0);
      inferenceSamplesRef.current = [];
      processedAtSamplesRef.current = [];
      setPostureStatus(
        initialMode === "server"
          ? "카메라가 연결되었습니다. 현재 질문에 서버 분석 모드가 활성화되어 있습니다."
          : question
            ? "카메라가 연결되었습니다. 현재 질문의 로컬 자세 요약을 전송합니다."
            : "카메라가 연결되었습니다. 샘플 수집을 시작하려면 면접 질문을 시작하세요.",
      );
      setOverlayStatus("자세 오버레이가 활성화되었습니다.");
      postureSampleCountRef.current = 0;
      setPostureSampleCount(0);
      appendLog("카메라 연결에 성공했습니다.");
    } catch (cameraLoadError) {
      streamRef.current = null;
      setCameraState("error");
      const detail =
        cameraLoadError instanceof Error ? cameraLoadError.message : "카메라 접근이 거부되었습니다.";
      setCameraError(detail);
      setPostureStatus("실시간 자세 샘플링을 위해 카메라 권한이 필요합니다.");
      setOverlayStatus("자세 오버레이를 시작하지 못했습니다.");
      appendLog("카메라 연결에 실패했습니다.");
    }
  }

  function stopCamera() {
    const stream = streamRef.current;
    if (stream) {
      for (const track of stream.getTracks()) {
        track.stop();
      }
    }
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraState("idle");
    setCameraError(null);
    postureModeRef.current = postureModePreferenceRef.current === "force-server" ? "server" : "local";
    setPostureMode(postureModeRef.current);
    setAverageInferenceMs(0);
    setAnalysisFps(0);
    inferenceSamplesRef.current = [];
    processedAtSamplesRef.current = [];
    postureSampleCountRef.current = 0;
    setPostureSampleCount(0);
    setPostureStatus(question ? "이 질문의 자세 샘플을 보내려면 카메라를 켜주세요." : "카메라가 꺼져 있습니다.");
    setOverlayStatus("자세 오버레이가 비활성 상태입니다.");
    latestPoseSnapshotRef.current = null;
    previousUpperBodyCenterRef.current = null;
    clearOverlay();
  }

  async function ensurePoseLandmarker() {
    if (poseLandmarkerRef.current) {
      return poseLandmarkerRef.current;
    }

    const vision = await FilesetResolver.forVisionTasks(POSE_WASM_URL);
    const poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: POSE_MODEL_URL,
      },
      runningMode: "VIDEO",
      numPoses: 1,
    });
    poseLandmarkerRef.current = poseLandmarker;
    appendLog("자세 랜드마커 초기화를 완료했습니다.");
    return poseLandmarker;
  }

  async function createPoseLandmarkerWithDelegate() {
    const vision = await FilesetResolver.forVisionTasks(POSE_WASM_URL);
    const preferredDelegate = mediaPipeDelegatePreferenceRef.current;
    const delegates =
      preferredDelegate === "gpu"
        ? ["GPU"]
        : preferredDelegate === "cpu"
          ? ["CPU"]
          : ["GPU", "CPU"];

    setMediaPipeRuntime("loading");

    let lastError: unknown = null;
    for (const delegate of delegates) {
      try {
        const poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: POSE_MODEL_URL,
            delegate: delegate as "GPU" | "CPU",
          },
          runningMode: "VIDEO",
          numPoses: 1,
        });
        poseLandmarkerRef.current = poseLandmarker;
        setMediaPipeRuntime(delegate === "GPU" ? "gpu" : "cpu");
        appendLog(`MediaPipe 자세 분석기가 ${delegate} 모드로 초기화되었습니다.`);
        return poseLandmarker;
      } catch (delegateError) {
        lastError = delegateError;
        if (preferredDelegate !== "auto") {
          break;
        }
      }
    }

    setMediaPipeRuntime("cpu");
    throw lastError instanceof Error
      ? lastError
      : new Error("MediaPipe 자세 분석기를 초기화하지 못했습니다.");
  }

  async function createOrRefreshPoseLandmarker(forceRefresh = false) {
    if (!forceRefresh && poseLandmarkerRef.current) {
      return poseLandmarkerRef.current;
    }

    if (poseLandmarkerRef.current) {
      poseLandmarkerRef.current.close();
      poseLandmarkerRef.current = null;
    }

    return createPoseLandmarkerWithDelegate();
  }

  async function handleMediaPipeDelegateChange(nextPreference: MediaPipeDelegatePreference) {
    mediaPipeDelegatePreferenceRef.current = nextPreference;
    setMediaPipeDelegatePreference(nextPreference);

    try {
      await createOrRefreshPoseLandmarker(true);
      latestPoseSnapshotRef.current = null;
      clearOverlay();
      if (cameraState === "ready") {
        startPoseLoop();
      }
      appendLog(
        `MediaPipe 실행 장치를 ${nextPreference === "auto" ? "자동" : nextPreference.toUpperCase()}로 변경했습니다.`,
      );
    } catch (delegateError) {
      const detail =
        delegateError instanceof Error ? delegateError.message : "MediaPipe 실행 장치를 변경하지 못했습니다.";
      setCameraError(detail);
      appendLog(`MediaPipe 실행 장치 변경 실패: ${detail}`);
    }
  }

  function handleServerMediaPipeDelegateChange(
    nextPreference: Exclude<MediaPipeDelegatePreference, "auto">,
  ) {
    if (nextPreference === "gpu") {
      appendLog("현재 서버 빌드는 CPU만 지원하여 서버 MediaPipe GPU를 사용할 수 없습니다.");
      setCameraError("현재 서버 빌드는 CPU만 지원합니다.");
      return;
    }
    serverMediaPipeDelegatePreferenceRef.current = nextPreference;
    setServerMediaPipeDelegatePreference(nextPreference);
    setServerMediaPipeRuntime(nextPreference);
    appendLog(`서버 MediaPipe 실행 장치를 ${nextPreference.toUpperCase()}로 설정했습니다.`);
  }

  function startPoseLoop() {
    stopPoseLoop();

    const loop = () => {
      const videoElement = videoRef.current;
      const poseLandmarker = poseLandmarkerRef.current;
      if (!videoElement || !poseLandmarker || cameraState !== "ready") {
        animationFrameRef.current = window.requestAnimationFrame(loop);
        return;
      }

      syncOverlayCanvasSize();

      const now = performance.now();
      const processIntervalMs = 1000 / LOCAL_POSTURE_SAMPLE_FPS;
      const canProcessFrame =
        videoElement.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
        videoElement.currentTime !== lastVideoTimeRef.current &&
        now - lastPoseProcessAtRef.current >= processIntervalMs;

      if (canProcessFrame) {
        const startedAt = performance.now();
        const result = poseLandmarker.detectForVideo(videoElement, startedAt);
        const inferenceMs = performance.now() - startedAt;
        lastPoseProcessAtRef.current = now;
        lastVideoTimeRef.current = videoElement.currentTime;
        handlePoseResult(result.landmarks[0] ?? [], inferenceMs, startedAt);
      } else {
        drawLatestOverlay();
      }

      animationFrameRef.current = window.requestAnimationFrame(loop);
    };

    animationFrameRef.current = window.requestAnimationFrame(loop);
  }

  function stopPoseLoop() {
    if (animationFrameRef.current !== null) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    lastPoseProcessAtRef.current = 0;
    lastVideoTimeRef.current = -1;
  }

  function handlePoseResult(landmarks: LandmarkPoint[], inferenceMs: number, timestampMs: number) {
    updatePosturePerformance(inferenceMs, timestampMs);

    if (landmarks.length === 0) {
      latestPoseSnapshotRef.current = null;
      setOverlayStatus("자세 오버레이는 활성화되어 있지만 신체를 감지하지 못했습니다.");
      clearOverlay();
      return;
    }

    const summary = buildPoseSummary(landmarks);
    const events = buildPoseEvents(summary, timestampMs);
    latestPoseSnapshotRef.current = {
      landmarks,
      inferenceMs,
      timestampMs,
      summary,
      events,
    };
    setOverlayStatus(`자세 오버레이 활성화. 로컬 추론 ${Math.round(inferenceMs)}ms`);
    drawLatestOverlay();
  }

  function updatePosturePerformance(inferenceMs: number, timestampMs: number) {
    const inferenceSamples = [...inferenceSamplesRef.current, inferenceMs].slice(-POSTURE_PERF_WINDOW);
    const processedSamples = [...processedAtSamplesRef.current, timestampMs].slice(-POSTURE_PERF_WINDOW);
    inferenceSamplesRef.current = inferenceSamples;
    processedAtSamplesRef.current = processedSamples;

    const avgInferenceMs =
      inferenceSamples.reduce((total, sample) => total + sample, 0) / inferenceSamples.length;
    const computedFps =
      processedSamples.length >= 2
        ? ((processedSamples.length - 1) * 1000) /
          Math.max(1, processedSamples[processedSamples.length - 1] - processedSamples[0])
        : LOCAL_POSTURE_SAMPLE_FPS;

    averageInferenceMsRef.current = avgInferenceMs;
    analysisFpsRef.current = computedFps;
    setAverageInferenceMs(avgInferenceMs);
    setAnalysisFps(computedFps);

    if (inferenceSamples.length < 3 || postureModePreferenceRef.current !== "auto") {
      return;
    }

    const nextMode =
      postureModeRef.current === "local"
        ? avgInferenceMs > LOCAL_INFERENCE_THRESHOLD_MS || computedFps < MIN_ANALYSIS_FPS
          ? "server"
          : "local"
        : avgInferenceMs < LOCAL_RECOVERY_THRESHOLD_MS && computedFps >= RECOVERY_ANALYSIS_FPS
          ? "local"
          : "server";

    if (nextMode !== postureModeRef.current) {
      postureModeRef.current = nextMode;
      setPostureMode(nextMode);
      if (nextMode === "server") {
        setPostureStatus("로컬 분석 성능이 낮아 서버 보조 분석 모드로 전환했습니다.");
        appendLog("로컬 자세 분석 성능이 낮아 서버 보조 분석으로 전환했습니다.");
      } else {
        setPostureStatus("로컬 분석 성능이 회복되어 로컬 모드로 전환했습니다.");
        appendLog("로컬 자세 분석 성능이 회복되어 로컬 모드로 전환했습니다.");
      }
    }
  }

  function handlePostureModePreferenceChange(nextPreference: PostureModePreference) {
    postureModePreferenceRef.current = nextPreference;
    setPostureModePreference(nextPreference);

    if (nextPreference === "force-server") {
      postureModeRef.current = "server";
      setPostureMode("server");
      setPostureStatus("수동 전환이 활성화되었습니다. 서버 분석 모드로 자세 샘플을 전송합니다.");
      appendLog("수동 자세 모드 전환: 서버 분석 모드 활성화.");
      if (cameraState !== "ready") {
        pendingImmediateServerSyncRef.current = true;
        appendLog("서버 모드가 선택되었지만 아직 카메라가 준비되지 않았습니다.");
      } else if (!session || !question) {
        pendingImmediateServerSyncRef.current = true;
        appendLog("서버 모드가 선택되었지만 아직 진행 중인 면접 질문이 없습니다.");
      } else {
        pendingImmediateServerSyncRef.current = false;
        appendLog("서버 모드가 선택되어 즉시 자세 샘플을 백엔드로 전송합니다.");
        void syncPostureSample(session.session_id, question.id, question.sequence_no);
      }
      return;
    }

    if (nextPreference === "force-local") {
      pendingImmediateServerSyncRef.current = false;
      postureModeRef.current = "local";
      setPostureMode("local");
      setPostureStatus("수동 전환이 활성화되었습니다. 로컬 분석 요약을 전송합니다.");
      appendLog("수동 자세 모드 전환: 로컬 분석 모드 활성화.");
      return;
    }

    pendingImmediateServerSyncRef.current = false;
    const nextMode =
      averageInferenceMsRef.current > LOCAL_INFERENCE_THRESHOLD_MS ||
      analysisFpsRef.current < MIN_ANALYSIS_FPS
        ? "server"
        : "local";
    postureModeRef.current = nextMode;
    setPostureMode(nextMode);
    setPostureStatus(
      nextMode === "server"
        ? "자동 자세 모드로 복귀했습니다. 로컬 성능이 낮아 서버 보조 분석이 활성화되었습니다."
        : "자동 자세 모드로 복귀했습니다. 로컬 분석이 활성화되었습니다.",
    );
    appendLog(`수동 자세 모드를 해제하고 자동 모드(${nextMode})로 복귀했습니다.`);
  }

  async function syncPostureSample(
    sessionId: string,
    questionId: string,
    questionSequenceNo: number,
  ) {
    if (postureSubmittingRef.current) {
      return;
    }

    postureSubmittingRef.current = true;
    try {
      const nextSampleCount = postureSampleCountRef.current + POSTURE_SAMPLE_BATCH;
      const poseSnapshot = latestPoseSnapshotRef.current;

      if (poseSnapshot && postureModeRef.current === "local") {
        appendLog(
          `로컬 자세 요약 전송: 질문 ${questionSequenceNo}, 샘플 수 ${nextSampleCount}`,
        );
        const response = await api.submitPostureLocalSummary({
          session_id: sessionId,
          question_id: questionId,
          source_mode: "local",
          sample_fps: LOCAL_POSTURE_SAMPLE_FPS,
          mediapipe_delegate_preference: mediaPipeDelegatePreferenceRef.current,
          summary: poseSnapshot.summary,
          events: poseSnapshot.events,
        });
        setPostureStatus(
          `자세 오버레이 활성화. ${LOCAL_POSTURE_SAMPLE_FPS}FPS 기준 로컬 자세 요약을 업로드했습니다.`,
        );
        setServerAnalysisResult(null);
        appendLog(
          `로컬 자세 요약 저장 완료: 질문 ${questionSequenceNo}, 샘플 수 ${nextSampleCount}, 상태 ${response.status}`,
        );
      } else {
        const videoElement = videoRef.current;
        const stream = streamRef.current;
        const activeTrack = stream?.getVideoTracks()[0];
        const settings = activeTrack?.getSettings();
        const frameJpegBase64 = captureFrameJpegBase64();
        const requestMode = postureModeRef.current === "server" ? "server" : "fallback";

        appendLog(
          `${requestMode === "server" ? "서버" : "보조"} 자세 샘플 전송: 질문 ${questionSequenceNo}, 샘플 수 ${nextSampleCount}, 프레임 ${frameJpegBase64 ? "포함" : "없음"}`,
        );

        const response = await api.submitPostureFallbackSamples({
          session_id: sessionId,
          question_id: questionId,
          sample_count: nextSampleCount,
          source_mode: requestMode,
          mediapipe_delegate_preference: serverMediaPipeDelegatePreferenceRef.current,
          frame_jpeg_base64: frameJpegBase64,
          landmarks_summary: {
            camera_label: activeTrack?.label ?? "default-camera",
            frame_width: settings?.width ?? videoElement?.videoWidth ?? 0,
            frame_height: settings?.height ?? videoElement?.videoHeight ?? 0,
            question_sequence_no: questionSequenceNo,
            captured_at: new Date().toISOString(),
            overlay_status: overlayStatus,
            avg_inference_ms: Math.round(averageInferenceMsRef.current),
            analysis_fps: Number(analysisFpsRef.current.toFixed(2)),
          },
        });
        setServerAnalysisResult({
          status: response.status,
          storedEventCount: response.stored_event_count,
          syncedAtLabel: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          questionSequenceNo,
        });
        if (response.mediapipe_runtime === "gpu" || response.mediapipe_runtime === "cpu") {
          setServerMediaPipeRuntime(response.mediapipe_runtime);
        }
        setPostureStatus(
          postureModeRef.current === "server"
            ? "로컬 분석 성능이 낮아 서버 보조 분석으로 자세 데이터를 업로드했습니다."
            : "자세 오버레이를 사용할 수 없어 보조 자세 메타데이터를 업로드했습니다.",
        );
        appendLog(
          `${requestMode === "server" ? "서버" : "보조"} 자세 샘플 저장 응답: 질문 ${questionSequenceNo}, 샘플 수 ${nextSampleCount}, 상태 ${response.status}, 이벤트 ${response.stored_event_count}개`,
        );
      }

      postureSampleCountRef.current = nextSampleCount;
      setPostureSampleCount(nextSampleCount);
    } catch (postureError) {
      const detail =
        postureError instanceof Error ? postureError.message : "자세 샘플 동기화에 실패했습니다.";
      setCameraError(detail);
      setPostureStatus("카메라는 켜져 있지만 자세 샘플 동기화에 실패했습니다.");
      appendLog(`자세 샘플 동기화 실패: ${detail}`);
    } finally {
      postureSubmittingRef.current = false;
    }
  }

  function captureFrameJpegBase64(): string | undefined {
    const videoElement = videoRef.current;
    if (!videoElement) {
      return undefined;
    }

    const width = videoElement.videoWidth;
    const height = videoElement.videoHeight;
    if (!width || !height) {
      return undefined;
    }

    const frameCanvas = document.createElement("canvas");
    frameCanvas.width = width;
    frameCanvas.height = height;
    const context = frameCanvas.getContext("2d");
    if (!context) {
      return undefined;
    }

    context.drawImage(videoElement, 0, 0, width, height);
    const dataUrl = frameCanvas.toDataURL("image/jpeg", 0.72);
    return dataUrl.split(",")[1];
  }

  function buildPoseSummary(landmarks: LandmarkPoint[]) {
    const nose = landmarks[0];
    const leftShoulder = landmarks[11];
    const rightShoulder = landmarks[12];
    const leftWrist = landmarks[15];
    const rightWrist = landmarks[16];
    const leftHip = landmarks[23];
    const rightHip = landmarks[24];

    const shoulderCenter = {
      x: (leftShoulder.x + rightShoulder.x) / 2,
      y: (leftShoulder.y + rightShoulder.y) / 2,
    };
    const hipCenter = {
      x: (leftHip.x + rightHip.x) / 2,
      y: (leftHip.y + rightHip.y) / 2,
    };

    const shoulderAsymmetryScore = clamp01(Math.abs(leftShoulder.y - rightShoulder.y) * 3.2);
    const gazeAwayRatio = nose ? clamp01(Math.abs(nose.x - shoulderCenter.x) * 3.5) : 0;
    const handFaceEventCount = nose && (distance(leftWrist, nose) < 0.12 || distance(rightWrist, nose) < 0.12) ? 1 : 0;

    let upperBodyMotionScore = 0;
    if (previousUpperBodyCenterRef.current) {
      upperBodyMotionScore = clamp01(
        distance(previousUpperBodyCenterRef.current, shoulderCenter) * 12 +
          distance(shoulderCenter, hipCenter) * 0.4,
      );
    }
    previousUpperBodyCenterRef.current = shoulderCenter;

    return {
      shoulder_asymmetry_score: shoulderAsymmetryScore,
      gaze_away_ratio: gazeAwayRatio,
      hand_face_event_count: handFaceEventCount,
      upper_body_motion_score: upperBodyMotionScore,
    };
  }

  function buildPoseEvents(
    summary: {
      shoulder_asymmetry_score: number;
      gaze_away_ratio: number;
      hand_face_event_count: number;
      upper_body_motion_score: number;
    },
    timestampMs: number,
  ): PostureEventPayload[] {
    const events: PostureEventPayload[] = [];

    if (summary.gaze_away_ratio > 0.35) {
      events.push({
        event_type: "gaze_away",
        severity: summary.gaze_away_ratio > 0.6 ? "high" : "medium",
        started_at_ms: Math.max(0, Math.round(timestampMs - 1000)),
        ended_at_ms: Math.round(timestampMs),
      });
    }

    if (summary.hand_face_event_count > 0) {
      events.push({
        event_type: "hand_face_contact",
        severity: "medium",
        started_at_ms: Math.max(0, Math.round(timestampMs - 1000)),
        ended_at_ms: Math.round(timestampMs),
      });
    }

    if (summary.upper_body_motion_score > 0.45) {
      events.push({
        event_type: "upper_body_motion",
        severity: summary.upper_body_motion_score > 0.7 ? "high" : "low",
        started_at_ms: Math.max(0, Math.round(timestampMs - 1000)),
        ended_at_ms: Math.round(timestampMs),
      });
    }

    return events;
  }

  function syncOverlayCanvasSize() {
    const videoElement = videoRef.current;
    const overlayCanvas = overlayCanvasRef.current;
    if (!videoElement || !overlayCanvas) {
      return;
    }

    const width = videoElement.videoWidth || videoElement.clientWidth;
    const height = videoElement.videoHeight || videoElement.clientHeight;
    if (!width || !height) {
      return;
    }

    if (overlayCanvas.width !== width) {
      overlayCanvas.width = width;
    }
    if (overlayCanvas.height !== height) {
      overlayCanvas.height = height;
    }
  }

  function clearOverlay() {
    const overlayCanvas = overlayCanvasRef.current;
    if (!overlayCanvas) {
      return;
    }
    const ctx = overlayCanvas.getContext("2d");
    if (!ctx) {
      return;
    }
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  }

  function drawLatestOverlay() {
    if (!overlayEnabledRef.current) {
      clearOverlay();
      return;
    }
    const overlayCanvas = overlayCanvasRef.current;
    const snapshot = latestPoseSnapshotRef.current;
    if (!overlayCanvas || !snapshot) {
      clearOverlay();
      return;
    }
    drawPoseOverlay(snapshot.landmarks);
  }

  function drawPoseOverlay(landmarks: LandmarkPoint[]) {
    if (!overlayEnabledRef.current) {
      clearOverlay();
      return;
    }
    const overlayCanvas = overlayCanvasRef.current;
    if (!overlayCanvas) {
      return;
    }

    const ctx = overlayCanvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(255, 181, 90, 0.9)";
    ctx.fillStyle = "rgba(116, 255, 214, 0.95)";

    for (const connection of PoseLandmarker.POSE_CONNECTIONS) {
      const start = landmarks[connection.start];
      const end = landmarks[connection.end];
      if (!isVisible(start) || !isVisible(end)) {
        continue;
      }
      ctx.beginPath();
      ctx.moveTo(start.x * overlayCanvas.width, start.y * overlayCanvas.height);
      ctx.lineTo(end.x * overlayCanvas.width, end.y * overlayCanvas.height);
      ctx.stroke();
    }

    for (const landmark of landmarks) {
      if (!isVisible(landmark)) {
        continue;
      }
      ctx.beginPath();
      ctx.arc(
        landmark.x * overlayCanvas.width,
        landmark.y * overlayCanvas.height,
        4,
        0,
        Math.PI * 2,
      );
      ctx.fill();
    }
  }

  async function handleSubmitAnswer() {
    if (!session || !question || !answerText.trim()) {
      return;
    }
    setBusyAction("submit-answer");
    setError(null);
    try {
      const result = await api.submitTextAnswer(session.session_id, question.id, {
        text: answerText.trim(),
        attempt_no: 1,
        is_final_attempt: true,
      });
      appendLog(
        `Submitted answer for question ${question.sequence_no}. Next action: ${result.next_action}.`,
      );
    } catch (submitError) {
      handleError(submitError, "Failed to submit the answer.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleNextQuestion() {
    if (!session || !question) {
      return;
    }
    setBusyAction("next-question");
    setError(null);
    try {
      const next = await api.nextQuestion(session.session_id, question.id);
      setSession((current) => (current ? { ...current, status: next.status } : current));
      setQuestion(next.question);
      setAnswerText("");
      appendLog(
        next.question
          ? `Moved to question ${next.question.sequence_no}.`
          : "Interview completed. Report is now available.",
      );

      if (next.report_ready) {
        const nextReport = await api.getReport(session.session_id);
        setReport(nextReport);
        appendLog("Loaded interview report.");
      }

      await refreshAdminOverview();
    } catch (nextError) {
      handleError(nextError, "Failed to move to the next question.");
    } finally {
      setBusyAction(null);
    }
  }

  async function refreshAdminOverview() {
    try {
      const overview = await api.getAdminOverview();
      setAdminOverview(overview);
    } catch (overviewError) {
      setAdminOverview(null);
      const message = overviewError instanceof Error ? overviewError.message : "";
      if (!message.includes("Admin access is required") && !message.includes("Bearer token is required")) {
        handleError(overviewError, "Failed to refresh admin overview.");
      }
    }
  }

  async function handleLogout() {
    setBusyAction("logout");
    setError(null);
    try {
      await api.logout();
    } catch {
      // Clear local session state even if the backend session is already gone.
    } finally {
      api.setAccessToken(null);
      stopCamera();
      setLogin(null);
      setSession(null);
      setQuestion(null);
      setAnswerText("");
      setReport(null);
      setAdminOverview(null);
      appendLog("Logged out and cleared the local session.");
      setBusyAction(null);
    }
  }

  function appendLog(message: string) {
    setActivityLog((current) => [
      `${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ${message}`,
      ...current,
    ]);
  }

  function handleError(cause: unknown, fallbackMessage: string) {
    const detail = cause instanceof Error ? cause.message : fallbackMessage;
    setError(detail);
    appendLog(`Error: ${fallbackMessage}`);
  }

  const isBusy = busyAction !== null;
  const isServerFallback = postureMode === "server";
  const cameraCardClassName = `camera-card ${isServerFallback ? "camera-card-server" : "camera-card-local"}`;
  const modeBadgeClassName = `mode-badge ${isServerFallback ? "mode-badge-server" : "mode-badge-local"}`;
  const postureModePreferenceLabel =
    postureModePreference === "auto"
      ? "AUTO"
      : postureModePreference === "force-server"
        ? "서버 모드"
        : "브라우저 모드";

  const mediaPipeDelegatePreferenceLabel =
    mediaPipeDelegatePreference === "auto"
      ? "자동"
      : mediaPipeDelegatePreference === "gpu"
        ? "GPU"
        : "CPU";
  const mediaPipeRuntimeLabel =
    mediaPipeRuntime === "loading" ? "전환 중" : mediaPipeRuntime.toUpperCase();

  const serverMediaPipeDelegatePreferenceLabel = serverMediaPipeDelegatePreference.toUpperCase();
  const serverMediaPipeRuntimeLabel =
    serverMediaPipeRuntime === "loading" ? "LOADING" : serverMediaPipeRuntime.toUpperCase();
  const serverGpuSupported = false;

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">AI Interview v2</p>
          <h1>실전 연습과 백엔드 검증을 위한 면접 제어 화면</h1>
          <p className="body-copy">
            이 화면은 로그인, 카테고리 조회, 면접 세션 생성, 질문 진행,
            리포트 조회, 관리자 개요 갱신까지 전체 흐름을 한 번에 점검할 수 있습니다.
          </p>
        </div>
        <div className="hero-badge hero-auth-badge">
          <div className="hero-auth-head">
            <span>백엔드</span>
            <strong>{error ? "확인 필요" : "흐름 점검 준비 완료"}</strong>
          </div>
          {login ? (
            <div className="stack-form">
              <div className="session-summary auth-summary">
                <div>
                  <span>이름</span>
                  <strong>{login.user.display_name}</strong>
                </div>
                <div>
                  <span>권한</span>
                  <strong>{login.user.role}</strong>
                </div>
              </div>
              <button type="button" onClick={handleLogout} disabled={isBusy}>
                {busyAction === "logout" ? "로그아웃 중..." : "로그아웃"}
              </button>
            <div className="session-summary camera-summary camera-summary-runtime">
              <div>
                <span>MediaPipe 실행</span>
                <strong>{mediaPipeRuntimeLabel}</strong>
              </div>
              <div>
                <span>실행 장치 설정</span>
                <strong>{mediaPipeDelegatePreferenceLabel}</strong>
              </div>
              <div>
                <span>Server MediaPipe</span>
                <strong>{serverMediaPipeRuntimeLabel}</strong>
              </div>
              <div>
                <span>Server Delegate</span>
                <strong>{serverMediaPipeDelegatePreferenceLabel}</strong>
              </div>
            </div>
            </div>
          ) : (
            <form className="stack-form" onSubmit={handleLogin}>
              <label>
                <span>이메일</span>
                <input value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
              <label>
                <span>비밀번호</span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <button type="submit" disabled={isBusy}>
                {busyAction === "login" ? "로그인 중..." : "로그인"}
              </button>
            </form>
          )}
          <p className="inline-note">
            {login
              ? `${login.user.display_name} 님이 ${login.user.role} 권한으로 로그인했습니다.`
              : "헤더 우측 카드에서 바로 로그인 상태를 확인할 수 있습니다."}
          </p>
          <span>백엔드</span>
          <strong>{error ? "확인 필요" : "흐름 점검 준비 완료"}</strong>
        </div>
      </section>

      {error ? <section className="error-banner">{error}</section> : null}

      <section className="workspace-grid">
        <article className="panel panel-form">
          <div className="panel-heading">
            <p className="panel-kicker">인증</p>
            <h2>{login ? "세션 활성화" : "로그인"}</h2>
          </div>
          {login ? (
            <div className="stack-form">
              <div className="session-summary auth-summary">
                <div>
                  <span>이름</span>
                  <strong>{login.user.display_name}</strong>
                </div>
                <div>
                  <span>권한</span>
                  <strong>{login.user.role}</strong>
                </div>
              </div>
              <button type="button" onClick={handleLogout} disabled={isBusy}>
                {busyAction === "logout" ? "로그아웃 중..." : "로그아웃"}
              </button>
            </div>
          ) : (
            <form className="stack-form" onSubmit={handleLogin}>
              <label>
                <span>이메일</span>
                <input value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
              <label>
                <span>비밀번호</span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <button type="submit" disabled={isBusy}>
                {busyAction === "login" ? "로그인 중..." : "로그인"}
              </button>
            </form>
          )}
          <p className="inline-note">
            {login
              ? `${login.user.display_name} 님이 ${login.user.role} 권한으로 로그인했습니다.`
              : "기본 테스트 계정으로 로그인 세션을 시작할 수 있습니다."}
          </p>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <p className="panel-kicker">면접</p>
            <h2>실시간 세션 실행</h2>
          </div>

          <div className="control-row">
            <label className="compact-field">
              <span>직무</span>
              <select
                value={selectedCategory}
                onChange={(event) => setSelectedCategory(event.target.value)}
                disabled={isBusy}
              >
                {categories.map((category) => (
                  <option key={category.code} value={category.code}>
                    {category.name_ko} ({category.code})
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={handleCreateSession} disabled={isBusy}>
              {busyAction === "create-session" ? "생성 중..." : "세션 생성"}
            </button>
          </div>

          <div className="session-summary">
            <div>
              <span>상태</span>
              <strong>{session?.status ?? "대기"}</strong>
            </div>
            <div>
              <span>질문 수</span>
              <strong>{session?.question_count ?? 0}</strong>
            </div>
            <div>
              <span>재시도</span>
              <strong>{session?.allow_retry ? "허용" : "비허용"}</strong>
            </div>
          </div>

          <div className="action-row">
            <button
              type="button"
              onClick={handleStartInterview}
              disabled={isBusy || !session}
            >
              {busyAction === "start-interview" ? "시작 중..." : "면접 시작"}
            </button>
            <button
              type="button"
              onClick={() => void refreshAdminOverview()}
              disabled={isBusy}
              className="button-ghost"
            >
              관리자 새로고침
            </button>
          </div>

          <div className="interview-main-grid">
            <div className={cameraCardClassName}>
            <div className="camera-stage-card">
            <div className="question-meta">
              <span>카메라</span>
              <strong>{cameraState === "ready" ? "연결됨" : cameraState === "requesting" ? "연결 중" : "꺼짐"}</strong>
            </div>
            <div className="camera-preview-shell">
              <video
                ref={videoRef}
                className="camera-preview"
                autoPlay
                muted
                playsInline
              />
              <canvas ref={overlayCanvasRef} className="camera-overlay" />
              {cameraState !== "ready" ? (
                <div className="camera-placeholder">
                  <strong>웹캠 미리보기</strong>
                  <span>면접 중 자세 샘플을 전송하려면 카메라 접근을 허용하세요.</span>
                </div>
              ) : null}
            </div>
            </div>
            <div className="camera-insights-panel">
            <div className="session-summary camera-summary">
              <div>
                <span>상태</span>
                <strong>{postureStatus}</strong>
              </div>
              <div>
                <span>전송 샘플</span>
                <strong>{postureSampleCount}</strong>
              </div>
              <div>
                <span>오버레이</span>
                <strong>{overlayEnabled ? overlayStatus : "오버레이가 꺼져 있습니다."}</strong>
              </div>
              <div>
                <span>분석 모드</span>
                <strong className={modeBadgeClassName}>
                  {postureMode === "local" ? "로컬" : "서버 보조"}
                </strong>
              </div>
              <div>
                <span>자세분석</span>
                <strong>{postureModePreferenceLabel}</strong>
              </div>
              <div>
                <span>평균 추론</span>
                <strong>{averageInferenceMs > 0 ? `${Math.round(averageInferenceMs)} ms` : "-"}</strong>
              </div>
              <div>
                <span>분석 FPS</span>
                <strong>{analysisFps > 0 ? analysisFps.toFixed(1) : "-"}</strong>
              </div>
              <div>
                <span>서버 결과</span>
                <strong>{serverAnalysisResult?.status ?? "-"}</strong>
              </div>
              <div>
                <span>저장 이벤트</span>
                <strong>{serverAnalysisResult ? serverAnalysisResult.storedEventCount : "-"}</strong>
              </div>
              <div>
                <span>마지막 저장</span>
                <strong>
                  {serverAnalysisResult
                    ? `Q${serverAnalysisResult.questionSequenceNo} ${serverAnalysisResult.syncedAtLabel}`
                    : "-"}
                </strong>
              </div>
            </div>
            <div className="session-summary camera-summary camera-summary-runtime">
              <div>
                <span>MediaPipe 실행</span>
                <strong>{mediaPipeRuntimeLabel}</strong>
              </div>
              <div>
                <span>실행 장치 설정</span>
                <strong>{mediaPipeDelegatePreferenceLabel}</strong>
              </div>
            </div>
            <div className="session-summary camera-summary camera-summary-runtime">
              <div>
                <span>Server MediaPipe</span>
                <strong>{serverMediaPipeRuntimeLabel}</strong>
              </div>
              <div>
                <span>Server Delegate</span>
                <strong>{serverMediaPipeDelegatePreferenceLabel}</strong>
              </div>
            </div>
            {cameraError ? <p className="camera-error">{cameraError}</p> : null}
            <div className="action-row camera-action-row">
              <button
                type="button"
                onClick={() => void startCamera()}
                disabled={isBusy || cameraState === "requesting"}
              >
                {cameraState === "ready"
                    ? "카메라 다시 연결"
                  : cameraState === "requesting"
                    ? "연결 중..."
                    : "카메라 켜기"}
              </button>
              <button
                type="button"
                onClick={stopCamera}
                disabled={isBusy || cameraState === "idle"}
                className="button-ghost"
              >
                카메라 끄기
              </button>
              <button
                type="button"
                onClick={() => handlePostureModePreferenceChange("auto")}
                disabled={cameraState !== "ready" || postureModePreference === "auto"}
                className={postureModePreference === "auto" ? "" : "button-ghost"}
              >
                AUTO
              </button>
              <button
                type="button"
                onClick={() => handlePostureModePreferenceChange("force-local")}
                disabled={cameraState !== "ready" || postureModePreference === "force-local"}
                className="button-ghost"
              >
                브라우저 모드
              </button>
              <button
                type="button"
                onClick={() => handlePostureModePreferenceChange("force-server")}
                disabled={cameraState !== "ready" || postureModePreference === "force-server"}
                className="button-ghost"
              >
                서버 모드
              </button>
              <button
                type="button"
                onClick={() => setOverlayEnabled((current) => !current)}
                disabled={cameraState !== "ready"}
                className="button-ghost"
              >
                {overlayEnabled ? "오버레이 끄기" : "오버레이 켜기"}
              </button>
            </div>
            <div className="action-row camera-action-row camera-delegate-row">
              <button
                type="button"
                onClick={() => void handleMediaPipeDelegateChange("auto")}
                disabled={cameraState !== "ready" || mediaPipeDelegatePreference === "auto"}
                className={mediaPipeDelegatePreference === "auto" ? "" : "button-ghost"}
              >
                MediaPipe 자동
              </button>
              <button
                type="button"
                onClick={() => void handleMediaPipeDelegateChange("gpu")}
                disabled={cameraState !== "ready" || mediaPipeDelegatePreference === "gpu"}
                className={mediaPipeDelegatePreference === "gpu" ? "" : "button-ghost"}
              >
                MediaPipe GPU
              </button>
              <button
                type="button"
                onClick={() => void handleMediaPipeDelegateChange("cpu")}
                disabled={cameraState !== "ready" || mediaPipeDelegatePreference === "cpu"}
                className={mediaPipeDelegatePreference === "cpu" ? "" : "button-ghost"}
              >
                MediaPipe CPU
              </button>
            </div>
            <div className="action-row camera-action-row camera-delegate-row">
              <button
                type="button"
                onClick={() => handleServerMediaPipeDelegateChange("gpu")}
                disabled={!serverGpuSupported || cameraState !== "ready" || serverMediaPipeDelegatePreference === "gpu"}
                className={serverMediaPipeDelegatePreference === "gpu" ? "" : "button-ghost"}
              >
                서버 MediaPipe GPU
              </button>
              <button
                type="button"
                onClick={() => handleServerMediaPipeDelegateChange("cpu")}
                disabled={cameraState !== "ready" || serverMediaPipeDelegatePreference === "cpu"}
                className={serverMediaPipeDelegatePreference === "cpu" ? "" : "button-ghost"}
              >
                서버 MediaPipe CPU
              </button>
            </div>
            <p className="inline-note server-delegate-note">
              현재 서버 빌드는 CPU만 지원합니다. 서버 MediaPipe GPU는 비활성화되어 있습니다.
            </p>
            <p className="inline-note">
              {postureModePreference === "force-server"
                ? "서버 모드가 활성화되어 자세 샘플마다 백엔드로 전송하고 서버에서 MediaPipe 분석을 수행합니다."
                : postureModePreference === "force-local"
                  ? "브라우저 모드가 활성화되어 이 기기에서 자세 분석을 직접 수행하고 요약만 백엔드로 전송합니다."
                  : postureMode === "local"
                    ? "로컬 모드는 이 기기에서 자세 분석을 직접 수행하고 요약을 백엔드로 전송하는 방식입니다."
                    : "서버 보조 모드는 로컬 분석 속도가 낮아 현재 비디오 프레임을 백엔드로 보내고 서버에서 MediaPipe 분석을 대신 수행하는 방식입니다."}
            </p>
            {isServerFallback ? (
              <p className="mode-alert">
                현재 서버 보조 분석이 활성화되어 있습니다. 로컬 추론 성능이 목표치보다 낮아 백엔드 분석이 대신 수행 중입니다.
              </p>
            ) : null}
            </div>
          </div>

            <div className="question-card question-card-main">
            <div className="question-meta">
              <span>현재 질문</span>
              <strong>
                {question ? `Q${question.sequence_no}` : "시작 대기"}
              </strong>
            </div>
            <p>{question?.question_text ?? "아직 불러온 질문이 없습니다."}</p>
            <textarea
              value={answerText}
              onChange={(event) => setAnswerText(event.target.value)}
              placeholder="지원자의 답변을 여기에 입력하세요."
              disabled={isBusy || !question}
            />
            <div className="action-row">
              <button
                type="button"
                onClick={handleSubmitAnswer}
                disabled={isBusy || !question || !answerText.trim()}
              >
                {busyAction === "submit-answer" ? "제출 중..." : "답변 제출"}
              </button>
              <button
                type="button"
                onClick={handleNextQuestion}
                disabled={isBusy || !question}
              >
                {busyAction === "next-question" ? "불러오는 중..." : "다음 질문"}
              </button>
            </div>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <p className="panel-kicker">관리</p>
            <h2>실행 현황</h2>
          </div>
          <div className="metric-grid">
            <div className="metric-card">
              <span>활성 로그인</span>
              <strong>{adminOverview?.active_login_count ?? 0}</strong>
            </div>
            <div className="metric-card">
              <span>진행 중 면접</span>
              <strong>{adminOverview?.active_interview_count ?? 0}</strong>
            </div>
            <div className="metric-card">
              <span>안전 동시 처리</span>
              <strong>{adminOverview?.safe_estimated_concurrency_now ?? 0}</strong>
            </div>
            <div className="metric-card">
              <span>병목 지점</span>
              <strong>{adminOverview?.bottleneck_component ?? "알 수 없음"}</strong>
            </div>
          </div>

          <div className="report-card">
            <div className="question-meta">
              <span>면접 리포트</span>
              <strong>{report?.status ?? "준비 안 됨"}</strong>
            </div>
            <p>{report?.report?.summary ?? "전체 면접을 완료하면 리포트를 불러올 수 있습니다."}</p>
            <div className="report-stats">
              <span>점수: {report?.report?.overall_score ?? "-"}</span>
              <span>응답 수: {report?.report?.answered_question_count ?? 0}</span>
              <span>제출 수: {report?.report?.submitted_answer_count ?? 0}</span>
            </div>
          </div>

          <div className="log-card">
            <div className="question-meta">
              <span>활동 로그</span>
              <strong>{activityLog.length}</strong>
            </div>
            <ul>
              {activityLog.map((entry, index) => (
                <li key={`${index}-${entry}`}>{entry}</li>
              ))}
            </ul>
          </div>
        </article>
      </section>
    </main>
  );
}
