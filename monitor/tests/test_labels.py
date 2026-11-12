import json

from monitor.ai.labels import BATCH_SCHEMA, LABEL_SCHEMA, ArticleLabel, parse_labels
from monitor.tools.probe import clean, match_schema, openapi

UPDATE = {
    "id": "1", "kind": "update", "domain": "terrorism", "sk_link": "indirect",
    "countries": ["PL"], "incident_type": "attack", "severity": 5,
    "incident_date": "2026-11-07", "incident_country": "PL", "incident_place": "Kraków",
    "ideology": "unknown",
    "summary_en": "The alleged Kraków shooter died of his injuries in hospital.",
    "summary_sk": "Údajný strelec z Krakova zomrel v nemocnici na následky zranení.",
    "confidence": 0.9,
}
CONTEXT = UPDATE | {"id": "2", "kind": "context", "incident_type": None, "severity": 0,
                    "incident_date": None, "incident_country": None, "incident_place": None}


def test_schema_asks_for_every_field_of_the_label():
    # Strict modes require every property to be listed as required.
    assert list(LABEL_SCHEMA["properties"]) == list(ArticleLabel.model_fields)
    assert LABEL_SCHEMA["required"] == list(ArticleLabel.model_fields)
    assert LABEL_SCHEMA["additionalProperties"] is False
    assert BATCH_SCHEMA["properties"]["items"]["items"] is LABEL_SCHEMA


def test_fields_that_may_not_apply_allow_null():
    for name in ("incident_type", "incident_date", "incident_country", "incident_place"):
        assert LABEL_SCHEMA["properties"][name]["type"] == ["string", "null"]
    assert None in LABEL_SCHEMA["properties"]["incident_type"]["enum"]


def test_an_update_and_a_context_item_are_both_valid_labels():
    labels, errors = parse_labels(json.dumps({"items": [UPDATE, CONTEXT]}), {"1", "2"})
    assert errors == []
    assert labels["1"].incident_date == "2026-11-07"
    assert labels["1"].problems() == [] and labels["2"].problems() == []


def test_one_malformed_label_does_not_lose_the_others():
    broken = {k: v for k, v in UPDATE.items() if k != "summary_sk"} | {"id": "2"}
    labels, errors = parse_labels(json.dumps({"items": [UPDATE, broken]}), {"1", "2"})
    assert list(labels) == ["1"]
    assert len(errors) == 1 and "summary_sk" in errors[0]


def test_a_label_for_an_article_that_was_not_sent_is_refused():
    labels, errors = parse_labels(json.dumps({"items": [UPDATE | {"id": "9"}]}), {"1"})
    assert labels == {} and errors == ["unknown id '9'"]


def test_a_label_that_contradicts_itself_says_how():
    assert ArticleLabel(**CONTEXT | {"severity": 3}).problems() == ["context with incident facts"]
    assert ArticleLabel(**UPDATE | {"severity": 0}).problems() == ["update with severity 0"]
    assert ArticleLabel(**UPDATE | {"summary_sk": ""}).problems() == ["update without a summary"]


def test_a_date_that_is_not_a_date_is_refused():
    labels, errors = parse_labels(
        json.dumps({"items": [UPDATE | {"incident_date": "last Saturday"}]}), {"1"})
    assert labels == {} and "incident_date" in errors[0]


def test_older_gemini_schema_style_uses_nullable():
    old = openapi(BATCH_SCHEMA)
    label = old["properties"]["items"]["items"]
    assert "additionalProperties" not in old and "additionalProperties" not in label
    assert label["properties"]["incident_type"]["type"] == "string"
    assert label["properties"]["incident_type"]["nullable"] is True
    assert None not in label["properties"]["incident_type"]["enum"]
    assert label["properties"]["severity"] == {"type": "integer", "enum": [0, 1, 2, 3, 4, 5]}
    # The schema sent in strict mode is left as it was.
    assert LABEL_SCHEMA["properties"]["incident_type"]["type"] == ["string", "null"]


def test_a_match_may_only_name_a_listed_incident_or_new():
    entry = match_schema(["inc1", "inc2"])["properties"]["matches"]["items"]
    assert entry["properties"]["incident"]["enum"] == ["inc1", "inc2", "new"]


def test_error_text_for_the_public_log_hides_the_organisation_id():
    assert clean("Request too large in organization `org_01abcXYZ`\n on TPM") == (
        "Request too large in organization `org_(hidden)` on TPM")
