from apps.api import RUNTIME_NAME as API_RUNTIME_NAME
from apps.worker import RUNTIME_NAME as WORKER_RUNTIME_NAME
from backend.auditor import __version__


def test_python_workspace_boundaries_are_importable() -> None:
    assert API_RUNTIME_NAME == "api"
    assert WORKER_RUNTIME_NAME == "worker"
    assert __version__ == "0.0.0"
