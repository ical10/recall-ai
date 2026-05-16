from app.services.interests import TOPIC_TAGS, is_valid_tag


def test_topic_tags_has_kid_friendly_categories() -> None:
    assert "animals" in TOPIC_TAGS
    assert "family" in TOPIC_TAGS
    assert "food" in TOPIC_TAGS
    assert "school" in TOPIC_TAGS
    assert "colors" in TOPIC_TAGS


def test_is_valid_tag_accepts_curated_tag() -> None:
    assert is_valid_tag("animals") is True


def test_is_valid_tag_rejects_unknown_tag() -> None:
    assert is_valid_tag("cryptocurrency") is False


def test_is_valid_tag_rejects_empty_string() -> None:
    assert is_valid_tag("") is False
