"""Code analysis tools."""

from .parser import FreqtradeCodeParser, ParseResult
from .simhash import compute_code_hash, is_duplicate_code, normalize_code

__all__ = [
    "FreqtradeCodeParser",
    "ParseResult",
    "compute_code_hash",
    "is_duplicate_code",
    "normalize_code",
]
