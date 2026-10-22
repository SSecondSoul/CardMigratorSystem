# formal_30_v3 automatic results

## Evidence boundary

- `formal_30_v3` is a new post-remediation holdout selected from the prior `development_unseen` pool before any v3 model call.
- It has zero overlap with pilot 9 and formal_30_v1.
- The frozen protocol passed 126 checksum checks after execution.
- The three generation timeouts were retried once with the unchanged checkpoint command and reproduced; no timeout, model, Prompt, or pipeline setting changed.
- Automatic pass does not imply browser interaction equivalence.

## Aggregate

| Metric | Result |
| --- | --- |
| Configured / completed | 30 / 27 |
| Passed / failed / execution errors | 18 / 9 / 3 |
| Pass rate among configured | 60.00% |
| Pass rate among completed | 66.67% |
| Initial passed / repaired to pass | 2 / 16 |
| Repair rounds total / average | 45 / 1.667 |
| Generation / repair / total tokens | 552,963 / 1,396,414 / 1,949,377 |

## Complexity

| Complexity | Configured | Completed | Passed | Failed | Errors | Configured rate | Completed rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| simple | 10 | 10 | 10 | 0 | 0 | 100.00% | 100.00% |
| medium | 10 | 10 | 7 | 3 | 0 | 70.00% | 70.00% |
| complex | 10 | 7 | 1 | 6 | 3 | 10.00% | 14.29% |

## Completed failures

| Sample | Complexity | Stop reason | Final validation errors | Final visual errors |
| --- | --- | --- | --- | --- |
| habit_week_tracker | medium | max_repair_rounds_reached | - | dom_structure_similarity_low |
| playback_queue | medium | max_repair_rounds_reached | - | dom_critical_attribute_mismatch |
| course_module_accordion | medium | max_repair_rounds_reached | hidden_template_reactive_dependency;hidden_template_reactive_dependency | dom_structure_similarity_low |
| incident_response_board | complex | no_repair_progress | vue_this_state | dom_critical_attribute_mismatch |
| rule_builder | complex | max_repair_rounds_reached | missing_prop_defaults | dom_structure_similarity_low;dom_critical_attribute_mismatch |
| access_matrix | complex | max_repair_rounds_reached | - | dom_structure_similarity_low |
| localization_workspace | complex | max_repair_rounds_reached | invalid_s_for_key_binding | dom_structure_similarity_low |
| trip_itinerary_planner | complex | max_repair_rounds_reached | hidden_template_reactive_dependency | dom_structure_similarity_low;dom_critical_attribute_mismatch |
| schema_mapping_workbench | complex | no_repair_progress | invalid_s_for_key_binding | dom_critical_attribute_mismatch |

## Execution errors

| Sample | Complexity | Error |
| --- | --- | --- |
| analytics_dashboard | complex | Generation request failed: HTTP 400 {"error":"The read operation timed out","ok":false} |
| TaskManager | complex | Generation request failed: HTTP 400 {"error":"The read operation timed out","ok":false} |
| MonitoringDashboard | complex | Generation request failed: HTTP 400 {"error":"The read operation timed out","ok":false} |

## Comparison with formal_30_v1

- Configured-sample pass rate: 53.33% in v1 and 60.00% in v3, a change of +6.67 percentage points.
- Completed-sample pass rate: 55.17% in v1 and 66.67% in v3, a change of +11.49 percentage points.
- Total model tokens: 2,469,176 in v1 and 1,949,377 in v3 (-21.05%).
- These are different complexity-balanced samples, so this is not a paired component-level comparison.
- Simple improved from 9/10 configured to 10/10; medium improved from 5/10 to 7/10; complex changed from 2/10 to 1/10 with three v3 generation timeouts.

## Interpretation

The generalized rules improved the overall configured and completed pass rates, but the gain is concentrated in simple and medium components. Complex migration remains the main limitation. The initial validator still reported `missing_prop_defaults` 25 times, and the final failures retain hidden reactive dependency, standalone `key` on `s-for`, state-access, DOM-structure, and critical-attribute errors. These v3 outcomes must now be treated as test evidence, not as another source for modifying the same claimed holdout.
