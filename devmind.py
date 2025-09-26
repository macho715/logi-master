"""기존 devmind CLI는 autosort 엔트리포인트를 위임합니다./Legacy wrapper delegating to autosort CLI."""

from autosort import cli

if __name__ == "__main__":
    cli()
