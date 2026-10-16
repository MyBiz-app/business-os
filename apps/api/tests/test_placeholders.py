from app.messaging.placeholders import missing_counts, render_placeholders, used_variables


def test_fallback_unknown_and_blank_values() -> None:
    values = {"first_name": "Dana", "plan_name": "  ", "branch": ""}
    text = "{first_name}|{plan_name|member}|{branch}|{nope|x}|{id_number}"
    assert render_placeholders(text, values) == "Dana|member||{nope|x}|{id_number}"


def test_full_id_number_is_not_a_variable() -> None:
    assert used_variables("{id_number} {id_last4} {id_last4|n/a}") == {"id_last4": False}


def test_missing_counts_skip_variables_with_fallback() -> None:
    people = [{"plan_name": "A"}, {"plan_name": ""}, {}]
    assert missing_counts("{plan_name} {phone|none}", people) == {"plan_name": 2}
