TOPIC_TAGS: tuple[str, ...] = (
    "animals",
    "colors",
    "family",
    "food",
    "school",
    "toys_and_games",
    "weather",
    "sports",
    "body",
    "clothing",
    "nature",
    "feelings",
    "transportation",
    "holidays",
)


def is_valid_tag(tag: str) -> bool:
    return tag in TOPIC_TAGS
