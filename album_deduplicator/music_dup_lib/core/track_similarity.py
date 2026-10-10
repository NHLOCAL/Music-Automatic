"""Exact, bounded reuse of ordered string comparisons within one analysis."""
from collections import OrderedDict
from typing import Iterable, Optional

from rapidfuzz import fuzz


class StringSequenceComparer:
    def __init__(self, cache_size: int = 10000):
        self._sequence_ids: dict[tuple[Optional[str], ...], int] = {}
        self._sequences: list[tuple[Optional[str], ...]] = []
        self._constants: list[Optional[tuple[int, Optional[str]]]] = []
        self._sums: OrderedDict[tuple[int, int, float, bool], float] = OrderedDict()
        self._cache_size = max(1, cache_size)

    def prepare(self, values: Iterable[Optional[str]]) -> int:
        # Preserve raw presence: whitespace is present but normalizes to empty.
        # This matches cached_string_similarity's lower/strip, not casefold.
        sequence = tuple(value.lower().strip() if value else None for value in values)
        sequence_id = self._sequence_ids.get(sequence)
        if sequence_id is None:
            sequence_id = len(self._sequences)
            self._sequences.append(sequence)
            self._constants.append((len(sequence), sequence[0])
                                   if sequence and all(value == sequence[0] for value in sequence) else None)
            self._sequence_ids[sequence] = sequence_id
        return sequence_id

    def sum(self, left_id: int, right_id: int, adjustment: float = 1.0, *, include_missing: bool = False) -> float:
        key = (left_id, right_id, adjustment, include_missing)
        cached = self._sums.get(key)
        if cached is not None:
            self._sums.move_to_end(key)
            return cached
        total = 0.0
        constant_left, constant_right = self._constants[left_id], self._constants[right_id]
        if constant_left is not None and constant_right is not None:
            left, right = constant_left[1], constant_right[1]
            if left is None or right is None:
                similarity = 0.0 if include_missing else None
            elif not left or not right:
                similarity = 0.0
            elif left == right:
                similarity = 1.0
            else:
                similarity = fuzz.ratio(left, right) / 100.0
            if similarity is not None:
                term = similarity * adjustment
                for _ in range(min(constant_left[0], constant_right[0])):
                    total += term
        else:
            total = self._sum_tracks(left_id, right_id, adjustment, include_missing)
        self._sums[key] = total
        if len(self._sums) > self._cache_size:
            self._sums.popitem(last=False)
        return total

    def _sum_tracks(self, left_id: int, right_id: int, adjustment: float, include_missing: bool) -> float:
        total = 0.0
        for left, right in zip(self._sequences[left_id], self._sequences[right_id]):
            if left is None or right is None:
                if include_missing:
                    total += 0.0 * adjustment
                continue
            if not left or not right:
                similarity = 0.0
            elif left == right:
                similarity = 1.0
            else:
                similarity = fuzz.ratio(left, right) / 100.0
            # Keep every per-track multiply/add in its original order. Multiplying
            # a final sum would change floating-point rounding at score thresholds.
            total += similarity * adjustment
        return total
