# AI Interview v2 Database Schema Draft

## 1. Core Tables

### `users`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `email` | varchar unique | login id |
| `password_hash` | varchar | local auth |
| `display_name` | varchar | |
| `role` | varchar | `user` or `admin` |
| `is_active` | boolean | |
| `last_login_at` | timestamptz | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `job_categories`
| column | type | notes |
|---|---|---|
| `id` | smallint pk | |
| `code` | varchar unique | e.g. `it`, `finance` |
| `name_ko` | varchar | |
| `sort_order` | smallint | |
| `is_active` | boolean | |

### `login_sessions`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `user_id` | uuid fk users.id | |
| `access_token_jti` | varchar unique | token tracking |
| `started_at` | timestamptz | |
| `last_seen_at` | timestamptz | |
| `ended_at` | timestamptz nullable | |
| `client_type` | varchar | `electron` |
| `client_version` | varchar | |
| `device_label` | varchar nullable | |
| `ip_address` | inet nullable | optional |

### `interview_sessions`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `user_id` | uuid fk users.id | |
| `job_category_id` | smallint fk job_categories.id | |
| `mode` | varchar | `live` or `recorded` |
| `status` | varchar | `pending`, `in_progress`, `evaluating`, `completed`, `failed` |
| `question_count` | smallint | default 5 |
| `answer_time_limit_sec` | integer | default 60 |
| `allow_retry` | boolean | default true |
| `started_at` | timestamptz nullable | |
| `completed_at` | timestamptz nullable | |
| `final_score` | numeric(5,2) nullable | |
| `report_status` | varchar | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `questions`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `interview_session_id` | uuid fk interview_sessions.id | |
| `sequence_no` | smallint | 1..5 |
| `question_text` | text | |
| `llm_prompt_version` | varchar | |
| `generated_at` | timestamptz | |

### `answers`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `question_id` | uuid fk questions.id | |
| `answer_type` | varchar | `text` or `voice` |
| `attempt_no` | smallint | retry tracking |
| `text_content` | text nullable | user text or STT text |
| `audio_file_path` | varchar nullable | stored file ref |
| `duration_sec` | numeric(8,2) nullable | |
| `submitted_at` | timestamptz | |
| `is_final_attempt` | boolean | |

### `speech_metrics`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `answer_id` | uuid fk answers.id | |
| `stt_model` | varchar | `gpt-4o-transcribe` |
| `stt_latency_ms` | integer | |
| `transcript_confidence_note` | varchar nullable | optional summary |
| `speaking_rate_wpm` | numeric(8,2) | |
| `pause_count` | integer | |
| `pause_ratio` | numeric(6,4) | |
| `filler_count` | integer | |
| `repetition_score` | numeric(6,4) | |
| `created_at` | timestamptz | |

### `posture_metrics`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `interview_session_id` | uuid fk interview_sessions.id | |
| `question_id` | uuid fk questions.id nullable | live mode linking |
| `source_mode` | varchar | `local` or `server` |
| `sample_fps` | numeric(4,2) | default 5 |
| `shoulder_asymmetry_score` | numeric(6,4) | |
| `torso_tilt_score` | numeric(6,4) | |
| `gaze_away_ratio` | numeric(6,4) | |
| `hand_face_event_count` | integer | |
| `upper_body_motion_score` | numeric(6,4) | |
| `visibility_drop_ratio` | numeric(6,4) | |
| `created_at` | timestamptz | |

### `posture_events`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `interview_session_id` | uuid fk interview_sessions.id | |
| `question_id` | uuid fk questions.id nullable | |
| `event_type` | varchar | `shoulder_tilt`, `gaze_away`, etc. |
| `severity` | varchar | `low`, `medium`, `high` |
| `started_at_ms` | integer | relative timeline |
| `ended_at_ms` | integer | |
| `evidence_json` | jsonb | supporting values |
| `created_at` | timestamptz | |

### `feedback_reports`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `interview_session_id` | uuid fk interview_sessions.id unique | |
| `overall_score` | numeric(5,2) | |
| `content_score` | numeric(5,2) | |
| `speech_score` | numeric(5,2) | |
| `posture_score` | numeric(5,2) | |
| `strength_summary` | text | |
| `improvement_summary` | text | |
| `full_report_markdown` | text | |
| `generated_at` | timestamptz | |

### `processing_jobs`
| column | type | notes |
|---|---|---|
| `id` | uuid pk | |
| `interview_session_id` | uuid fk interview_sessions.id nullable | |
| `job_type` | varchar | `stt`, `posture`, `evaluation`, `report` |
| `status` | varchar | `queued`, `running`, `completed`, `failed` |
| `current_stage` | varchar | admin display |
| `queue_name` | varchar | |
| `started_at` | timestamptz nullable | |
| `completed_at` | timestamptz nullable | |
| `error_message` | text nullable | |
| `metrics_json` | jsonb nullable | |
| `created_at` | timestamptz | |

### `system_metrics`
| column | type | notes |
|---|---|---|
| `id` | bigserial pk | |
| `captured_at` | timestamptz | |
| `active_login_count` | integer | |
| `active_interview_count` | integer | |
| `api_p95_latency_ms` | integer | |
| `queue_wait_p95_ms` | integer | |
| `stt_avg_turnaround_ms` | integer | |
| `posture_avg_turnaround_ms` | integer | |
| `validated_max_concurrency` | integer | |
| `safe_estimated_concurrency_now` | integer | bottleneck min result |
| `bottleneck_component` | varchar | `api`, `worker`, `stt`, `posture` |

## 2. Initial Seed Data
- `job_categories`
  - 경영/인사
  - 회계
  - IT
  - R&D
  - 제조
  - 유통
  - 공공
  - 일반 사무

## 3. Important Relationships
- one `user` -> many `login_sessions`
- one `user` -> many `interview_sessions`
- one `interview_session` -> many `questions`
- one `question` -> many `answers`
- one `answer` -> one `speech_metrics`
- one `interview_session` -> many `posture_events`
- one `interview_session` -> one `feedback_reports`

## 4. Suggested Indexes
- `login_sessions (user_id, ended_at)`
- `interview_sessions (user_id, status, created_at desc)`
- `questions (interview_session_id, sequence_no)`
- `answers (question_id, attempt_no desc)`
- `processing_jobs (status, queue_name, created_at)`
- `system_metrics (captured_at desc)`

## 5. Retention Notes
- keep final reports long-term
- consider TTL/archive policy for raw uploaded media
- keep detailed runtime metrics at lower granularity after a retention window
