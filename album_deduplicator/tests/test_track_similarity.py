from music_dup_lib.core.track_similarity import StringSequenceComparer
from music_dup_lib.utils import cached_string_similarity


def test_sequences_reuse_the_exact_ordered_sum(monkeypatch):
    from music_dup_lib.core import track_similarity as module

    first = [" Artist ", None, "", " ", "אמן", "A", "B"]
    second = ["artist", "X", None, " ", "אומן", "B", "A"]
    expected = 0.0
    for left, right in zip(first, second):
        if left and right:
            expected += cached_string_similarity(left, right) * 0.55
    comparer = StringSequenceComparer(cache_size=2)
    left, right = comparer.prepare(first), comparer.prepare(second)
    assert comparer.sum(left, right, 0.55) == expected

    def no_recalculation(*args):
        raise AssertionError("An identical sequence comparison should be reused")

    monkeypatch.setattr(module.fuzz, "ratio", no_recalculation)
    assert comparer.sum(left, right, 0.55) == expected


def test_case_normalization_and_missing_values_keep_original_semantics():
    import math

    comparer = StringSequenceComparer()
    assert comparer.prepare(["ABC", " Straße "]) == comparer.prepare([" abc ", "straße"])
    assert comparer.prepare(["ß"]) != comparer.prepare(["ss"])  # lower, not casefold
    missing = comparer.prepare([None, ""])
    spaces = comparer.prepare([" ", "\t"])
    assert comparer.sum(missing, missing, math.inf) == 0.0
    assert math.isnan(comparer.sum(spaces, spaces, math.inf))
    assert math.isnan(comparer.sum(missing, missing, math.inf, include_missing=True))


def test_sequence_cache_eviction_preserves_recomputed_scores():
    comparer = StringSequenceComparer(cache_size=2)
    vectors = [comparer.prepare([text]) for text in ("alpha", "beta", "gamma")]
    expected = comparer.sum(vectors[0], vectors[1])
    comparer.sum(vectors[0], vectors[2])
    comparer.sum(vectors[1], vectors[2])
    assert len(comparer._sums) == 2
    assert comparer.sum(vectors[0], vectors[1]) == expected


def test_constant_track_metadata_computes_similarity_only_once(monkeypatch):
    from music_dup_lib.core import track_similarity as module

    original = module.fuzz.ratio
    expected = 0.0
    for _ in range(12):
        expected += original("first artist", "second artist") / 100.0
    calls = []

    def counted_ratio(first, second):
        calls.append(1)
        return original(first, second)

    monkeypatch.setattr(module.fuzz, "ratio", counted_ratio)
    comparer = StringSequenceComparer()
    assert comparer.sum(comparer.prepare(["first artist"] * 12),
                        comparer.prepare(["second artist"] * 12)) == expected
    assert len(calls) == 1


def test_random_sequence_sums_match_original_float_bits():
    import itertools
    import random

    rng = random.Random(42)
    values = [None, "", " ", "ABC", " abc ", "Straße", "STRASSE", "אמן", "אומן", "ΟΣ", "🙂"]
    sequences = [[rng.choice(values) for _ in range(rng.randrange(13))] for _ in range(32)]
    comparer = StringSequenceComparer(cache_size=16)
    ids = [comparer.prepare(sequence) for sequence in sequences]
    for left, right in itertools.product(range(32), repeat=2):
        for adjustment, include_missing in itertools.product((0.0, 0.55, 1.0), (False, True)):
            expected = 0.0
            for first, second in zip(sequences[left], sequences[right]):
                if include_missing or (first and second):
                    expected += cached_string_similarity(first, second) * adjustment
            actual = comparer.sum(ids[left], ids[right], adjustment, include_missing=include_missing)
            assert actual.hex() == expected.hex()
    assert len(comparer._sums) <= 16
