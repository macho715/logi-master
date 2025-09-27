"""S3 단계: rollback이 이동 파일을 되돌리는 테스트"""

import json
from pathlib import Path

import pytest

from organize import OrganizeConfig, organize_files, rollback
from scan import FileRecord, scan_paths


class TestRollbackFunctionality:
    """롤백 기능 테스트"""

    def test_should_rollback_moved_files_to_original_locations(self, tmp_workspace: Path):
        """이동된 파일들이 원래 위치로 되돌려지는지 테스트"""
        # Given: 파일들이 이동된 상태
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"
        
        # 테스트 파일 생성
        (hvdc_path / "test_file.txt").write_text("test content A", encoding="utf-8")
        (cursor_path / "test_file.txt").write_text("test content B", encoding="utf-8")
        
        # 스캔 및 organize 실행
        records, safe_map = scan_paths([hvdc_path, cursor_path])
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/")
        )
        
        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)
        
        # 이동 확인
        target_files = list(target_path.rglob("test_file*"))
        assert len(target_files) >= 2, "Files should be moved to target"
        
        # When: rollback 실행
        rollback(journal_path)
        
        # Then: 파일들이 원래 위치로 되돌려져야 함
        original_files = list(hvdc_path.rglob("test_file*")) + list(cursor_path.rglob("test_file*"))
        assert len(original_files) >= 2, f"Expected files to be rolled back, found {len(original_files)}"
        
        # 내용 확인
        file_contents = []
        for file_path in original_files:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                file_contents.append(content)
        
        assert "test content A" in file_contents, "Content A should be preserved"
        assert "test content B" in file_contents, "Content B should be preserved"

    def test_should_handle_rollback_with_versioned_files(self, tmp_workspace: Path):
        """버전 충돌로 생성된 파일들도 올바르게 롤백되는지 테스트"""
        # Given: 중복 파일들이 버전 충돌로 처리된 상태
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"
        
        # 중복 파일 생성
        (hvdc_path / "dup.txt").write_text("A", encoding="utf-8")
        (cursor_path / "dup.txt").write_text("B", encoding="utf-8")
        
        # 스캔 및 organize 실행
        records, safe_map = scan_paths([hvdc_path, cursor_path])
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/")
        )
        
        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)
        
        # 버전 충돌 파일 확인
        target_files = list(target_path.rglob("dup*"))
        assert len(target_files) >= 2, "Versioned files should exist in target"
        
        # When: rollback 실행
        rollback(journal_path)
        
        # Then: 원래 위치에 파일들이 되돌려져야 함
        original_files = list(hvdc_path.rglob("dup*")) + list(cursor_path.rglob("dup*"))
        assert len(original_files) >= 2, f"Expected files to be rolled back, found {len(original_files)}"
        
        # 내용 확인
        file_contents = []
        for file_path in original_files:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                file_contents.append(content)
        
        assert "A" in file_contents, "Content A should be preserved"
        assert "B" in file_contents, "Content B should be preserved"

    def test_should_handle_missing_journal_file_gracefully(self, tmp_workspace: Path):
        """저널 파일이 없을 때 롤백이 안전하게 처리되는지 테스트"""
        # Given: 존재하지 않는 저널 파일
        journal_path = tmp_workspace / "nonexistent_journal.jsonl"
        
        # When: rollback 실행
        # Then: 예외가 발생하지 않아야 함
        try:
            rollback(journal_path)
            # 성공적으로 처리되어야 함
        except Exception as e:
            pytest.fail(f"Rollback should handle missing journal gracefully, but raised: {e}")

    def test_should_handle_corrupted_journal_entries_gracefully(self, tmp_workspace: Path):
        """손상된 저널 엔트리가 있을 때 롤백이 안전하게 처리되는지 테스트"""
        # Given: 손상된 저널 파일
        journal_path = tmp_workspace / "corrupted_journal.jsonl"
        
        # 유효한 엔트리와 손상된 엔트리 혼합
        journal_content = [
            '{"ts": 1234567890, "code": "MOVE", "src": "/valid/path", "dst": "/valid/dest"}',
            'invalid json line',
            '{"ts": 1234567891, "code": "COPY", "src": "/another/path", "dst": "/another/dest"}'
        ]
        
        journal_path.write_text('\n'.join(journal_content), encoding="utf-8")
        
        # When: rollback 실행
        # Then: 예외가 발생하지 않아야 함
        try:
            rollback(journal_path)
            # 성공적으로 처리되어야 함
        except Exception as e:
            pytest.fail(f"Rollback should handle corrupted journal gracefully, but raised: {e}")
