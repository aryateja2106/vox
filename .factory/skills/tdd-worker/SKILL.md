---
name: tdd-worker
description: Strict TDD worker for Python CLI features — tests first, then implementation
---

# TDD Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features that require writing new test files or extending existing source files following strict TDD (Red-Green-Refactor). Typical features: adding test coverage for existing code, refactoring with new abstractions, adding new functionality with tests.

## Work Procedure

### Step 1: Read Feature Context

1. Read the feature description, preconditions, expectedBehavior, and verificationSteps from the assigned feature.
2. Read `AGENTS.md` for mission boundaries and conventions.
3. Read all source files mentioned in the feature description to understand current behavior.
4. Read `.factory/library/architecture.md` and `.factory/library/environment.md` for context.

### Step 2: Write Failing Tests (RED)

1. Create the test file specified in the feature description.
2. Write ALL test functions covering the feature's expectedBehavior. Each test should:
   - Have a descriptive name (`test_<specific_behavior>`)
   - Test ONE behavior
   - Use `unittest.mock.patch` for external dependencies (httpx, subprocess, shutil.which, os, sys)
   - Be a pure unit test (no network, no filesystem side effects, no real subprocess calls)
3. Run the tests: `uv run pytest tests/<test_file> -v`
4. Verify they FAIL (Red phase). If they pass without implementation, the tests are testing the wrong thing — fix the tests.
5. Record the failing test output.

### Step 3: Implement to Pass (GREEN)

1. Make the MINIMUM changes to source code to make all tests pass.
2. Follow existing patterns in the codebase (dataclasses, classmethods, import style).
3. Run the new tests: `uv run pytest tests/<test_file> -v`
4. Run ALL tests: `uv run pytest tests/ -v`
5. ALL tests must pass (new AND existing).

### Step 4: Refactor

1. Review the implementation for code quality.
2. Refactor if needed (extract functions, improve naming, remove duplication).
3. Run ALL tests again after refactoring: `uv run pytest tests/ -v`
4. Run ruff: `uv run ruff check src/`
5. Fix any ruff issues.

### Step 5: Verify

1. Run the full test suite: `uv run pytest tests/ -v`
2. Run the linter: `uv run ruff check src/`
3. Both must pass with 0 failures/errors.
4. Check that existing test files were NOT modified (unless the feature explicitly requires it): `git diff tests/test_engine.py tests/test_config.py tests/test_agents.py tests/test_voice.py`
5. If the feature involves CLI-observable behavior, verify with a quick CLI command (e.g., `uv run vox --version`).

### Step 6: Commit

1. Stage all changes: `git add -A`
2. Review staged changes: `git diff --cached`
3. Commit with a descriptive message following the existing convention: `feat(scope): description`

## Example Handoff

```json
{
  "salientSummary": "Created tests/test_cli.py with 22 test functions covering subcommand dispatch, flag overrides, safety detection, and config actions. All 22 tests initially failed (Red), then implemented minimal changes to cli.py to pass (Green). Ran full suite: 49 tests passing, ruff clean.",
  "whatWasImplemented": "tests/test_cli.py with 22 tests covering: subcommand dispatch (8 tests), flag overrides (3 tests), is_dangerous/looks_like_shell (6 tests), config actions (5 tests). Minor refactoring of cli.py main() to improve testability by extracting dispatch logic.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      { "command": "uv run pytest tests/test_cli.py -v", "exitCode": 0, "observation": "22 passed in 0.05s" },
      { "command": "uv run pytest tests/ -v", "exitCode": 0, "observation": "49 passed in 0.08s — all existing tests still pass" },
      { "command": "uv run ruff check src/", "exitCode": 0, "observation": "All checks passed!" },
      { "command": "git diff tests/test_engine.py tests/test_config.py tests/test_agents.py tests/test_voice.py", "exitCode": 0, "observation": "No changes to existing test files" },
      { "command": "uv run vox --version", "exitCode": 0, "observation": "vox 0.3.0" }
    ],
    "interactiveChecks": []
  },
  "tests": {
    "added": [
      {
        "file": "tests/test_cli.py",
        "cases": [
          { "name": "test_no_args_launches_repl", "verifies": "REPL starts when no arguments given" },
          { "name": "test_positional_query_dispatches_single_shot", "verifies": "Query string passed to handle_command" },
          { "name": "test_version_flag", "verifies": "--version prints version and exits" }
        ]
      }
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Feature depends on code that doesn't exist yet (e.g., missing module, undefined function)
- Existing tests break and can't be fixed without modifying them (boundary violation)
- Requirements are ambiguous (e.g., unclear what the expected behavior should be for an edge case)
- A pre-existing bug prevents the feature from being implemented correctly
- Cannot make ruff pass without changing code outside the feature's scope
