import pytest

from src.llm.json_parser import parse_json_array, parse_json_object


def test_parse_plain_json_object():
    assert parse_json_object('{"hello": "world"}') == {"hello": "world"}


def test_parse_fenced_json_object():
    text = """```json
{"hello": "world"}
```"""

    assert parse_json_object(text) == {"hello": "world"}


def test_parse_json_object_with_extra_text():
    text = 'Here is the result:\n{"hello": "world"}\nDone.'

    assert parse_json_object(text) == {"hello": "world"}


def test_parse_invalid_object_input_raises_value_error():
    with pytest.raises(ValueError, match="Could not"):
        parse_json_object("No JSON object here.")


def test_parse_plain_json_array():
    assert parse_json_array('[{"hello": "world"}]') == [{"hello": "world"}]


def test_parse_fenced_json_array():
    text = """```json
[{"hello": "world"}]
```"""

    assert parse_json_array(text) == [{"hello": "world"}]


def test_parse_json_array_with_extra_text():
    text = 'Here is the result:\n[{"hello": "world"}]\nDone.'

    assert parse_json_array(text) == [{"hello": "world"}]


def test_parse_invalid_array_input_raises_value_error():
    with pytest.raises(ValueError, match="Could not"):
        parse_json_array("No JSON array here.")
