export const statuses = ['queued', 'running', 'review_required', 'finished', 'cancelled', 'execution_error'] as const
export type RunStatus = typeof statuses[number]
export type Profile = 'success' | 'repairable' | 'regression' | 'always_fail'
export interface Configuration { mode: string; production_ready: boolean; profiles: Profile[]; max_repair_rounds: number }
export interface Health { status: string; mode: string; production_ready: boolean; worker_readiness?: string }
export interface RunSummary { run_id: string; task_id: string; task_name: string; filename: string; status: RunStatus; outcome: string; created_at: number }
export interface RunInfo {
  run_id: string; task_id: string; status: RunStatus; outcome: string; mode: string; production_ready: boolean
  created_at: number; cancel_requested: boolean; final_revision_id: string | null; stop_reason: string; request_sha256: string
  request: { profile: Profile; max_repair_rounds: number }; binding: { implementation_sha256: string }
}
export interface EventRow { sequence: number; kind: string; details: { reason?: string; revision_id?: string; outcome?: string } }
export interface Report {
  run_id: string; status: RunStatus; outcome: string; final_revision_id: string | null; request_sha256: string; scope: string
  actual_model_calls: number; langsmith_uploaded: boolean; browser_evaluation: string
  attempts: { attempt_id: string; kind: string; status: string; model_tokens: number | null }[]
  revisions: { revision_id: string; parent_id: string | null; sha256: string; source_kind: string }[]
  candidate_decisions: { decision_id: string; candidate_id: string; previous_id: string; action: string; reason: string }[]
  fixture_audit: { status: string; accepted_revision_id: string | null; revision_order: string[] }
  contract_projection: { status: string; reason: string }
  contract_report: { status: string; required_dimensions: string[]; final_revision_id: string | null;
    final_results: { dimension: string; status: string; reason: string }[] } | null
}
export interface RunPage { items: RunSummary[]; next_cursor: string | null }
export interface Draft { name: string; filename: string; source: string; profile: Profile; rounds: number }
export interface Submission { draft: Draft; key: string; inputId?: string; taskId?: string }

export interface ExtractionSummary {
  extraction_id: string; input_id: string; referenced_run_id: string | null
  filename: string; status: string; created_at: number
}
export interface ExtractionPage { items: ExtractionSummary[]; next_cursor: string | null }
export interface ExtractionReport {
  extraction_id: string; status: string; stop_reason: string; request_sha256: string
  request: { protocol: string; source: { input_id: string; referenced_run_id: string | null; filename: string; source_sha256: string } }
  files: { kind: string; relative_path: string; sha256: string }[]
  receipt: { status: string; error?: string; limitations?: string[] } | null
  migration_quality_status: string; actual_model_calls: number; langsmith_uploaded: boolean; production_ready: boolean
  contract_evaluation: { status: string; evidence_level: string; evaluator_version: string | null; environment_sha256: string | null; diagnostics: { code: string; origin: string }[]; evidence_refs: string[] }
  contract_report: { status: string; final_results: { dimension: string; status: string; reason: string }[] } | null
  contract_projection: { status: string; reason: string; evidence_index: { path: string; sha256: string }[] }
}
