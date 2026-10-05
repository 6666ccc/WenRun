from io import StringIO

from loguru import logger

from app.core import logging as app_logging


def test_exception_logging_does_not_dump_sensitive_local_values(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(app_logging.sys, "stderr", output)
    app_logging.configure_logging()
    patient_secret = "synthetic-patient-secret-do-not-log"
    try:
        raise ValueError("synthetic failure")
    except ValueError:
        logger.exception("operation failed")
    assert patient_secret not in output.getvalue()
    assert "operation failed" in output.getvalue()
    # Restore the process-wide sink before pytest closes its capture stream.
    monkeypatch.undo()
    app_logging.configure_logging()
