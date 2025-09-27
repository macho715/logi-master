"""Test cases for dash_web.py refactoring - UI improvements"""

import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import streamlit as st
import tempfile
import os

# Mock streamlit before importing our modules
sys.modules["streamlit"] = Mock()

from dash_web_components import (
    PipelineConfig,
    PipelineRunner,
    StatusDisplay,
    LogDisplay,
    SidebarControls,
)


class TestPipelineConfig:
    """Test PipelineConfig class"""

    def test_should_initialize_with_default_values(self):
        """PipelineConfig should initialize with default values"""
        config = PipelineConfig()
        assert config.base_path is not None
        assert config.cache_path is not None
        assert config.reports_path is not None
        assert config.target_path is not None

    def test_should_load_config_from_file(self):
        """PipelineConfig should load configuration from file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
target_path: "C:/TEST_TARGET"
cache_path: "C:/TEST_CACHE"
reports_path: "C:/TEST_REPORTS"
"""
            )
            config_path = f.name

        try:
            config = PipelineConfig(config_file=config_path)
            assert config.target_path == "C:/TEST_TARGET"
            assert str(config.cache_path).replace("\\", "/") == "C:/TEST_CACHE"
            assert str(config.reports_path).replace("\\", "/") == "C:/TEST_REPORTS"
        finally:
            os.unlink(config_path)

    def test_should_validate_paths_exist(self):
        """PipelineConfig should validate that paths exist"""
        config = PipelineConfig()
        assert config.base_path.exists()
        assert config.cache_path.exists()
        assert config.reports_path.exists()


class TestPipelineRunner:
    """Test PipelineRunner class"""

    def test_should_initialize_with_config(self):
        """PipelineRunner should initialize with config"""
        config = PipelineConfig()
        runner = PipelineRunner(config)
        assert runner.config == config
        assert runner.is_running is False

    def test_should_run_local_pipeline(self):
        """PipelineRunner should run local pipeline successfully"""
        config = PipelineConfig()
        runner = PipelineRunner(config)

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = runner.run_pipeline("local")
            assert result is True
            assert runner.is_running is False

    def test_should_handle_pipeline_failure(self):
        """PipelineRunner should handle pipeline failure gracefully"""
        config = PipelineConfig()
        runner = PipelineRunner(config)

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            result = runner.run_pipeline("local")
            assert result is False
            assert runner.is_running is False

    def test_should_validate_mode_before_running(self):
        """PipelineRunner should validate mode before running"""
        config = PipelineConfig()
        runner = PipelineRunner(config)

        with pytest.raises(ValueError, match="Invalid mode"):
            runner.run_pipeline("invalid_mode")


class TestStatusDisplay:
    """Test StatusDisplay class"""

    def test_should_initialize_with_default_status(self):
        """StatusDisplay should initialize with default status"""
        display = StatusDisplay()
        assert display.current_status == "Idle"
        assert display.progress == 0

    def test_should_update_status(self):
        """StatusDisplay should update status correctly"""
        display = StatusDisplay()
        display.update_status("Running", 50)
        assert display.current_status == "Running"
        assert display.progress == 50

    def test_should_reset_to_idle(self):
        """StatusDisplay should reset to idle state"""
        display = StatusDisplay()
        display.update_status("Running", 50)
        display.reset()
        assert display.current_status == "Idle"
        assert display.progress == 0


class TestLogDisplay:
    """Test LogDisplay class"""

    def test_should_initialize_empty_log(self):
        """LogDisplay should initialize with empty log"""
        display = LogDisplay()
        assert len(display.lines) == 0
        assert display.max_lines == 800

    def test_should_add_log_line(self):
        """LogDisplay should add log line correctly"""
        display = LogDisplay()
        display.add_line("test line")
        assert len(display.lines) == 1
        assert display.lines[0] == "test line"

    def test_should_limit_max_lines(self):
        """LogDisplay should limit maximum lines"""
        display = LogDisplay(max_lines=3)
        for i in range(5):
            display.add_line(f"line {i}")
        assert len(display.lines) == 3
        assert display.lines[0] == "line 2"  # First lines should be removed

    def test_should_clear_log(self):
        """LogDisplay should clear log correctly"""
        display = LogDisplay()
        display.add_line("test line")
        display.clear()
        assert len(display.lines) == 0


class TestSidebarControls:
    """Test SidebarControls class"""

    def test_should_initialize_with_default_values(self):
        """SidebarControls should initialize with default values"""
        controls = SidebarControls()
        assert controls.mode == "LOCAL"
        assert controls.run_button_clicked is False
        assert controls.clear_button_clicked is False

    def test_should_validate_gpt_mode_without_api_key(self):
        """SidebarControls should validate GPT mode without API key"""
        controls = SidebarControls()
        controls.mode = "GPT"

        with patch.dict(os.environ, {}, clear=True):
            assert controls.validate_mode() is False

    def test_should_validate_gpt_mode_with_api_key(self):
        """SidebarControls should validate GPT mode with API key"""
        controls = SidebarControls()
        controls.mode = "GPT"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            assert controls.validate_mode() is True

    def test_should_reset_buttons_after_action(self):
        """SidebarControls should reset buttons after action"""
        controls = SidebarControls()
        controls.run_button_clicked = True
        controls.clear_button_clicked = True
        controls.reset_buttons()
        assert controls.run_button_clicked is False
        assert controls.clear_button_clicked is False


class TestIntegration:
    """Integration tests for refactored dash_web"""

    def test_should_create_all_components_together(self):
        """Should create all components together without errors"""
        config = PipelineConfig()
        runner = PipelineRunner(config)
        status_display = StatusDisplay()
        log_display = LogDisplay()
        controls = SidebarControls()

        assert runner.config == config
        assert status_display.current_status == "Idle"
        assert len(log_display.lines) == 0
        assert controls.mode == "LOCAL"

    def test_should_handle_component_interaction(self):
        """Should handle component interaction correctly"""
        config = PipelineConfig()
        runner = PipelineRunner(config)
        status_display = StatusDisplay()
        log_display = LogDisplay()

        # Simulate pipeline start
        status_display.update_status("Running", 0)
        log_display.add_line("Pipeline started")

        assert status_display.current_status == "Running"
        assert len(log_display.lines) == 1
