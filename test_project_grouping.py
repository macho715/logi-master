from __future__ import annotations

from devmind import DEFAULT_HINTS, local_cluster


def test_local_cluster_derives_project_label_from_common_directory() -> None:
    items = [
        {
            "path": r"C:\\HVDC PJT\\ProjectAlpha\\src\\alpha.py",
            "name": "alpha.py",
            "hint": "alpha source module",
            "bucket": "src",
        },
        {
            "path": r"C:\\HVDC PJT\\ProjectAlpha\\docs\\alpha.md",
            "name": "alpha.md",
            "hint": "alpha documentation",
            "bucket": "docs",
        },
    ]

    result = local_cluster(items, k=1, hints=DEFAULT_HINTS)
    assert result["projects"], "Expected at least one project cluster"
    project = result["projects"][0]
    assert project["project_label"] == "projectalpha"
    assert project["project_id"] == "projectalpha"
