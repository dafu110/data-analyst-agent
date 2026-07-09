# Changelog

## [0.2.0] - 2026-07-09

### Added

- Added `docs/API.md` with FastAPI endpoint, auth, export, and error contracts.
- Added launch hardening guidance and an ADR for sandboxed analysis execution.
- Added FastAPI smoke coverage for Markdown, HTML, CSV, PDF, and PPTX report exports.

### Changed

- Improved CSV ingestion for UTF-8 BOM, UTF-8, GB18030, and common delimiter variants.
- Improved Excel multi-sheet selection by preferring informative sheets over empty rows.
- Updated Chinese QuickStart and production verification docs for GitHub presentation.
- Expanded `.dockerignore` to keep generated runtime files and local secrets out of images.

### Fixed

- Hardened SQL execution to reject comments, multi-statement queries, and write/admin operations.
- Constrained FastAPI report exports to files under the configured report directory.
- Counted each constant column when calculating the data quality variability score.

### Verification

- `python -m unittest discover -s tests`: 74 tests passed.
- `python -m evals.run_evals`: 6/6 eval cases passed.
- `python -m backend.production_check`: local dependency and configuration checks passed.
- Docker, PostgreSQL, and Redis/RQ external smoke checks still require a real production-like environment.
