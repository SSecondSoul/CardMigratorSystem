# formal_30_v3 frozen protocol

Frozen date: 2026-10-22

## 1. Purpose and evidence boundary

`formal_30_v3` measures the generalized Vue-to-San pipeline after the post-hoc
remediation derived from `formal_30_v1` and the targeted manual `formal_30_v2`
review. The v1 and v2 samples are development evidence for this comparison and
must not be counted as an untouched evaluation of the remediated pipeline.

The v3 holdout contains 30 samples selected only from the 61 entries recorded as
`development_unseen` in the parent split. It excludes all nine pilot samples and
all 30 formal_30_v1 samples. Selection happened before any v3 model run or result
inspection.

This is a fixed test protocol. After the first v3 model call:

- do not change Prompt, SSM extraction, Validator, renderer, repair loop, model,
  temperature, or maximum repair rounds;
- do not use `--force` or selectively replace failed results;
- infrastructure failures may resume through the unchanged checkpoint command;
- any algorithm or evaluator correction requires a new batch and protocol version;
- manual browser review, if performed, is reported separately from automatic pass rates.

## 2. Frozen configuration

- Batch: `formal_30_v3`
- Samples: 30 (`simple=10`, `medium=10`, `complex=10`)
- Maximum repair rounds: 3
- Provider: `qwen`
- Model: `qwen-plus`
- Pipeline outputs include full state for evidence reconstruction.

The reference San files are frozen only for later blinded analysis. They are not
provided to generation or repair requests.

## 3. Primary metrics

1. Automatic final pass rate among all 30 configured samples.
2. Automatic final pass rate among normally completed samples.
3. Initial pass rate and repaired-to-pass count.
4. Pass rate by simple, medium, and complex strata.
5. Repair-round and token totals.
6. Execution-error and final validation/visual error-code distributions.

The v1-to-v3 comparison is a between-sample comparison over two independently
frozen, complexity-balanced holdouts. It is not a paired rerun of the same 30
components and must be described with that limitation.

## 4. Selection algorithm

Within each complexity stratum, greedily choose the component that adds the most
previously uncovered feature-signature tags. Break ties by total signature size,
then by stable order in the parent split. Select 10 per stratum.

## 5. Samples

| ID | Component | Complexity |
| --- | --- | --- |
| volume_control | VolumeControl | simple |
| NotificationCard | NotificationCard | simple |
| reading_progress_card | ReadingProgressCard | simple |
| text_length_gauge | TextLengthGauge | simple |
| budget_threshold | BudgetThreshold | simple |
| otp_code_input | OtpCodeInput | simple |
| stock_reservation_badge | StockReservationBadge | simple |
| tip_split_calculator | TipSplitCalculator | simple |
| status_switch | StatusSwitch | simple |
| search_clear_field | SearchClearField | simple |
| batch_renamer | BatchRenamer | medium |
| habit_week_tracker | HabitWeekTracker | medium |
| playback_queue | PlaybackQueue | medium |
| seat_booking_map | SeatBookingMap | medium |
| breadcrumb_navigator | BreadcrumbNavigator | medium |
| shipping_estimator | ShippingEstimator | medium |
| meeting_poll_scheduler | MeetingPollScheduler | medium |
| course_module_accordion | CourseModuleAccordion | medium |
| delivery_route_timeline | DeliveryRouteTimeline | medium |
| audio_segment_marker | AudioSegmentMarker | medium |
| analytics_dashboard | AnalyticsDashboard | complex |
| incident_response_board | IncidentResponseBoard | complex |
| fleet_dispatch_console | FleetDispatchConsole | complex |
| TaskManager | TaskManager | complex |
| MonitoringDashboard | MonitoringDashboard | complex |
| rule_builder | RuleBuilder | complex |
| access_matrix | AccessMatrix | complex |
| localization_workspace | LocalizationWorkspace | complex |
| trip_itinerary_planner | TripItineraryPlanner | complex |
| schema_mapping_workbench | SchemaMappingWorkbench | complex |

## 6. Preflight

```powershell
python data/experiments/protocols/formal_30_v3_frozen_20261022/verify_protocol.py --live
python -m unittest discover -s tests -p "test_*.py" -v
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v3.json `
  --include-state `
  --dry-run
```

All three commands must pass before the first model call.

## 7. Formal run

Start `local_server` in a terminal with `LLM_API_KEY`, `LLM_PROVIDER=qwen`, and
`LLM_MODEL=qwen-plus`, then run in another activated `cardmig` terminal:

```powershell
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v3.json `
  --include-state
```

Use exactly the same command to resume an infrastructure interruption. Do not add
`--force`.

## 8. Fixed outputs

- Generated code: `data/experiments/pipeline/batches/formal_30_v3/`
- Per-sample reports: `data/experiments/repair_reports/batches/formal_30_v3/`
- Checkpoint/summary: `data/experiments/batch_reports/formal_30_v3_summary.json`
- Later frozen result snapshot: a new timestamped `formal_30_v3_results_*` directory
