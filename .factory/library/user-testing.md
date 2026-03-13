# User Testing

Testing surface, validation tools, and resource cost classification.

**What belongs here:** How to test user-facing behavior, what tools to use, resource constraints.

---

## Validation Surface

- **CLI commands** (non-interactive): `vox --version`, `vox config show`, `vox config path`, `vox agent --list`
- **CLI with Ollama** (requires running Ollama): `vox "list files"` (NL-to-shell translation)
- **REPL** (interactive): Cannot be tested non-interactively. Validate via unit tests only.
- **Agent delegation**: Requires agent binaries in PATH. Can test `vox agent --list` non-interactively.

## Validation Tools

- Primary: shell commands via Execute tool
- Tests: `uv run pytest tests/ -v`
- Lint: `uv run ruff check src/`
- REPL testing: unit tests with mocked input only (no tuistory needed for this scope)

## Validation Concurrency

- Machine: 24GB RAM, 12 CPU cores
- Test suite: 27 tests in 0.04s (extremely lightweight)
- CLI validation: no heavy services to start (Ollama already running)
- Max concurrent validators: **5** (each pytest/CLI invocation is trivial, ~50MB overhead)

## Flow Validator Guidance: CLI

All CLI assertions are validated through **unit tests** (not live CLI invocations). The test suite is in `tests/test_cli.py`.

**How to validate:**
1. Run `uv run pytest tests/test_cli.py -v --tb=short` to verify CLI tests pass
2. For each assertion, map to specific test function(s) and verify they pass
3. Run `uv run ruff check src/` to verify lint is clean
4. Check `git diff tests/test_engine.py tests/test_config.py tests/test_agents.py tests/test_voice.py` to verify existing tests not modified

**Isolation:** No shared state. Each test uses mocks. Multiple validators can run concurrently.

**Assertion-to-test mapping:**
- VAL-CLI-001 → test_no_args_launches_repl
- VAL-CLI-002 → test_positional_query_dispatches_single_shot
- VAL-CLI-003 → test_version_flag
- VAL-CLI-004 → test_listen_subcommand_dispatches
- VAL-CLI-005 → test_speak_subcommand_dispatches
- VAL-CLI-006 → test_agent_subcommand_dispatches
- VAL-CLI-007 → test_config_subcommand_dispatches
- VAL-CLI-008 → test_model_flag_overrides_config
- VAL-CLI-009 → test_api_flag_overrides_config
- VAL-CLI-010 → test_execute_flag_enables_auto_execute
- VAL-CLI-011 → TestIsDangerous::test_* (multiple)
- VAL-CLI-012 → TestLooksLikeShell::test_* (multiple)
- VAL-CLI-013 → test_config_init_creates_template
- VAL-CLI-014 → test_config_show_displays_toml, test_config_show_hint_when_missing
- VAL-CLI-015 → test_config_path_prints_path
- VAL-CLI-016 → test_agent_list_shows_agents, test_agent_list_no_agents
- VAL-CLI-017 → test_agent_no_task_prints_hint
- VAL-CLI-018 → test_agent_use_flag_sets_env
- VAL-CLI-019 → test_config_edit_launches_editor, test_config_edit_creates_config_if_missing, test_config_edit_defaults_to_nano

## Flow Validator Guidance: Router

All Router assertions (VAL-RTR-*) are validated through **unit tests** in `tests/test_router.py`.

**How to validate:**
1. Run `uv run pytest tests/test_router.py -v --tb=short` to verify router tests pass
2. For each assertion, map to specific test function(s) and verify they pass

**Isolation:** No shared state. All tests use mocks. Multiple validators can run concurrently.

**Assertion-to-test mapping:**
- VAL-RTR-001 → TestHeuristicCodingKeywords::test_refactor_routes_to_coding_agent, test_code_routes_to_coding_agent, test_fix_routes_to_coding_agent, test_debug_routes_to_coding_agent, test_implement_routes_to_coding_agent
- VAL-RTR-002 → TestHeuristicResearchKeywords::test_research_routes_to_gemini, test_search_routes_to_gemini, test_summarize_routes_to_gemini
- VAL-RTR-003 → TestCaseInsensitiveMatching::test_uppercase_refactor_matches, test_mixed_case_research_matches, test_uppercase_fix_matches
- VAL-RTR-004 → TestLLMFallback::test_no_keyword_triggers_llm_fallback
- VAL-RTR-005 → TestLLMFallback::test_llm_valid_response_selects_agent
- VAL-RTR-006 → TestLLMFallback::test_llm_garbage_falls_back_to_preferred, test_llm_none_falls_back_to_preferred
- VAL-RTR-007 → TestNoAgents::test_no_agents_returns_message
- VAL-RTR-008 → TestSingleAgent::test_single_agent_used_directly
- VAL-RTR-009 → TestForceAgent::test_force_agent_overrides_heuristic, test_force_agent_via_env_var
- VAL-RTR-010 → TestAutoRouteDisabled::test_auto_route_false_uses_preferred
- VAL-RTR-011 → TestHeuristicPriorityOverLLM::test_heuristic_match_skips_llm_with_multiple_agents
- VAL-RTR-012 → TestAgentDiscovery::test_discovers_selective_agents, test_discovers_all_agents
- VAL-RTR-013 → TestOutputFormatting::test_success_shows_agent_and_output, test_failure_shows_error, test_empty_output_shows_completed
- VAL-RTR-014 → TestWordBoundaryMatching::test_fix_does_not_match_prefix, test_fix_does_not_match_suffix, test_code_does_not_match_barcode, test_search_does_not_match_researcher
- VAL-RTR-015 → TestConflictingKeywords::test_coding_priority_over_research, test_implement_beats_summarize
- VAL-RTR-016 → TestForceAgentUnavailable::test_force_agent_unavailable_falls_through

## Flow Validator Guidance: Wrappers

All Wrapper assertions (VAL-WRAP-*) are validated through **unit tests** in `tests/test_wrappers.py`.

**How to validate:**
1. Run `uv run pytest tests/test_wrappers.py -v --tb=short` to verify wrapper tests pass
2. For each assertion, map to specific test function(s) and verify they pass

**Isolation:** No shared state. All tests use mocks. Multiple validators can run concurrently.

**Assertion-to-test mapping:**
- VAL-WRAP-001 → TestAgentResultDataclass::test_stores_all_explicit_fields, test_exit_code_defaults_to_zero, test_error_defaults_to_none, test_defaults_together
- VAL-WRAP-002 → TestExecTimeoutHandling::test_timeout_returns_exit_code_124, test_timeout_returns_timed_out_error, test_timeout_returns_empty_output
- VAL-WRAP-003 → TestExecFileNotFoundHandling::test_file_not_found_returns_exit_code_127, test_file_not_found_error_contains_binary_name, test_file_not_found_returns_empty_output
- VAL-WRAP-004 → TestClaudeCommandConstruction, TestCodexCommandConstruction, TestGeminiCommandConstruction, TestAmpCommandConstruction, TestDroidCommandConstruction
- VAL-WRAP-005 → TestAllAgentsAttributes::test_all_agents_have_non_empty_name, test_all_agents_have_non_empty_binary, test_all_agents_have_non_empty_description
- VAL-WRAP-006 → TestExecNonZeroExitWithStderr::test_nonzero_exit_captures_returncode, test_nonzero_exit_captures_stderr, test_nonzero_exit_captures_stdout

## Flow Validator Guidance: Cross-Area

Cross-area assertions (VAL-CROSS-*) are validated through a mix of tests, lint, and git checks.

**How to validate:**
- VAL-CROSS-001 → TestCLIAgentIntegrationFlow in `tests/test_wrappers.py` (test_refactor_task_flows_through_heuristic_to_wrapper, test_research_task_flows_through_heuristic_to_gemini)
- VAL-CROSS-003 → Run `uv run pytest tests/ -v` — all tests must pass with 0 failures
- VAL-CROSS-004 → Run `uv run ruff check src/` — must report no errors
- VAL-CROSS-005 → Run `git diff tests/test_engine.py tests/test_config.py tests/test_agents.py tests/test_voice.py` — must be empty (no modifications)

**Isolation:** No shared state. Can run concurrently with other validators.

## Flow Validator Guidance: Provider

All Provider assertions are validated through **unit tests** in `tests/test_provider.py`, plus backward-compatibility checks through `tests/test_engine.py` and `tests/test_config.py`.

**How to validate:**
1. Run `uv run pytest tests/test_provider.py -v --tb=short` to verify provider tests pass
2. Run `uv run pytest tests/test_engine.py -v --tb=short` to verify existing engine tests still pass
3. Run `uv run pytest tests/test_config.py -v --tb=short` to verify existing config tests still pass
4. For each assertion, map to specific test function(s) and verify they pass

**Isolation:** No shared state. All tests use mocks. Multiple validators can run concurrently.

**Assertion-to-test mapping:**
- VAL-PROV-001 → test_base_provider_is_abstract, test_base_provider_has_abstract_methods
- VAL-PROV-002 → test_ollama_provider_is_subclass_of_base, test_ollama_provider_instantiates
- VAL-PROV-003 → test_translate_sends_correct_request
- VAL-PROV-004 → test_translate_applies_clean_response
- VAL-PROV-005 → test_translate_connect_error_returns_none, test_translate_404_returns_none, test_translate_keyboard_interrupt_returns_none, test_translate_generic_error_returns_none
- VAL-PROV-006 → test_query_returns_content, test_query_with_system_message, test_query_error_returns_none
- VAL-PROV-007 → test_check_ready, test_check_no_model, test_check_no_ollama
- VAL-PROV-008 → test_get_provider_returns_ollama, test_get_provider_unknown_raises
- VAL-PROV-009 → test_module_level_functions_importable
- VAL-PROV-010 → (run tests/test_engine.py — all 9 pass without modification)
- VAL-PROV-011 → (run tests/test_config.py — all 5 pass without modification)
- VAL-CROSS-002 → test_config_provider_setting_affects_factory
