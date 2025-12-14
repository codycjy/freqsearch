"""Code similarity detection using SimHash.

SimHash is a locality-sensitive hashing technique that produces similar
hashes for similar content. This allows us to detect duplicate or
near-duplicate strategies efficiently.
"""

import re
import hashlib
from typing import Sequence

import structlog

logger = structlog.get_logger(__name__)


def normalize_code(code: str) -> str:
    """Normalize Python code for comparison.

    Removes:
    - Comments
    - Docstrings
    - Extra whitespace
    - Variable name variations (optional)

    Args:
        code: Python source code

    Returns:
        Normalized code string
    """
    lines = []

    in_multiline_string = False
    multiline_char = None

    for line in code.split("\n"):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Skip single-line comments
        if stripped.startswith("#"):
            continue

        # Handle multiline strings (docstrings)
        if '"""' in stripped or "'''" in stripped:
            quote = '"""' if '"""' in stripped else "'''"
            count = stripped.count(quote)

            if not in_multiline_string:
                if count == 1:
                    in_multiline_string = True
                    multiline_char = quote
                # count == 2 means single-line docstring, skip it
                continue
            else:
                if quote == multiline_char:
                    in_multiline_string = False
                continue

        if in_multiline_string:
            continue

        # Remove inline comments
        if "#" in stripped:
            # Simple heuristic: split on # not in strings
            # This is imperfect but good enough for similarity
            parts = stripped.split("#")
            stripped = parts[0].strip()
            if not stripped:
                continue

        # Normalize whitespace
        stripped = re.sub(r"\s+", " ", stripped)

        lines.append(stripped)

    return " ".join(lines)


def _shingles(text: str, k: int = 3) -> set[str]:
    """Generate k-shingles (k-grams) from text.

    Args:
        text: Input text
        k: Shingle size

    Returns:
        Set of k-shingles
    """
    tokens = text.split()
    if len(tokens) < k:
        return {text}

    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _hash_shingle(shingle: str) -> int:
    """Hash a shingle to a 64-bit integer.

    Args:
        shingle: Text shingle

    Returns:
        64-bit hash value
    """
    h = hashlib.md5(shingle.encode()).hexdigest()
    return int(h[:16], 16)


def compute_simhash(text: str, hash_bits: int = 64) -> int:
    """Compute SimHash of text.

    SimHash works by:
    1. Generating shingles from the text
    2. Hashing each shingle
    3. For each bit position, sum +1 if bit is 1, -1 if bit is 0
    4. Final hash: bit is 1 if sum > 0, else 0

    Args:
        text: Input text
        hash_bits: Number of bits in the hash

    Returns:
        SimHash as integer
    """
    shingles = _shingles(text)

    if not shingles:
        return 0

    # Initialize bit counts
    v = [0] * hash_bits

    # Process each shingle
    for shingle in shingles:
        h = _hash_shingle(shingle)

        for i in range(hash_bits):
            bit = (h >> i) & 1
            if bit:
                v[i] += 1
            else:
                v[i] -= 1

    # Generate final hash
    simhash = 0
    for i in range(hash_bits):
        if v[i] > 0:
            simhash |= 1 << i

    return simhash


def compute_code_hash(code: str) -> str:
    """Compute a SimHash for strategy code.

    The code is normalized before hashing to make the hash
    resistant to cosmetic changes like formatting and comments.

    Args:
        code: Python source code

    Returns:
        SimHash as hex string
    """
    normalized = normalize_code(code)
    simhash = compute_simhash(normalized)
    return hex(simhash)[2:]  # Remove '0x' prefix


def hamming_distance(hash1: int, hash2: int) -> int:
    """Calculate Hamming distance between two hashes.

    Hamming distance is the number of positions where the bits differ.

    Args:
        hash1: First hash value
        hash2: Second hash value

    Returns:
        Number of differing bits
    """
    xor = hash1 ^ hash2
    return bin(xor).count("1")


def is_duplicate_code(
    hash1: str,
    hash2: str,
    threshold: int = 3,
) -> bool:
    """Check if two code hashes indicate duplicate/similar code.

    Args:
        hash1: First SimHash (hex string)
        hash2: Second SimHash (hex string)
        threshold: Maximum Hamming distance to consider as duplicate

    Returns:
        True if the codes are considered duplicates
    """
    try:
        h1 = int(hash1, 16)
        h2 = int(hash2, 16)
    except ValueError:
        return False

    distance = hamming_distance(h1, h2)
    return distance <= threshold


def find_duplicates(
    hashes: Sequence[tuple[str, str]],
    threshold: int = 3,
) -> list[tuple[str, str, int]]:
    """Find all duplicate pairs in a list of (id, hash) tuples.

    Args:
        hashes: List of (identifier, hash) tuples
        threshold: Maximum Hamming distance for duplicates

    Returns:
        List of (id1, id2, distance) tuples for duplicates
    """
    duplicates = []

    for i, (id1, hash1) in enumerate(hashes):
        for id2, hash2 in hashes[i + 1 :]:
            try:
                h1 = int(hash1, 16)
                h2 = int(hash2, 16)
                distance = hamming_distance(h1, h2)

                if distance <= threshold:
                    duplicates.append((id1, id2, distance))
            except ValueError:
                continue

    return duplicates


def deduplicate_strategies(
    strategies: list[dict],
    hash_field: str = "code_hash",
    id_field: str = "name",
    threshold: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Remove duplicate strategies from a list.

    Args:
        strategies: List of strategy dictionaries
        hash_field: Field name containing the code hash
        id_field: Field name for strategy identifier
        threshold: Hamming distance threshold

    Returns:
        Tuple of (unique strategies, duplicate strategies)
    """
    if not strategies:
        return [], []

    unique = [strategies[0]]
    duplicates = []

    for strategy in strategies[1:]:
        is_dup = False
        current_hash = strategy.get(hash_field, "")

        if not current_hash:
            unique.append(strategy)
            continue

        for existing in unique:
            existing_hash = existing.get(hash_field, "")
            if existing_hash and is_duplicate_code(current_hash, existing_hash, threshold):
                is_dup = True
                logger.debug(
                    "Found duplicate strategy",
                    duplicate=strategy.get(id_field),
                    original=existing.get(id_field),
                )
                break

        if is_dup:
            duplicates.append(strategy)
        else:
            unique.append(strategy)

    logger.info(
        "Deduplication complete",
        unique_count=len(unique),
        duplicate_count=len(duplicates),
    )

    return unique, duplicates
