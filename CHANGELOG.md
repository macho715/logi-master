# Changelog

## [Unreleased]
### Added
- Logistics validation toolkit with Incoterm/HS Code/AED checks and CLI support.
- psutil fallback shim via `sitecustomize.py` for deterministic memory tests.
- Documentation in Korean and English covering logistics validation flows.
- Modular autosort components (`scan.py`, `classify.py`, `organize.py`, `report.py`, `utils.py`) with typed interfaces.
- Refactored Streamlit dashboard with progress tracking, KPI cards, charts, search UI, and journal viewer.
- Pilot package created
  - Added `inbox_reader.py` Outlook collector with queue persistence.
  - Added `report_builder.py` OCR pipeline with sample attachments and Excel export.
  - Added automation scripts, Kutools rulebook, and IT readiness documentation.

### Changed
- Updated README with logistics validation command reference.
- Introduced `autosort.py` CLI entrypoint and delegated `devmind.py` to the new pipeline orchestrator.
- Hardened rule loading to support escaped regex patterns and ignore pytest temp directories during classification.
