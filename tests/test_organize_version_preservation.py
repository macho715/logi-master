"""S2 단계: organize가 중복 이름 파일을 2개 모두 보존하는 테스트"""

import json
from pathlib import Path

import pytest

from organize import OrganizeConfig, organize_files
from scan import FileRecord, scan_paths


class TestOrganizeVersionPreservation:
    """중복 파일 보존 기능 테스트"""

    def test_should_preserve_duplicate_files_with_hash_suffix(self, tmp_workspace: Path):
        """중복 파일이 __{hash7} 서픽스로 모두 보존되는지 테스트"""
        # Given: 중복 이름 파일들이 있는 워크스페이스
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"

        # 중복 파일 직접 생성
        (hvdc_path / "dup.txt").write_text("A", encoding="utf-8")
        (cursor_path / "dup.txt").write_text("B", encoding="utf-8")

        # 스캔 실행
        records, safe_map = scan_paths([hvdc_path, cursor_path])

        # 중복 파일 확인 (dup.txt가 2개 있어야 함)
        dup_files = [r for r in records if r.name == "dup.txt"]
        assert len(dup_files) == 2, f"Expected 2 dup.txt files, found {len(dup_files)}"

        # When: organize 실행 (version 충돌 정책)
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/"),
        )

        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)

        # Then: 두 파일 모두 보존되어야 함 (해시 서픽스 포함)
        target_files = list(target_path.rglob("dup*"))
        assert (
            len(target_files) >= 2
        ), f"Expected at least 2 dup files in target, found {len(target_files)}"

        # 파일 내용 확인
        file_contents = []
        for file_path in target_files:
            content = file_path.read_text(encoding="utf-8")
            file_contents.append(content)

        # "A"와 "B" 내용이 모두 보존되어야 함
        assert "A" in file_contents, "Content 'A' should be preserved"
        assert "B" in file_contents, "Content 'B' should be preserved"

        # 해시 서픽스 확인
        hash_suffixed_files = [f for f in target_files if "__" in f.name]
        assert len(hash_suffixed_files) >= 1, "At least one file should have hash suffix"

    def test_should_generate_unique_hash_suffixes_for_duplicates(self, tmp_workspace: Path):
        """중복 파일들이 서로 다른 해시 서픽스를 가지는지 테스트"""
        # Given: 중복 파일들
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"

        # 중복 파일 직접 생성
        (hvdc_path / "dup.txt").write_text("A", encoding="utf-8")
        (cursor_path / "dup.txt").write_text("B", encoding="utf-8")

        records, safe_map = scan_paths([hvdc_path, cursor_path])

        # When: organize 실행
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/"),
        )

        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)

        # Then: 해시 서픽스가 서로 달라야 함
        target_files = list(target_path.rglob("dup*"))
        hash_suffixed_files = [f for f in target_files if "__" in f.name]

        if len(hash_suffixed_files) >= 2:
            suffixes = [f.stem.split("__")[-1] for f in hash_suffixed_files]
            assert len(set(suffixes)) == len(suffixes), "Hash suffixes should be unique"

    def test_should_record_version_conflicts_in_journal(self, tmp_workspace: Path):
        """버전 충돌이 저널에 기록되는지 테스트"""
        # Given: 중복 파일들
        hvdc_path = tmp_workspace / "C_HVDC_PJT"
        cursor_path = tmp_workspace / "C_cursor_mcp"
        target_path = tmp_workspace / "PROJECTS_STRUCT"

        # 중복 파일 직접 생성
        (hvdc_path / "dup.txt").write_text("A", encoding="utf-8")
        (cursor_path / "dup.txt").write_text("B", encoding="utf-8")

        records, safe_map = scan_paths([hvdc_path, cursor_path])

        # When: organize 실행
        config = OrganizeConfig(
            target_root=target_path,
            mode="move",
            conflict="version",
            schema_paths=("src/", "docs/", "tests/", "scripts/", "misc/"),
        )

        journal_path = tmp_workspace / "journal.jsonl"
        organize_files(records, safe_map, config, journal_path)

        # Then: 저널에 버전 충돌 기록이 있어야 함
        assert journal_path.exists(), "Journal file should exist"

        journal_entries = []
        with journal_path.open("r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line.strip())
                journal_entries.append(entry)

        # 버전 충돌 관련 엔트리 확인
        version_conflicts = [e for e in journal_entries if "version" in str(e).lower()]
        assert len(version_conflicts) > 0, "Should have version conflict entries in journal"
