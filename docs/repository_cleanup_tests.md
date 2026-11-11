# Cleanup test ledger

Baseline: 319 passing offline tests. Removed tests are enumerated below; active onboarding, corporate identity, evidence, legal drafting, Google graph safety and Tavily coverage remain. Financial-only behavior is intentionally retired.

## tests/test_404_and_research.py

Financial endpoint/error classifier retired; exact-identity Tavily query tests retained.

- `test_specific_envelopes`
- `test_generic_unfamiliar_and_conflicting_signals_remain_unknown`
- `test_matching_code_and_message`
- `test_rest_sdk_parity_and_safe_logs`
- `test_sdk_existing_response_body_is_used_without_rest_request`
- `test_availability_dimensions_survive_analysis_and_rendering`

## tests/test_api_usage.py

Retired financial cache integration; generic budget/cache/duplicate behavior remains covered using company details.

- `test_financial_cache_preserved_without_approval_or_credits`
- `test_financial_budget_check_precedes_adapter`
- `test_financial_fresh_result_still_uses_existing_cache`

## tests/test_evidence_validator.py

Retired command-line/LLM report orchestration; deterministic evidence validators remain tested.

- `test_mocked_registry_pipeline`
- `test_mocked_german_response_retained`
- `test_validation_precedes_mocked_analysis`

## tests/test_financial_cache_regression.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_actual_shape_extracts_figures_without_inventing_units`
- `test_explicit_indicator_units_are_preserved_and_calculable`
- `test_conflicting_units_block_calculations`
- `test_prior_indicator_date_conflict_stays_invalid`
- `test_no_scope_mixing_and_no_nonconsecutive_yoy`
- `test_no_signed_urls_in_rendered_financial_section`
- `test_report_reanalysis_only_no_approval_or_pricing_dependency`

## tests/test_financial_errors.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_rest_status_categories_and_terminal_diagnostic`
- `test_route_404_only_identified_from_machine_code`
- `test_sdk_http_errors_have_same_categories_without_rest_fallback`
- `test_network_errors_not_data_absence`
- `test_json_and_schema_failures_are_not_no_data`
- `test_success_empty_is_not_request_failure_or_absence_proof`
- `test_success_figures_and_original_shape`
- `test_sdk_setup_and_parsing_errors_do_not_make_second_call`
- `test_missing_key_and_default_guard_make_no_requests`

## tests/test_financials.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_ratios_decimal_and_zero`
- `test_missing_units_no_inference`
- `test_incompatible_currency_and_negative_denominators`
- `test_trends_and_unit_normalization`
- `test_unequal_scope_short_year_and_periods`
- `test_nonfinite_values_and_missing_data`
- `test_openregister_documented_shape_excludes_estimates`
- `test_conflicting_and_future_periods`
- `test_financial_identity_binding`
- `test_not_requested_is_not_identity_exclusion`
- `test_invalid_start_date_and_duplicate_periods`
- `test_issues_and_report_sections`
- `test_financial_analysis_in_model_payload_without_bytes`
- `test_xbrl_exact_company_period_unit`
- `test_conflicting_duplicate_facts_and_unsupported_input`
- `test_ixbrl_scale_and_sign`
- `test_no_automatic_paid_calls`
- `test_openregister_rest_no_sdk`
- `test_sdk_supported_and_no_fallback_on_failure`
- `test_older_sdk_missing_method_uses_rest`
- `test_rest_errors_not_retried`
- `test_accounts_specific_bounded_query`
- `test_one_document_and_pdf_limitation`
- `test_mocked_machine_readable_accounts_end_to_end`
- `test_metadata_only_never_downloads`
- `test_large_file_not_downloaded`
- `test_untrusted_document_host_rejected`
- `test_bounded_stream_and_storage_redirect_no_credentials`

## tests/test_german_accounts.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_checked_actual_figures_and_mixed_units`
- `test_decimal_formats_and_absence`
- `test_missing_revenue_not_zero_and_units_not_inferred`
- `test_zero_negative_and_incompatible_periods`
- `test_required_provenance_and_review`
- `test_pdf_hash_and_ambiguous_matches_fail_closed`
- `test_actual_unrestricted_pdf_round_trip`
- `test_no_signed_urls_in_report`

## tests/test_incept_corporate_workflow.py

Retired isolated corporate fixture-export configuration; current corporate routing and pipeline scenarios remain tested.

- `test_isolated_copies_have_no_external_nodes_or_credentials`

## tests/test_incept_google_read_workflows.py

Superseded historical/isolated workflow generator; canonical 37-node graph and semantic safety validation are retained.

- `test_exports_are_inactive_get_only_and_credential_free`
- `test_compatible_metadata_only_binding`
- `test_counts_do_not_export_personal_content`
- `test_http_failure_never_yields_pass`
- `test_pagination_and_empty_calendar_are_honest`

## tests/test_incept_sheets_workflow.py

Superseded historical/isolated workflow generator; canonical 37-node graph and semantic safety validation are retained.

- `test_read_only_config_and_sanitized_export`
- `test_bind_only_existing_credential_metadata`
- `test_unique_document_is_from_api_metadata_not_guessed`
- `test_tabs_require_unique_grid_and_preserve_zero_id`
- `test_summary_does_not_export_row_values`

## tests/test_n8n_workflow.py

Superseded historical/isolated workflow generator; canonical 37-node graph and semantic safety validation are retained.

- `test_form_fields_credential_reference_and_inactive_state_preserved`
- `test_all_connections_and_required_branches_resolve`
- `test_active_workflow_cannot_be_rebuilt`
- `test_real_form_name_and_financial_opt_in_are_never_forwarded`
- `test_health_guard_rejects_live_and_network_failure`
- `test_selected_candidate_is_not_verified_by_name`
- `test_ambiguous_candidates_require_validated_form_selection`
- `test_missing_failed_and_non_synthetic_results_stop`
- `test_verified_response_requires_detail_checks_and_scope`
- `test_research_branch_preserves_phase1_and_unresolved_routes`
- `test_research_plan_guard_rejects_unapproved_tools_and_high_iterations`

## tests/test_report_renderer.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_readable_gaps_preserve_structured_identifiers`
- `test_traceable_uk_reference`
- `test_german_reference_does_not_invent_url`
- `test_missing_retrieval_is_not_analysis_date`
- `test_model_contradictions_never_published`
- `test_priority_selection_allowlist`
- `test_outdated_and_future_dates_are_readable`
- `test_failed_registry_check_is_not_called_verified`
- `test_source_text_cannot_inject_report_sections`
- `test_end_to_end_mocked_conflicting_model`

## tests/test_repository_exports.py

Replaced old 29-node export assertion with canonical 37-node export validation.

- `test_current_export_is_29_node_development_workflow`

## tests/test_volkswagen_continuation.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_fresh_approval_scope_and_expiry`
- `test_ineligible_without_search`
- `test_success_persists_separate_outcomes_and_replay`
- `test_concurrent_calls_only_one_detail`
- `test_cumulative_budget_blocks_at_approval_and_execution`
- `test_budget_blocks_fresh_approval`
- `test_cached_detail_requires_provenance_and_exact_identity`
- `test_missing_mismatched_and_conflicting_fields`
- `test_timeout_keeps_reservation_and_prevents_retry`
- `test_crash_keeps_reservation_and_blocks_restart`
- `test_hard_exit_keeps_pending_reservation`
- `test_untrusted_cache_does_not_skip_provider_verification`
- `test_conflicting_raw_register_fields_are_manual_review`
- `test_http_requires_enable_and_separate_approval`

## tests/test_volkswagen_financial_test.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_no_approval_or_wrong_approval`
- `test_verified_identity_required_read_only`
- `test_real_figures_ratios_comparisons_and_report`
- `test_cache_reuse_zero_credits`
- `test_untrusted_cache_not_reused`
- `test_missing_figures_and_units_never_invented`
- `test_malformed_payloads_fail_closed_and_do_not_retry`
- `test_expired_approval_and_pricing`
- `test_concurrency_and_budget_persist_across_restart`
- `test_crash_reservation_blocks_restart`
- `test_timeout_safe_no_retry`
- `test_fixed_transport_no_retries_redirects_or_proxy`

## tests/test_volkswagen_live_test.py

Retired financial extraction, financial cache/error/reporting or isolated paid financial/identity-test implementation; no retained caller.

- `test_unapproved_and_wrong_scope_no_requests`
- `test_two_calls_11_credits_and_provenance`
- `test_restart_replay_and_reapproval_do_not_duplicate`
- `test_concurrent_same_test_only_one_search_and_details`
- `test_hard_process_exit_keeps_pending_reservation`
- `test_timeout_reserved_and_never_retried_after_restart`
- `test_crash_between_reservation_and_request_blocks_restart`
- `test_direct_requests_and_other_operations_forbidden`
- `test_second_details_and_budget_over_15_are_blocked`
- `test_selected_id_cannot_be_overridden`
- `test_expired_approval_does_not_call_provider`
- `test_ambiguous_and_wrong_register_search_stop_without_details`
- `test_details_mismatch_fails_closed`
- `test_legacy_and_current_detail_schema`
- `test_full_identity_and_explicit_name_alias_required`
- `test_preview_is_cache_only_and_requires_no_approval`
- `test_attested_detail_cache_zero_requests`
- `test_unattested_synthetic_stale_and_wrong_identity_cache_not_promoted`
- `test_attested_search_cache_uses_only_one_detail_call`
- `test_pricing_missing_expired_inconsistent_and_future_fail_closed`
- `test_policy_change_does_not_reset_ledger`
- `test_http_opt_in_auth_and_closed_surface`
- `test_nonloopback_client_rejected`
- `test_transport_exact_routes_auth_no_redirects_or_retries`
- `test_transport_errors_do_not_expose_secrets_or_retry`

## tests/test_workflow_validation.py

Superseded historical/isolated workflow generator; canonical 37-node graph and semantic safety validation are retained.

- `test_phase1_success_is_not_phase2_success`
- `test_successful_review_branch_does_not_count_as_report_pass`
- `test_complete_evidence_is_accepted`
- `test_duplicate_or_missing_tool_execution_is_rejected`
- `test_tampered_source_and_missing_warnings_are_rejected`
- `test_report_for_wrong_company_is_rejected`

## Added or replacement tests

- `tests/test_cleanup_safeguards.py`: `test_retired_operations_block_before_cache_or_transport_even_with_approval`, `test_uk_document_and_accounts_routes_fail_before_transport`, `test_company_search_details_and_officers_still_work_offline`, `test_retired_financial_topics_and_routes_explicitly_rejected`, `test_counterparty_lookup_does_not_reclassify_or_mutate_client`, `test_shared_report_escaping_remains_active`
- `tests/test_repository_exports.py`: `test_only_export_is_canonical_37_node_workflow`

Function-name inventory: before 319; removed 154; added/replaced 7; after 172. Renamed replacements appear on both sides. Runtime unittest results are reported separately.
