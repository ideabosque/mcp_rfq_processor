# Repository Guidelines

## Project Structure & Module Organization
- Core package lives in `mcp_rfq_processor/`; each `*_processor.py` module wraps a specific RFQ domain (request, quote, pricing, installments, files, segments) and is orchestrated by `mcp_rfq_processor.py` via `MCPRfqProcessor`.
- GraphQL client and helpers sit in `graphql_backed_processor.py` and `graphql_client.py`, with status logic in `status_manager.py`.
- Tests and fixtures are under `mcp_rfq_processor/tests/` (`test_mcp_rfq_processor.py`, `test_data.json`). API and workflow docs are in `API_REFERENCE.md` and `DEVELOPMENT_PLAN.md`.

## Build, Test, and Development Commands
- Install in editable mode: `pip install -e .[dev]` (run from repo root; pulls pytest/black). For runtime-only: `pip install -e .`.
- Launch server locally: `python -m mcp_rfq_processor` after setting required env vars (see README configuration).
- Run tests: `pytest -q` or `pytest -q --cov=mcp_rfq_processor --cov-report=term-missing` for coverage.
- Format: `black .` (88-char width, Python 3.8 target).

## Coding Style & Naming Conventions
- Python 3.8+, Black-formatted (88 chars). Prefer type hints on public methods; match existing patterns in processors.
- Use snake_case for functions/variables, PascalCase for classes, and UPPER_SNAKE for constants/status values.
- Keep GraphQL operation names and note strings consistent with `DEVELOPMENT_PLAN.md` status rules.
- Log through the provided logger; avoid bare prints.

## Testing Guidelines
- Add/extend tests in `mcp_rfq_processor/tests/test_mcp_rfq_processor.py`; reuse/extend `test_data.json` fixtures.
- Name tests `test_*` and structure with clear Arrange/Act/Assert blocks.
- Validate status transitions, auto-complete/disapprove flows, and error paths; prefer explicit assertions on returned status and notes.
- Run `pytest -q` before pushing; include coverage run when altering workflow logic.

## Commit & Pull Request Guidelines
- Follow conventional-style prefixes observed in history (`feat:`, `fix:`, `chore:`). Keep summaries imperative and under ~72 chars.
- Each PR should describe behavior changes, affected tools, and checklist of tests run; link related issues/tickets.
- Include repro steps or sample payloads for behavior changes (e.g., request/quote IDs used) and note config/ENV variable impacts.
- Screenshots are unnecessary; prefer concise notes or log excerpts for failures.

## Security & Configuration Tips
- Never hardcode AWS credentials; rely on environment variables outlined in README (`AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ENDPOINT_ID`).
- When adding new GraphQL operations, ensure request signing/region handling matches `graphql_client.py`; guard sensitive logging (no secrets in logs).
- Default to `execute_mode="aws_lambda"` for production-like runs; `execute_mode="local"` is only for controlled testing.
