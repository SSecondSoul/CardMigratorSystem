-- FUTURE MYSQL PREPARATION ONLY. Runtime is currently tested on SQLite.
CREATE DATABASE `cardmigrator_multi_user_staging` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
USE `cardmigrator_multi_user_staging`;

CREATE TABLE `alembic_version` (
  `version_num` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `auth_throttle` (
  `bucket` VARCHAR(64) NOT NULL,
  `window_start` DOUBLE NOT NULL,
  `failures` INTEGER NOT NULL,
  PRIMARY KEY (`bucket`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `source_inputs` (
  `id` VARCHAR(32) NOT NULL,
  `filename` VARCHAR(120) NOT NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `users` (
  `id` VARCHAR(32) NOT NULL,
  `username` VARCHAR(64) NOT NULL,
  `username_normalized` VARCHAR(64) NOT NULL,
  `display_name` VARCHAR(120) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` VARCHAR(16) NOT NULL,
  `is_active` BOOLEAN NOT NULL,
  `must_change_password` BOOLEAN NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `password_changed_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_users_1` UNIQUE (`username_normalized`),
  CONSTRAINT `ck_users_1` CHECK (role IN ('admin','user'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `worker_health` (
  `id` VARCHAR(32) NOT NULL,
  `pid` INTEGER NOT NULL,
  `state` VARCHAR(24) NOT NULL,
  `run_id` VARCHAR(32) NULL,
  `last_seen` DOUBLE NOT NULL,
  `binding_sha256` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `audit_logs` (
  `id` VARCHAR(32) NOT NULL,
  `actor_id` VARCHAR(32) NULL,
  `action` VARCHAR(80) NOT NULL,
  `target_id` VARCHAR(100) NULL,
  `created_at` DOUBLE NOT NULL,
  `details` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_audit_logs_1` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `auth_sessions` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `token_sha256` VARCHAR(64) NOT NULL,
  `origin` VARCHAR(240) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `expires_at` DOUBLE NOT NULL,
  `revoked_at` DOUBLE NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_auth_sessions_1` UNIQUE (`token_sha256`),
  CONSTRAINT `fk_auth_sessions_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `input_owners` (
  `input_id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `byte_size` INTEGER NOT NULL,
  PRIMARY KEY (`input_id`),
  CONSTRAINT `uq_input_owners_1` UNIQUE (`user_id`, `input_id`),
  CONSTRAINT `fk_input_owners_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_input_owners_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_jobs` (
  `id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request` JSON NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `binding` JSON NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `stage` VARCHAR(40) NOT NULL,
  `stop_reason` VARCHAR(120) NOT NULL,
  `state` JSON NOT NULL,
  `cancel_requested` BOOLEAN NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `updated_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_migration_jobs_1` UNIQUE (`idempotency_key`),
  CONSTRAINT `fk_migration_jobs_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `tasks` (
  `id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_tasks_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `user_limits` (
  `user_id` VARCHAR(32) NOT NULL,
  `max_active_jobs` INTEGER NOT NULL,
  `daily_jobs` INTEGER NOT NULL,
  `daily_model_calls` INTEGER NOT NULL,
  `daily_tokens_soft` INTEGER NOT NULL,
  `storage_bytes` INTEGER NOT NULL,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_user_limits_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_user_limits_1` CHECK (max_active_jobs >= 0 AND daily_jobs >= 0 AND daily_model_calls >= 0 AND daily_tokens_soft >= 0 AND storage_bytes >= 0)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `user_usage_daily` (
  `user_id` VARCHAR(32) NOT NULL,
  `day` VARCHAR(10) NOT NULL,
  `jobs_count` INTEGER NOT NULL,
  `calls_count` INTEGER NOT NULL,
  `known_tokens` INTEGER NOT NULL,
  PRIMARY KEY (`user_id`, `day`),
  CONSTRAINT `fk_user_usage_daily_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `job_owners` (
  `job_id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`job_id`),
  CONSTRAINT `fk_job_owners_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_job_owners_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_feedback` (
  `id` VARCHAR(32) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `revision_sha256` VARCHAR(64) NOT NULL,
  `passed` BOOLEAN NOT NULL,
  `changed_lines` INTEGER NULL,
  `elapsed_seconds` DOUBLE NULL,
  `notes` VARCHAR(4000) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_migration_feedback_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(40) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `fk_migration_files_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_model_calls` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `ordinal` INTEGER NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `receipt` JSON NULL,
  `started_at` DOUBLE NOT NULL,
  `finished_at` DOUBLE NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_migration_model_calls_1` UNIQUE (`job_id`, `ordinal`),
  CONSTRAINT `fk_migration_model_calls_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `runs` (
  `id` VARCHAR(32) NOT NULL,
  `task_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `request` JSON NOT NULL,
  `binding` JSON NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `outcome` VARCHAR(32) NOT NULL,
  `final_revision_id` VARCHAR(80) NULL,
  `cancel_requested` BOOLEAN NOT NULL,
  `stop_reason` VARCHAR(120) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_runs_1` UNIQUE (`task_id`, `idempotency_key`),
  CONSTRAINT `fk_runs_1` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `artifact_revisions` (
  `id` VARCHAR(80) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `parent_id` VARCHAR(80) NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `source_kind` VARCHAR(40) NOT NULL,
  `fixture_assertions` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_artifact_revisions_1` UNIQUE (`id`, `run_id`),
  CONSTRAINT `fk_artifact_revisions_1` FOREIGN KEY (`parent_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_artifact_revisions_2` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `attempts` (
  `id` VARCHAR(100) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(40) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `result` JSON NULL,
  `started_at` DOUBLE NOT NULL,
  `model_tokens` INTEGER NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_attempts_1` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `run_events` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,
  `run_id` VARCHAR(32) NOT NULL,
  `event_key` VARCHAR(120) NOT NULL,
  `kind` VARCHAR(40) NOT NULL,
  `details` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_run_events_1` UNIQUE (`run_id`, `event_key`),
  CONSTRAINT `fk_run_events_1` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `ssm_extractions` (
  `id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `referenced_run_id` VARCHAR(32) NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `request` JSON NOT NULL,
  `stop_reason` VARCHAR(100) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_ssm_extractions_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ssm_extractions_2` FOREIGN KEY (`referenced_run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_ssm_extractions_1` CHECK (status IN ('prepared','started','received','completed','blocked','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `worker_locks` (
  `id` VARCHAR(20) NOT NULL,
  `owner` VARCHAR(32) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `expires_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_worker_locks_1` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `candidate_decisions` (
  `id` VARCHAR(100) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `previous_id` VARCHAR(80) NOT NULL,
  `candidate_id` VARCHAR(80) NOT NULL,
  `action` VARCHAR(24) NOT NULL,
  `reason` VARCHAR(120) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_candidate_decisions_1` FOREIGN KEY (`candidate_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_candidate_decisions_2` FOREIGN KEY (`previous_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_candidate_decisions_3` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `evaluations` (
  `id` VARCHAR(100) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `revision_id` VARCHAR(80) NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `scope` VARCHAR(80) NOT NULL,
  `fixture_assertions` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_evaluations_1` FOREIGN KEY (`revision_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_evaluations_2` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_approvals` (
  `id` VARCHAR(32) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request` JSON NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `expires_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_approvals_1` UNIQUE (`extraction_id`, `idempotency_key`),
  CONSTRAINT `fk_generation_approvals_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_approvals_1` CHECK (status IN ('pending','approved','revoked','consumed'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_jobs` (
  `id` VARCHAR(32) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `request` JSON NOT NULL,
  `stop_reason` VARCHAR(100) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_jobs_1` UNIQUE (`extraction_id`, `idempotency_key`),
  CONSTRAINT `fk_generation_jobs_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_generation_jobs_2` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_jobs_1` CHECK (status IN ('prepared','started','received','completed','blocked','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `provider_generation_jobs` (
  `id` VARCHAR(32) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request` JSON NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `stop_reason` VARCHAR(100) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_provider_generation_jobs_1` UNIQUE (`extraction_id`, `idempotency_key`),
  CONSTRAINT `fk_provider_generation_jobs_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_provider_generation_jobs_1` CHECK (status IN ('prepared','started','received','completed','blocked','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `ssm_extraction_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_ssm_extraction_files_1` UNIQUE (`extraction_id`, `kind`),
  CONSTRAINT `fk_ssm_extraction_files_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_ssm_extraction_files_1` CHECK (kind IN ('request','ssm','receipt'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_approval_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `approval_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_generation_approval_files_1` UNIQUE (`approval_id`, `kind`),
  CONSTRAINT `fk_generation_approval_files_1` FOREIGN KEY (`approval_id`) REFERENCES `generation_approvals` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_approval_files_1` CHECK (kind IN ('request','approval','revocation','claim'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_attempts` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `started_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_attempts_1` UNIQUE (`job_id`),
  CONSTRAINT `fk_generation_attempts_1` FOREIGN KEY (`job_id`) REFERENCES `generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_attempts_1` CHECK (status IN ('started','received','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_generation_files_1` UNIQUE (`job_id`, `kind`),
  CONSTRAINT `fk_generation_files_1` FOREIGN KEY (`job_id`) REFERENCES `generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_files_1` CHECK (kind IN ('request','receipt','candidate'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `provider_generation_attempts` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `started_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_provider_generation_attempts_1` UNIQUE (`job_id`),
  CONSTRAINT `fk_provider_generation_attempts_1` FOREIGN KEY (`job_id`) REFERENCES `provider_generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_provider_generation_attempts_1` CHECK (status IN ('started','received','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `provider_generation_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_provider_generation_files_1` UNIQUE (`job_id`, `kind`),
  CONSTRAINT `fk_provider_generation_files_1` FOREIGN KEY (`job_id`) REFERENCES `provider_generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_provider_generation_files_1` CHECK (kind IN ('plan','request','response','receipt','candidate'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_candidates` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `parent_id` VARCHAR(80) NULL,
  `source_kind` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_candidates_1` UNIQUE (`job_id`),
  CONSTRAINT `uq_generation_candidates_2` UNIQUE (`relative_path`),
  CONSTRAINT `fk_generation_candidates_1` FOREIGN KEY (`job_id`) REFERENCES `generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_generation_candidates_2` FOREIGN KEY (`relative_path`) REFERENCES `generation_files` (`relative_path`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_candidates_1` CHECK (parent_id IS NULL),
  CONSTRAINT `ck_generation_candidates_2` CHECK (source_kind = 'offline_client_test')
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
