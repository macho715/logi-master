"""S3 단계: report가 HTML 생성하는 테스트"""

import json
from pathlib import Path

import pytest

from organize import OrganizeConfig, organize_files
from report import generate_html_report
from scan import FileRecord, scan_paths


class TestReportHtmlGeneration:
    """HTML 리포트 생성 테스트"""

    def test_should_generate_html_report_from_journal(self, tmp_workspace: Path):
        """저널에서 HTML 리포트가 생성되는지 테스트"""
        # Given: 파일 이동이 완료된 상태
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"

        # 테스트 파일 생성
        (hvdc_path / "test_file.txt").write_text("test content", encoding="utf-8")
        (cursor_path / "sample.py").write_text("print('hello')", encoding="utf-8")

        # 스캔 및 organize 실행
        records, safe_map = scan_paths([hvdc_path, cursor_path])
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/"),
        )

        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)

        # When: HTML 리포트 생성
        output_path = tmp_workspace / "report.html"
        generate_html_report(journal_path, output_path)

        # Then: HTML 파일이 생성되어야 함
        assert output_path.exists(), "HTML report should be generated"

        # HTML 내용 확인
        html_content = output_path.read_text(encoding="utf-8")
        assert "<html" in html_content.lower(), "Should contain HTML structure"
        assert "<head>" in html_content.lower(), "Should contain head section"
        assert "<body>" in html_content.lower(), "Should contain body section"
        assert "test_file" in html_content, "Should contain moved file information"

    def test_should_include_journal_statistics_in_html(self, tmp_workspace: Path):
        """HTML 리포트에 저널 통계가 포함되는지 테스트"""
        # Given: 여러 파일이 이동된 상태
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"

        # 여러 파일 생성
        (hvdc_path / "file1.txt").write_text("content 1", encoding="utf-8")
        (hvdc_path / "file2.py").write_text("content 2", encoding="utf-8")
        (cursor_path / "file3.md").write_text("content 3", encoding="utf-8")

        # 스캔 및 organize 실행
        records, safe_map = scan_paths([hvdc_path, cursor_path])
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/"),
        )

        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)

        # When: HTML 리포트 생성
        output_path = tmp_workspace / "report.html"
        generate_html_report(journal_path, output_path)

        # Then: 통계 정보가 포함되어야 함
        html_content = output_path.read_text(encoding="utf-8")

        # 기본 통계 키워드 확인
        assert (
            "total" in html_content.lower()
            or "count" in html_content.lower()
            or "총" in html_content
        ), "Should contain statistics"
        assert (
            "move" in html_content.lower() or "copy" in html_content.lower()
        ), "Should contain operation types"
        assert "file" in html_content.lower(), "Should contain file information"

    def test_should_handle_empty_journal_gracefully(self, tmp_workspace: Path):
        """빈 저널 파일에 대해 HTML 리포트가 안전하게 생성되는지 테스트"""
        # Given: 빈 저널 파일
        journal_path = tmp_workspace / "empty_journal.jsonl"
        journal_path.write_text("", encoding="utf-8")

        # When: HTML 리포트 생성
        output_path = tmp_workspace / "report.html"

        # Then: 예외가 발생하지 않아야 함
        try:
            generate_html_report(journal_path, output_path)
            assert output_path.exists(), "HTML report should be generated even for empty journal"
        except Exception as e:
            pytest.fail(f"HTML generation should handle empty journal gracefully, but raised: {e}")

    def test_should_handle_missing_journal_file_gracefully(self, tmp_workspace: Path):
        """존재하지 않는 저널 파일에 대해 HTML 리포트가 안전하게 생성되는지 테스트"""
        # Given: 존재하지 않는 저널 파일
        journal_path = tmp_workspace / "nonexistent_journal.jsonl"

        # When: HTML 리포트 생성
        output_path = tmp_workspace / "report.html"

        # Then: 예외가 발생하지 않아야 함
        try:
            generate_html_report(journal_path, output_path)
            # 파일이 존재하지 않아도 기본 HTML은 생성되어야 함
        except Exception as e:
            pytest.fail(
                f"HTML generation should handle missing journal gracefully, but raised: {e}"
            )

    def test_should_generate_valid_html_structure(self, tmp_workspace: Path):
        """생성된 HTML이 유효한 구조를 가지는지 테스트"""
        # Given: 파일 이동이 완료된 상태
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"

        # 테스트 파일 생성
        (hvdc_path / "test.html").write_text("test", encoding="utf-8")

        # 스캔 및 organize 실행
        records, safe_map = scan_paths([hvdc_path, cursor_path])
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/"),
        )

        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)

        # When: HTML 리포트 생성
        output_path = tmp_workspace / "report.html"
        generate_html_report(journal_path, output_path)

        # Then: 유효한 HTML 구조여야 함
        html_content = output_path.read_text(encoding="utf-8")

        # 기본 HTML 태그 확인
        assert html_content.strip().startswith("<"), "Should start with HTML tag"
        assert "</html>" in html_content.lower(), "Should have closing html tag"
        assert (
            "<!doctype" in html_content.lower() or "<html" in html_content.lower()
        ), "Should have proper HTML declaration"
