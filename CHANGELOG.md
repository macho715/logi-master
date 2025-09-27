# Changelog

## [Unreleased]
### Added
- Logistics validation toolkit with Incoterm/HS Code/AED checks and CLI support.
- psutil fallback shim via `sitecustomize.py` for deterministic memory tests.
- Documentation in Korean and English covering logistics validation flows.
- **PROJECT_VALIDATION_REPORT.md**: Comprehensive project file validation report
- **Enhanced Hybrid GPT Mode**: Retry logic with 3 attempts and 2-second delays
- **API Key Status Display**: Real-time API key validation in dashboard
- **YAML Escape Fix**: Resolved ScannerError for regex patterns in rules.yml

### Changed
- Updated README with logistics validation command reference.
- Refined clustering to derive project folder names from shared directories, guaranteeing project-isolated organization outputs.
- **Streamlit Compatibility**: Updated width="stretch" to use_container_width=True
- **Function Updates**: Replaced st.experimental_rerun() with st.rerun()
- **GPT Mode Default**: Set Hybrid GPT mode as default with value=True

### Fixed
- **IndentationError**: Fixed for loop try block indentation in devmind.py
- **YAML Parsing**: Resolved unknown escape character errors in rules.yml
- **Streamlit Warnings**: Eliminated runtime warnings and compatibility issues
- **File Classification**: Confirmed individual file classification is working correctly
