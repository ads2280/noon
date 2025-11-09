# Testing the Noon Agent

This document outlines the current automated tests for the calendar agent plus
guidance on how to run and extend them.

## Test Suite Overview

- **Unit tests (`tests/unit_tests/`)**  
  Fast tests that exercise individual modules in isolation. Examples include:
  - `test_intent_parser.py` – validates the LLM intent parser’s schema handling.
  - `test_graph.py` – smoke tests core LangGraph wiring.
  - `test_calendar_service.py` – validates the new calendar service abstraction (see below).

- **Integration tests (`tests/integration_tests/`)**  
  Slower, end-to-end style tests that step through larger pieces of the agent
  (e.g., graph execution with mocked LangChain components). These typically
  require more involved fixtures and may rely on recorded responses.

- **Manual scripts**  
  `test_calendar_operations.py` offers a manual smoke test for Google Calendar
  CRUD operations against a live calendar when valid OAuth tokens are present.

## Calendar Service Tests

`tests/unit_tests/test_calendar_service.py` focuses on the `CalendarService`
contract. It uses pytest plus monkeypatching to stub Google client factories and
wrapper functions. Coverage includes:

- Ensuring context defaults (primary calendar, timezone) are applied.
- Validating required arguments for create/update/delete/search/schedule flows.
- Verifying auth tokens are passed to the underlying service factory.

Add new test cases here when introducing additional behaviors or validation in
`noon_agent/calendar_service.py`.

## Running Tests

```bash
cd noon-agent
pytest                      # run entire suite
pytest tests/unit_tests     # run just the unit tests
pytest tests/unit_tests/test_calendar_service.py
```

Set `PYTEST_ADDOPTS=-q` for quieter output, or `-k <pattern>` to filter cases.

## Extending the Suite

1. Prefer unit tests for pure logic modules; rely on integration tests only when
   orchestrating multiple components.
2. Mock external APIs (Google Calendar, LangChain, Supabase, etc.) so tests stay
   deterministic and do not require network access.
3. When adding new graph nodes or service methods, create a companion test that
   asserts both happy-path behavior and error handling.

Refer to `pyproject.toml`’s `tool.pytest.ini_options` section for base pytest
configuration (Python path, test directories).*** End Patch
