const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1";

const ACCESS_TOKEN_STORAGE_KEY = "ai-interview-access-token";

export type UserProfile = {
  id: string;
  display_name: string;
  role: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: UserProfile;
};

export type JobCategory = {
  code: string;
  name_ko: string;
};

export type InterviewSession = {
  session_id: string;
  status: string;
  question_count: number;
  answer_time_limit_sec: number;
  allow_retry: boolean;
};

export type InterviewQuestion = {
  id: string;
  sequence_no: number;
  question_text: string;
};

export type StartInterviewResponse = {
  session_id: string;
  status: string;
  question: InterviewQuestion;
};

export type SubmitAnswerResponse = {
  session_id: string;
  question_id: string;
  attempt_no: number;
  accepted: boolean;
  queued_stt: boolean;
  queued_evaluation: boolean;
  next_action: string;
};

export type NextQuestionResponse = {
  session_id: string;
  status: string;
  question: InterviewQuestion | null;
  report_ready: boolean;
};

export type InterviewReportResponse = {
  session_id: string;
  status: string;
  report: {
    overall_score: number;
    summary: string;
    answered_question_count: number;
    submitted_answer_count: number;
  } | null;
};

export type AdminOverview = {
  active_login_count: number;
  active_interview_count: number;
  validated_max_concurrency: number;
  safe_estimated_concurrency_now: number;
  bottleneck_component: string;
};

export type PostureSubmissionResponse = {
  session_id: string;
  question_id: string;
  status: string;
  stored_event_count: number;
  mediapipe_runtime?: string | null;
};

export type PostureEventPayload = {
  event_type: string;
  severity: "low" | "medium" | "high";
  started_at_ms: number;
  ended_at_ms: number;
};

function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}

function getAuthHeaders(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getAccessToken,

  setAccessToken(token: string | null) {
    if (token) {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
      return;
    }
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  },

  login(email: string, password: string) {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  logout() {
    return request<{ status: string }>("/auth/logout", {
      method: "POST",
    });
  },

  me() {
    return request<UserProfile>("/auth/me");
  },

  getJobCategories() {
    return request<JobCategory[]>("/job-categories");
  },

  createInterview(payload: {
    job_category_code: string;
    mode: "live" | "recorded";
    question_count: number;
    answer_time_limit_sec: number;
    allow_retry: boolean;
  }) {
    return request<InterviewSession>("/interviews", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  startInterview(sessionId: string) {
    return request<StartInterviewResponse>(`/interviews/${sessionId}/start`, {
      method: "POST",
    });
  },

  submitTextAnswer(
    sessionId: string,
    questionId: string,
    payload: {
      text: string;
      attempt_no: number;
      is_final_attempt: boolean;
    },
  ) {
    return request<SubmitAnswerResponse>(
      `/interviews/${sessionId}/questions/${questionId}/answers/text`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  nextQuestion(sessionId: string, questionId: string) {
    return request<NextQuestionResponse>(
      `/interviews/${sessionId}/questions/${questionId}/next`,
      {
        method: "POST",
      },
    );
  },

  getReport(sessionId: string) {
    return request<InterviewReportResponse>(`/interviews/${sessionId}/report`);
  },

  getAdminOverview() {
    return request<AdminOverview>("/admin/overview");
  },

  submitPostureFallbackSamples(payload: {
    session_id: string;
    question_id: string;
    sample_count: number;
    source_mode: "fallback" | "server";
    mediapipe_delegate_preference?: "auto" | "cpu" | "gpu";
    landmarks_summary: Record<string, unknown>;
    frame_jpeg_base64?: string;
  }) {
    return request<PostureSubmissionResponse>("/posture/fallback-samples", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  submitPostureLocalSummary(payload: {
    session_id: string;
    question_id: string;
    source_mode: "local" | "server";
    sample_fps: number;
    mediapipe_delegate_preference?: "auto" | "cpu" | "gpu";
    summary: {
      shoulder_asymmetry_score: number;
      gaze_away_ratio: number;
      hand_face_event_count: number;
      upper_body_motion_score: number;
    };
    events: PostureEventPayload[];
  }) {
    return request<PostureSubmissionResponse>("/posture/local-summary", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
