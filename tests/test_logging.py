import io
import json

from fechou.logging_setup import configure_logging, get_logger


def test_json_lines_with_run_id_and_extra_fields() -> None:
    stream = io.StringIO()
    configure_logging("run-123", "INFO", stream=stream)

    get_logger("test").info("source_read", extra={"rows_total": 10, "rows_invalid": 2})
    get_logger("test").debug("hidden")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["run_id"] == "run-123"
    assert event["event"] == "source_read"
    assert event["level"] == "INFO"
    assert event["logger"] == "fechou.test"
    assert (event["rows_total"], event["rows_invalid"]) == (10, 2)
    assert event["ts"].endswith("+00:00")


def test_reconfiguring_does_not_duplicate_handlers() -> None:
    stream = io.StringIO()
    configure_logging("a", stream=stream)
    configure_logging("b", stream=stream)

    get_logger("test").warning("once")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["run_id"] == "b"


def test_exceptions_are_serialized() -> None:
    stream = io.StringIO()
    configure_logging("x", stream=stream)

    try:
        raise ValueError("boom")
    except ValueError:
        get_logger("test").exception("failed")

    event = json.loads(stream.getvalue())
    assert "ValueError: boom" in event["exception"]
