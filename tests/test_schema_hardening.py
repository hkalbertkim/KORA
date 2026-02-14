from kora.adapters.openai_adapter import harden_schema_for_openai


def test_harden_schema_adds_additional_properties_false_recursively() -> None:
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "meta": {
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                },
            },
        },
        "required": ["name", "meta"],
    }

    hardened = harden_schema_for_openai(input_schema)

    assert "additionalProperties" not in input_schema
    assert hardened["additionalProperties"] is False
    assert hardened["properties"]["meta"]["additionalProperties"] is False


def test_harden_schema_adds_additional_properties_for_array_items() -> None:
    input_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                },
            },
        },
    }

    hardened = harden_schema_for_openai(input_schema)

    assert hardened["additionalProperties"] is False
    assert hardened["properties"]["items"]["items"]["additionalProperties"] is False
