import json
import logging

from intentkit.utils.logging import JsonFormatter


def create_log_record(message: str) -> logging.LogRecord:
    record = logging.LogRecord(
        name="intentkit.tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.__dict__["extra"] = {"component": "tests"}
    return record


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    record = create_log_record("hello world")

    output = formatter.format(record)
    payload = json.loads(output)

    assert payload["message"] == "hello world"
    assert payload["component"] == "tests"
    assert payload["name"] == "intentkit.tests"


def test_json_formatter_respects_filter_function():
    formatter = JsonFormatter(lambda record: False)
    record = create_log_record("filtered")

    assert formatter.format(record) == ""
