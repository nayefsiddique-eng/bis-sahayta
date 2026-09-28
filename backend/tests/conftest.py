import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add the backend directory to sys.path so that 'app' can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(autouse=True)
def isolate_env(tmp_path):
    """Set up environment variables for testing and isolate session db and feedback log."""
    # Set environment variables for testing
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["GEMINI_API_KEY"] = ""

    # Create temporary directories for session db and feedback log
    session_db_path = str(tmp_path / "sessions.db")
    feedback_log_path = str(tmp_path / "feedback_log.json")
    os.environ["SESSION_DB_PATH"] = session_db_path
    os.environ["FEEDBACK_LOG_PATH"] = feedback_log_path

    # Reload settings to pick up environment variables (in case they changed)
    from importlib import reload
    from app.core import config as settings_config
    reload(settings_config)

    # Reset LLM provider instance
    from app.services import llm_service
    llm_service._provider_instance = None
    # Reload llm_service to pick up the new settings
    reload(llm_service)

    # Reload session_db module to pick up the new SESSION_DB_PATH
    from app.services import session_db
    reload(session_db)

    # Reload feedback module to pick up the new FEEDBACK_LOG_PATH
    from app.routers import feedback
    reload(feedback)

    yield

    # Teardown: clean up environment variables
    os.environ.pop("LLM_PROVIDER", None)
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("SESSION_DB_PATH", None)
    os.environ.pop("FEEDBACK_LOG_PATH", None)