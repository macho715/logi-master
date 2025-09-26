# tests/test_performance.py
import time
from pathlib import Path
import pytest
from subprocess import CompletedProcess
import subprocess


def run(cmd: list[str], cwd: Path) -> CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_scan_performance(tmp_workspace: Path) -> None:
    """스캔 성능 테스트"""
    start_time = time.time()
    
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
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 스캔이 10초 이내에 완료되어야 함
    assert duration < 10.0, f"스캔이 너무 오래 걸렸습니다: {duration:.2f}초"


def test_rules_performance(tmp_workspace: Path) -> None:
    """규칙 엔진 성능 테스트"""
    # 1) scan 먼저 수행
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
    
    start_time = time.time()
    
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
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 규칙 처리가 5초 이내에 완료되어야 함
    assert duration < 5.0, f"규칙 처리가 너무 오래 걸렸습니다: {duration:.2f}초"


def test_cluster_performance(tmp_workspace: Path) -> None:
    """클러스터링 성능 테스트"""
    # 1) scan + rules 먼저 수행
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
    
    start_time = time.time()
    
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
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 클러스터링이 15초 이내에 완료되어야 함
    assert duration < 15.0, f"클러스터링이 너무 오래 걸렸습니다: {duration:.2f}초"


def test_organize_performance(tmp_workspace: Path) -> None:
    """조직화 성능 테스트"""
    # 1) 전체 파이프라인 먼저 수행
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
    
    start_time = time.time()
    
    run(
        [
            "python",
            "devmind.py",
            "organize",
            "--projects",
            ".cache/projects.json",
            "--scores",
            ".cache/scores.json",
            "--target",
            str(tmp_workspace / "PERFORMANCE_TEST_OUTPUT"),
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            ".cache/journal.jsonl",
        ],
        tmp_workspace,
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 조직화가 10초 이내에 완료되어야 함
    assert duration < 10.0, f"조직화가 너무 오래 걸렸습니다: {duration:.2f}초"


def test_full_pipeline_performance(tmp_workspace: Path) -> None:
    """전체 파이프라인 성능 테스트"""
    start_time = time.time()
    
    # 전체 파이프라인 실행
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
    
    run(
        [
            "python",
            "devmind.py",
            "organize",
            "--projects",
            ".cache/projects.json",
            "--scores",
            ".cache/scores.json",
            "--target",
            str(tmp_workspace / "FULL_PIPELINE_OUTPUT"),
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            ".cache/journal.jsonl",
        ],
        tmp_workspace,
    )
    
    run(
        [
            "python",
            "devmind.py",
            "report",
            "--journal",
            ".cache/journal.jsonl",
            "--out",
            "reports/performance_test.html",
        ],
        tmp_workspace,
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 전체 파이프라인이 60초 이내에 완료되어야 함
    assert duration < 60.0, f"전체 파이프라인이 너무 오래 걸렸습니다: {duration:.2f}초"
    
    # 결과 파일들이 생성되었는지 확인
    assert (tmp_workspace / "FULL_PIPELINE_OUTPUT").exists()
    assert (tmp_workspace / "reports/performance_test.html").exists()


@pytest.mark.benchmark
def test_memory_usage(tmp_workspace: Path) -> None:
    """메모리 사용량 테스트"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # 전체 파이프라인 실행
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
    
    peak_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = peak_memory - initial_memory
    
    # 메모리 사용량이 500MB 이하로 증가해야 함
    assert memory_increase < 500, f"메모리 사용량이 너무 많습니다: {memory_increase:.2f}MB 증가"


@pytest.mark.benchmark
def test_concurrent_operations(tmp_workspace: Path) -> None:
    """동시 작업 성능 테스트"""
    import threading
    import queue
    
    results = queue.Queue()
    
    def run_scan_task(task_id: int):
        """스캔 작업"""
        try:
            start_time = time.time()
            run(
                [
                    "python",
                    "devmind.py",
                    "scan",
                    "--paths",
                    str(tmp_workspace / "C_HVDC_PJT"),
                    "--emit",
                    f".cache/scan_{task_id}.json",
                    "--safe-map",
                    f".cache/safe_map_{task_id}.json",
                ],
                tmp_workspace,
            )
            end_time = time.time()
            results.put(("scan", task_id, end_time - start_time, True))
        except Exception as e:
            results.put(("scan", task_id, 0, False))
    
    # 3개의 동시 스캔 작업 실행
    threads = []
    for i in range(3):
        thread = threading.Thread(target=run_scan_task, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 모든 스레드 완료 대기
    for thread in threads:
        thread.join(timeout=30)
    
    # 결과 확인
    success_count = 0
    total_time = 0
    
    while not results.empty():
        task_type, task_id, duration, success = results.get()
        if success:
            success_count += 1
            total_time += duration
    
    # 최소 2개 작업이 성공해야 함
    assert success_count >= 2, f"동시 작업 성공률이 낮습니다: {success_count}/3"
    
    # 평균 실행 시간이 15초 이하여야 함
    avg_time = total_time / success_count if success_count > 0 else 0
    assert avg_time < 15.0, f"동시 작업 평균 시간이 너무 깁니다: {avg_time:.2f}초"
