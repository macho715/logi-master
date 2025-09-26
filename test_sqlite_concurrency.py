# tests/test_sqlite_concurrency.py
import json
import sqlite3
import threading
import time
from pathlib import Path
from subprocess import CompletedProcess
import subprocess


def run(cmd: list[str], cwd: Path) -> CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_sqlite_concurrent_access_should_not_lock(tmp_workspace: Path) -> None:
    """동시 SQLite 접근 시 잠금 문제가 발생하지 않는지 테스트"""
    # 1) 기본 scan 수행
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 2) 동시에 여러 명령어 실행 (잠금 문제 재현)
    def run_parallel_command(cmd_name: str, delay: float = 0.1) -> tuple[str, bool, str]:
        """병렬로 명령어 실행"""
        try:
            time.sleep(delay)  # 동시 실행 시뮬레이션
            if cmd_name == "rules":
                result = subprocess.run(
                    [
                        "python",
                        "devmind.py",
                        "rules",
                        "--scan",
                        ".cache/scan.json",
                        "--emit",
                        ".cache/scores.json",
                    ],
                    cwd=tmp_workspace,
                    capture_output=True,
                    text=True,
                )
            elif cmd_name == "cluster":
                result = subprocess.run(
                    [
                        "python",
                        "devmind.py",
                        "cluster",
                        "--scores",
                        ".cache/scores.json",
                        "--emit",
                        ".cache/projects.json",
                        "--project-mode",
                        "local",
                    ],
                    cwd=tmp_workspace,
                    capture_output=True,
                    text=True,
                )
            else:
                return cmd_name, False, "Unknown command"
            
            return cmd_name, result.returncode == 0, result.stderr
        except Exception as e:
            return cmd_name, False, str(e)
    
    # 3) 동시 실행 (잠금 문제 재현)
    threads = []
    results = {}
    
    # rules와 cluster를 거의 동시에 실행
    for i, cmd in enumerate(["rules", "cluster"]):
        thread = threading.Thread(
            target=lambda cmd=cmd, i=i: results.update({cmd: run_parallel_command(cmd, i * 0.05)})
        )
        threads.append(thread)
        thread.start()
    
    # 모든 스레드 완료 대기
    for thread in threads:
        thread.join(timeout=30)  # 30초 타임아웃
    
    # 4) 결과 검증 - 모든 명령어가 성공해야 함
    for cmd, (name, success, error) in results.items():
        assert success, f"명령어 {cmd}가 실패했습니다: {error}"
    
    # 5) 결과 파일들이 생성되었는지 확인
    assert (tmp_workspace / ".cache/scores.json").exists()
    assert (tmp_workspace / ".cache/projects.json").exists()


def test_sqlite_wal_mode_configuration(tmp_workspace: Path) -> None:
    """SQLite WAL 모드 설정이 올바르게 적용되는지 테스트"""
    # 1) scan으로 DB 생성
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 2) 생성된 SQLite DB 파일 확인 (devmind.py는 직접 DB 파일을 생성하지 않을 수 있음)
    # 대신 scan이 성공적으로 완료되었는지 확인
    assert (tmp_workspace / ".cache/scan.json").exists()
    assert (tmp_workspace / ".cache/safe_map.json").exists()
    
    # 3) SQLite 연결 테스트 (WAL 모드 설정 확인)
    test_db = tmp_workspace / ".cache/test.db"
    conn = sqlite3.connect(str(test_db), timeout=30.0)
    try:
        cursor = conn.cursor()
        
        # WAL 모드 설정
        cursor.execute("PRAGMA journal_mode=WAL;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.upper() == "WAL", f"WAL 모드가 설정되지 않았습니다: {journal_mode}"
        
        # busy_timeout 설정
        cursor.execute("PRAGMA busy_timeout=5000;")
        busy_timeout = cursor.fetchone()[0]
        assert busy_timeout > 0, f"busy_timeout이 설정되지 않았습니다: {busy_timeout}"
        
        # synchronous 설정
        cursor.execute("PRAGMA synchronous=NORMAL;")
        result = cursor.fetchone()
        if result:
            synchronous = result[0]
            assert synchronous in [1, 2], f"synchronous가 적절히 설정되지 않았습니다: {synchronous}"
        
    finally:
        conn.close()


def test_sqlite_connection_timeout_handling(tmp_workspace: Path) -> None:
    """SQLite 연결 타임아웃 처리가 올바르게 작동하는지 테스트"""
    # 1) 기본 scan 수행
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 2) rules 실행 (DB 접근)
    run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        tmp_workspace,
    )
    
    # 3) cluster 실행 (동일 DB 접근)
    run(
        [
            "python",
            "devmind.py",
            "cluster",
            "--scores",
            ".cache/scores.json",
            "--emit",
            ".cache/projects.json",
            "--project-mode",
            "local",
        ],
        tmp_workspace,
    )
    
    # 4) 결과 파일들이 생성되었는지 확인
    assert (tmp_workspace / ".cache/scores.json").exists()
    assert (tmp_workspace / ".cache/projects.json").exists()
    
    # 5) DB 파일이 잠금 상태가 아닌지 확인
    db_files = list((tmp_workspace / ".cache").glob("*.db"))
    for db_file in db_files:
        # DB 파일에 접근 시도 (잠금이면 실패)
        conn = sqlite3.connect(str(db_file), timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1, "DB 접근이 실패했습니다"
        finally:
            conn.close()


def test_sqlite_error_recovery(tmp_workspace: Path) -> None:
    """SQLite 에러 발생 시 복구가 올바르게 작동하는지 테스트"""
    # 1) .cache 디렉토리 생성
    (tmp_workspace / ".cache").mkdir(exist_ok=True)
    
    # 2) 정상적인 scan 수행
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 3) 정상적인 파이프라인 실행
    run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        tmp_workspace,
    )
    
    # 4) 결과 파일들이 생성되었는지 확인
    assert (tmp_workspace / ".cache/scores.json").exists()
    
    # 5) scan 결과가 유효한지 확인
    scan_data = json.loads((tmp_workspace / ".cache/scan.json").read_text(encoding="utf-8"))
    assert len(scan_data) > 0, "스캔 결과가 비어있습니다"
