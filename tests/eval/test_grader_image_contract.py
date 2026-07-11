from pathlib import Path


def test_grader_uses_isolated_python_startup() -> None:
    dockerfile = Path("eval/verifier/Dockerfile.grader").read_text(encoding="utf-8")
    shim = Path("eval/verifier/uv-shim-grader").read_text(encoding="utf-8")

    assert "COPY uv-shim-grader /usr/local/bin/uv" in dockerfile
    assert "ENV PYTHONPATH" not in dockerfile
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in shim
    assert "python -I -c" in shim
    assert 'sys.path.insert(0, "/opt/grader/tests")' in shim
