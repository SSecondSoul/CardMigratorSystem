-- Read-only; expect 34 tables, zero missing/extra tables and zero rows in every table.
SELECT VERSION() AS mysql_version, @@hostname AS db_host, @@port AS db_port, @@SESSION.sql_mode AS sql_mode;
SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='cardmigrator_multi_user_staging';
SELECT COLLATION_NAME, PAD_ATTRIBUTE FROM information_schema.COLLATIONS WHERE COLLATION_NAME='utf8mb4_0900_bin';
SELECT COUNT(*) AS table_count_must_be_34 FROM information_schema.TABLES WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' AND TABLE_TYPE='BASE TABLE';
WITH expected AS (
SELECT 'alembic_version' AS table_name
UNION ALL
SELECT 'auth_throttle' AS table_name
UNION ALL
SELECT 'source_inputs' AS table_name
UNION ALL
SELECT 'users' AS table_name
UNION ALL
SELECT 'worker_health' AS table_name
UNION ALL
SELECT 'audit_logs' AS table_name
UNION ALL
SELECT 'auth_sessions' AS table_name
UNION ALL
SELECT 'input_owners' AS table_name
UNION ALL
SELECT 'migration_jobs' AS table_name
UNION ALL
SELECT 'tasks' AS table_name
UNION ALL
SELECT 'user_limits' AS table_name
UNION ALL
SELECT 'user_usage_daily' AS table_name
UNION ALL
SELECT 'job_owners' AS table_name
UNION ALL
SELECT 'migration_feedback' AS table_name
UNION ALL
SELECT 'migration_files' AS table_name
UNION ALL
SELECT 'migration_model_calls' AS table_name
UNION ALL
SELECT 'runs' AS table_name
UNION ALL
SELECT 'artifact_revisions' AS table_name
UNION ALL
SELECT 'attempts' AS table_name
UNION ALL
SELECT 'run_events' AS table_name
UNION ALL
SELECT 'ssm_extractions' AS table_name
UNION ALL
SELECT 'worker_locks' AS table_name
UNION ALL
SELECT 'candidate_decisions' AS table_name
UNION ALL
SELECT 'evaluations' AS table_name
UNION ALL
SELECT 'generation_approvals' AS table_name
UNION ALL
SELECT 'generation_jobs' AS table_name
UNION ALL
SELECT 'provider_generation_jobs' AS table_name
UNION ALL
SELECT 'ssm_extraction_files' AS table_name
UNION ALL
SELECT 'generation_approval_files' AS table_name
UNION ALL
SELECT 'generation_attempts' AS table_name
UNION ALL
SELECT 'generation_files' AS table_name
UNION ALL
SELECT 'provider_generation_attempts' AS table_name
UNION ALL
SELECT 'provider_generation_files' AS table_name
UNION ALL
SELECT 'generation_candidates' AS table_name
)
SELECT e.table_name AS missing_table FROM expected e LEFT JOIN information_schema.TABLES t ON t.TABLE_SCHEMA='cardmigrator_multi_user_staging' AND t.TABLE_NAME=e.table_name AND t.TABLE_TYPE='BASE TABLE' WHERE t.TABLE_NAME IS NULL;
WITH expected AS (
SELECT 'alembic_version' AS table_name
UNION ALL
SELECT 'auth_throttle' AS table_name
UNION ALL
SELECT 'source_inputs' AS table_name
UNION ALL
SELECT 'users' AS table_name
UNION ALL
SELECT 'worker_health' AS table_name
UNION ALL
SELECT 'audit_logs' AS table_name
UNION ALL
SELECT 'auth_sessions' AS table_name
UNION ALL
SELECT 'input_owners' AS table_name
UNION ALL
SELECT 'migration_jobs' AS table_name
UNION ALL
SELECT 'tasks' AS table_name
UNION ALL
SELECT 'user_limits' AS table_name
UNION ALL
SELECT 'user_usage_daily' AS table_name
UNION ALL
SELECT 'job_owners' AS table_name
UNION ALL
SELECT 'migration_feedback' AS table_name
UNION ALL
SELECT 'migration_files' AS table_name
UNION ALL
SELECT 'migration_model_calls' AS table_name
UNION ALL
SELECT 'runs' AS table_name
UNION ALL
SELECT 'artifact_revisions' AS table_name
UNION ALL
SELECT 'attempts' AS table_name
UNION ALL
SELECT 'run_events' AS table_name
UNION ALL
SELECT 'ssm_extractions' AS table_name
UNION ALL
SELECT 'worker_locks' AS table_name
UNION ALL
SELECT 'candidate_decisions' AS table_name
UNION ALL
SELECT 'evaluations' AS table_name
UNION ALL
SELECT 'generation_approvals' AS table_name
UNION ALL
SELECT 'generation_jobs' AS table_name
UNION ALL
SELECT 'provider_generation_jobs' AS table_name
UNION ALL
SELECT 'ssm_extraction_files' AS table_name
UNION ALL
SELECT 'generation_approval_files' AS table_name
UNION ALL
SELECT 'generation_attempts' AS table_name
UNION ALL
SELECT 'generation_files' AS table_name
UNION ALL
SELECT 'provider_generation_attempts' AS table_name
UNION ALL
SELECT 'provider_generation_files' AS table_name
UNION ALL
SELECT 'generation_candidates' AS table_name
)
SELECT t.TABLE_NAME AS unexpected_table FROM information_schema.TABLES t LEFT JOIN expected e ON e.table_name=t.TABLE_NAME WHERE t.TABLE_SCHEMA='cardmigrator_multi_user_staging' AND t.TABLE_TYPE='BASE TABLE' AND e.table_name IS NULL;
SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME;
SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE, ENFORCED FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, UPDATE_RULE, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT tc.TABLE_NAME, cc.CONSTRAINT_NAME, cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY tc.TABLE_NAME, cc.CONSTRAINT_NAME;
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
SELECT 'alembic_version' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`alembic_version`
UNION ALL
SELECT 'auth_throttle' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`auth_throttle`
UNION ALL
SELECT 'source_inputs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`source_inputs`
UNION ALL
SELECT 'users' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`users`
UNION ALL
SELECT 'worker_health' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`worker_health`
UNION ALL
SELECT 'audit_logs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`audit_logs`
UNION ALL
SELECT 'auth_sessions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`auth_sessions`
UNION ALL
SELECT 'input_owners' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`input_owners`
UNION ALL
SELECT 'migration_jobs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_jobs`
UNION ALL
SELECT 'tasks' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`tasks`
UNION ALL
SELECT 'user_limits' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`user_limits`
UNION ALL
SELECT 'user_usage_daily' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`user_usage_daily`
UNION ALL
SELECT 'job_owners' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`job_owners`
UNION ALL
SELECT 'migration_feedback' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_feedback`
UNION ALL
SELECT 'migration_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_files`
UNION ALL
SELECT 'migration_model_calls' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_model_calls`
UNION ALL
SELECT 'runs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`runs`
UNION ALL
SELECT 'artifact_revisions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`artifact_revisions`
UNION ALL
SELECT 'attempts' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`attempts`
UNION ALL
SELECT 'run_events' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`run_events`
UNION ALL
SELECT 'ssm_extractions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`ssm_extractions`
UNION ALL
SELECT 'worker_locks' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`worker_locks`
UNION ALL
SELECT 'candidate_decisions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`candidate_decisions`
UNION ALL
SELECT 'evaluations' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`evaluations`
UNION ALL
SELECT 'generation_approvals' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_approvals`
UNION ALL
SELECT 'generation_jobs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_jobs`
UNION ALL
SELECT 'provider_generation_jobs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`provider_generation_jobs`
UNION ALL
SELECT 'ssm_extraction_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`ssm_extraction_files`
UNION ALL
SELECT 'generation_approval_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_approval_files`
UNION ALL
SELECT 'generation_attempts' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_attempts`
UNION ALL
SELECT 'generation_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_files`
UNION ALL
SELECT 'provider_generation_attempts' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`provider_generation_attempts`
UNION ALL
SELECT 'provider_generation_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`provider_generation_files`
UNION ALL
SELECT 'generation_candidates' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_candidates`;
SELECT COUNT(*) AS alembic_rows_must_be_zero FROM `cardmigrator_multi_user_staging`.alembic_version;
