"""Tests for SimHash code similarity detection."""

import pytest

from freqsearch_agents.tools.code.simhash import (
    normalize_code,
    compute_code_hash,
    is_duplicate_code,
    hamming_distance,
    deduplicate_strategies,
)


class TestNormalizeCode:
    """Tests for code normalization."""

    def test_remove_comments(self):
        """Test that comments are removed."""
        code = """
# This is a comment
def foo():
    pass  # inline comment
"""
        normalized = normalize_code(code)
        assert "#" not in normalized
        assert "comment" not in normalized

    def test_remove_docstrings(self):
        """Test that docstrings are removed."""
        code = '''
def foo():
    """This is a docstring."""
    pass
'''
        normalized = normalize_code(code)
        assert "docstring" not in normalized

    def test_normalize_whitespace(self):
        """Test that whitespace is normalized."""
        code = """
def    foo():
    if   True:
        pass
"""
        normalized = normalize_code(code)
        # Multiple spaces should become single space
        assert "   " not in normalized


class TestComputeCodeHash:
    """Tests for code hash computation."""

    def test_identical_code_same_hash(self):
        """Test that identical code produces same hash."""
        code = "def foo(): pass"
        hash1 = compute_code_hash(code)
        hash2 = compute_code_hash(code)
        assert hash1 == hash2

    def test_different_code_different_hash(self):
        """Test that different code produces different hash."""
        code1 = "def foo(): pass"
        code2 = "def bar(): return 42"
        hash1 = compute_code_hash(code1)
        hash2 = compute_code_hash(code2)
        assert hash1 != hash2

    def test_similar_code_similar_hash(self):
        """Test that similar code produces similar hash (low hamming distance)."""
        code1 = """
def foo():
    x = 10
    return x + 1
"""
        code2 = """
def foo():
    x = 20
    return x + 1
"""
        hash1 = compute_code_hash(code1)
        hash2 = compute_code_hash(code2)

        # Hashes should be somewhat similar (not identical, but close)
        h1 = int(hash1, 16)
        h2 = int(hash2, 16)
        distance = hamming_distance(h1, h2)

        # Similar code should have relatively low hamming distance
        assert distance < 32  # Less than half of 64 bits


class TestIsDuplicateCode:
    """Tests for duplicate detection."""

    def test_identical_is_duplicate(self):
        """Test that identical hashes are detected as duplicate."""
        hash1 = compute_code_hash("def foo(): pass")
        assert is_duplicate_code(hash1, hash1, threshold=3)

    def test_different_not_duplicate(self):
        """Test that very different code is not duplicate."""
        hash1 = compute_code_hash("def foo(): pass")
        hash2 = compute_code_hash("class Bar: x = 42; def method(self): return self.x * 2")
        assert not is_duplicate_code(hash1, hash2, threshold=3)


class TestDeduplicateStrategies:
    """Tests for strategy deduplication."""

    def test_deduplicate_removes_duplicates(self):
        """Test that duplicates are removed."""
        strategies = [
            {"name": "Strategy1", "code_hash": "abc123"},
            {"name": "Strategy2", "code_hash": "abc123"},  # Same hash
            {"name": "Strategy3", "code_hash": "def456"},
        ]

        unique, duplicates = deduplicate_strategies(strategies, threshold=3)

        assert len(unique) == 2
        assert len(duplicates) == 1
        assert duplicates[0]["name"] == "Strategy2"

    def test_deduplicate_empty_list(self):
        """Test deduplication of empty list."""
        unique, duplicates = deduplicate_strategies([])
        assert unique == []
        assert duplicates == []

    def test_deduplicate_single_item(self):
        """Test deduplication of single item."""
        strategies = [{"name": "Strategy1", "code_hash": "abc123"}]
        unique, duplicates = deduplicate_strategies(strategies)
        assert len(unique) == 1
        assert len(duplicates) == 0
