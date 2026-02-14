from kora.executor import normalize_answer_json_string


def test_normalize_answer_json_string_parses_json_object_string() -> None:
    output = {"status": "success", "task_id": "x", "answer": '{"k":1}'}

    normalized = normalize_answer_json_string(output)

    assert normalized["answer"] == {"k": 1}


def test_normalize_answer_json_string_keeps_invalid_json_string() -> None:
    output = {"status": "success", "task_id": "x", "answer": "{not-json"}

    normalized = normalize_answer_json_string(output)

    assert normalized["answer"] == "{not-json"
