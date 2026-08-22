"""Unit tests for structured logging."""

import json
import logging

from atlas.core.logging import JSONFormatter, get_logger, setup_logging


def test_logging_setup_and_retrieval() -> None:
    setup_logging(level="DEBUG", log_format="console")
    logger = get_logger("core.test")
    assert logger.name == "atlas.core.test"


def test_json_formatter() -> None:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="atlas.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="test message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "atlas.test"
    assert parsed["message"] == "test message"
    assert "timestamp" in parsed
