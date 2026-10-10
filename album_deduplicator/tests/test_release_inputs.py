import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_dependencies


@pytest.mark.parametrize("name", ["lgbm_regressor_model.joblib", "singer-list.csv"])
def test_release_assets_are_available_in_a_clean_git_checkout(name):
    project = Path(__file__).resolve().parents[1]
    assert (project / "data" / name).is_file()
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", f"album_deduplicator/data/{name}"],
        cwd=project.parent, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Release asset is not tracked: {name}"


def test_dependency_checker_imports_the_sklearn_runtime_for_scikit_learn(monkeypatch, tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("scikit-learn\n", encoding="utf-8")
    monkeypatch.setattr(check_dependencies, "REQUIREMENTS_PATH", requirements)
    monkeypatch.setattr(check_dependencies.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    # Actual installed sklearn is imported; pip check is isolated from unrelated
    # packages in the developer's global environment.
    assert check_dependencies.check_python_dependencies() == []
