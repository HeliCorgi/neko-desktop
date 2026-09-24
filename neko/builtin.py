"""Built-in coat identifiers, independent of artwork and animation logic."""

BUILTIN_COATS = {
    "kijitora": "キジトラ",
    "chatora": "茶トラ",
    "white": "白猫",
    "black": "黒猫",
}
DEFAULT_COAT = "kijitora"


def validate_coat(coat: str) -> str:
    """Accept only known coat IDs; never interpret a selection as a file path."""
    if not isinstance(coat, str) or coat not in BUILTIN_COATS:
        raise ValueError("Unknown built-in cat coat")
    return coat
