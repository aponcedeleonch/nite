from typing import Optional
import re


INVALID_CHARS = ['\n', ';']
ESCAPED_CHARS = [',']


def clean_pd_str(pd_str: Optional[str]) -> Optional[str]:
    if not pd_str:
        return pd_str
    pd_str = remove_invalid_chars(pd_str)
    pd_str = escape_chars(pd_str)
    return pd_str


def remove_invalid_chars(pd_str: Optional[str]) -> Optional[str]:
    if not pd_str:
        return pd_str

    for char in INVALID_CHARS:
        pd_str = pd_str.replace(char, '')
    return pd_str


def escape_chars(pd_str: Optional[str]) -> Optional[str]:
    if not pd_str:
        return pd_str

    for char in ESCAPED_CHARS:
        pd_str = re.sub(r'(?<!\\)' + re.escape(char), '\\' + char, pd_str)
    return pd_str


def transform_str_to_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    return int(float(value))
