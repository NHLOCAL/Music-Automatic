"""Build a reproducible metadata benchmark without trusting historical AI labels."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path, PureWindowsPath


TAG_FIELDS = {"title", "artist", "album", "albumartist", "tracknumber", "discnumber",
              "date", "genre", "composer", "version", "compilation", "grouping",
              "totaltracks", "totaldiscs", "originaldate"}
INITIAL_REVIEWS = {
    37: ("duplicate", "All 32 title and duration pairs match after reordering Track08"),
    42: ("duplicate", "Same artist and album; ten translated titles with identical durations"),
    49: ("duplicate", "Eleven renamed and reordered tracks match durations within 0.03 seconds"),
    50: ("duplicate", "Four named tracks match exact durations after reordering"),
    431: ("different", "Only five of eight tracks overlap; each album contains unique tracks"),
    438: ("duplicate", "Six renamed and reordered tracks match durations within 0.01 seconds"),
    440: ("uncertain", "Same titles but all ten durations differ materially; audio or edition review needed"),
}
INITIAL_CACHE_SHA256 = "4831ef36978ccf6f1930de54b93000725543726cc7d2ae5252471e2f11295233"
INITIAL_MUSIC_SHA256 = "675774c55ba78bf8d9d3b504f74be521e7f3f4c55e4f38bffb8363b73fee1a47"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def album_payload(album):
    """Explicit allowlist prevents source paths and arbitrary tags entering requests."""
    tracks = []
    for track in album.get("files", []):
        tags = track.get("all_tags") or {}
        tracks.append({
            "filename": PureWindowsPath(str(track.get("filename", ""))).name,
            **{key: track.get(key) for key in ("title", "artist", "album", "albumartist",
                                                "duration", "bitrate", "size_mb", "extension")},
            "tags": {key: value for key, value in tags.items() if key in TAG_FIELDS},
        })
    return {"folder_name": album.get("folder_name", ""),
            "artist": sorted(album.get("unique_artists") or []),
            "album": sorted(album.get("unique_albums") or []),
            "tracks": tracks}


def compact_input(album1, album2):
    """Factor repeated identity evidence; never truncate tracks or infer a verdict.

    Quality-only bitrate and size are not identity evidence. All track names,
    filenames, durations, identity tags, artists and album/edition metadata remain.
    """
    results = []
    first_rows = []
    for album_index, album in enumerate((album1, album2)):
        tracks = album["tracks"]
        identity = []
        for track in tracks:
            tags = {key: value for key, value in track["tags"].items()
                    if key not in {"title", "artist", "album", "albumartist"}}
            tags.update({key: track[key] for key in ("artist", "album", "albumartist")
                         if track.get(key) not in (None, "")})
            # Parsed fields and raw tags can disagree, including multi-valued tags.
            # Keep raw evidence whenever it cannot be reconstructed from parsed fields.
            for key in ("title", "artist", "album", "albumartist"):
                if key in track["tags"] and track["tags"][key] != track.get(key):
                    tags["raw_" + key] = track["tags"][key]
            identity.append(tags)
        defaults = {}
        if identity:
            for key, value in identity[0].items():
                if all(row.get(key) == value for row in identity): defaults[key] = value
        variable_keys = sorted({key for tags in identity for key in tags if key not in defaults})
        exceptional = {key: [tags.get(key) for tags in identity] for key in variable_keys}
        result = {"folder_name": album["folder_name"], "artists": album["artist"],
                  "albums": album["album"], "track_fields": ["filename", "title", "seconds"],
                  "filename_null_means": "title + .mp3", "tracks": []}
        if defaults: result["track_defaults"] = defaults
        if exceptional: result["track_tag_columns"] = exceptional
        if album_index:
            result["integer_track_means"] = "zero-based album1 track row reference"
        for track in tracks:
            filename = track["filename"]
            if filename == str(track.get("title")) + ".mp3": filename = None
            row = [filename, track.get("title"), track.get("duration")]
            if album_index == 0:
                first_rows.append(row)
                result["tracks"].append(row)
            elif row in first_rows:
                result["tracks"].append(first_rows.index(row))
            else:
                result["tracks"].append(row)
        results.append(result)
    return {"album1": results[0], "album2": results[1]}


def _read_reviews(path):
    if path is None:
        return {index: {"verdict": verdict, "reason": reason,
                        "provenance": "independent_metadata_review", "reviewer": "audit_data"}
                for index, (verdict, reason) in INITIAL_REVIEWS.items()}
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    rows = payload.get("reviews", []) if isinstance(payload, dict) else payload
    result = {}
    for row in rows:
        if row["verdict"] not in {"duplicate", "different", "uncertain"}:
            raise ValueError("Review verdict must be duplicate, different, or uncertain")
        if row.get("provenance") != "independent_metadata_review":
            raise ValueError("Review provenance must identify independent metadata review")
        result[int(row["cache_index"])] = row
    return result


def build_dataset(cache_path, music_path, *, limit=100, reviews_path=None):
    if limit < 1:
        raise ValueError("limit must be positive")
    cache = json.loads(Path(cache_path).read_text(encoding="utf-8-sig"))
    music = json.loads(Path(music_path).read_text(encoding="utf-8-sig"))
    if not isinstance(cache, list) or not isinstance(music, dict):
        raise ValueError("Expected JSON comparison list and metadata object")
    cache_hash, music_hash = digest(cache), digest(music)
    # Built-in review indices are bound to this exact historical snapshot.
    known_snapshot = cache_hash == INITIAL_CACHE_SHA256 and music_hash == INITIAL_MUSIC_SHA256
    bundled_reviews = Path(__file__).with_name("reviews") / "independent_metadata.json"
    if reviews_path is None and known_snapshot and bundled_reviews.exists():
        reviews_path = bundled_reviews
    reviews = _read_reviews(reviews_path) if reviews_path or known_snapshot else {}
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        if parent[key] != key:
            parent[key] = find(parent[key])
        return parent[key]

    linked = []
    album_payloads = {}
    aliases = {}
    for index, row in enumerate(cache):
        a, b = row["folder1_path"], row["folder2_path"]
        if a not in music or b not in music:
            continue
        ra, rb = find(a), find(b)
        parent[max(ra, rb)] = min(ra, rb)
        for key in (a, b):
            if key not in album_payloads:
                album_payloads[key] = album_payload(music[key])
                fingerprint = digest(album_payloads[key])
                if fingerprint in aliases:
                    ra, rb = find(key), find(aliases[fingerprint])
                    parent[max(ra, rb)] = min(ra, rb)
                else:
                    aliases[fingerprint] = key
        linked.append((index, row))
    component_members = defaultdict(list)
    for key in parent:
        component_members[find(key)].append(key)
    group_ids = {key: digest(sorted(members))[:16]
                 for key, members in component_members.items()}
    candidates = []
    seen = set()
    for index, row in linked:
        a, b = row["folder1_path"], row["folder2_path"]
        album1, album2 = album_payloads[a], album_payloads[b]
        identity = sorted([digest(album1), digest(album2)])
        case_id = digest(identity)[:20]
        if case_id in seen:
            continue
        seen.add(case_id)
        review = reviews.get(index)
        scores = row.get("similarity_scores") or {}
        tags = ["real"]
        if len(album1["tracks"]) != len(album2["tracks"]): tags.append("track_count_mismatch")
        if scores.get("title", 1) < .6: tags.append("title_mismatch")
        if scores.get("duration", 1) < .85: tags.append("duration_mismatch")
        if scores.get("artist", 1) < .6: tags.append("artist_mismatch")
        if row.get("gemini_verdict") == "uncertain": tags.append("historically_uncertain")
        if review: tags.extend(review.get("tags", []))
        candidates.append({
            "case_id": case_id, "input": compact_input(album1, album2),
            "label": review["verdict"] if review else None,
            "label_provenance": "independent_metadata_review" if review else "pending_review",
            "review": review, "historical_label": row.get("gemini_verdict"),
            "historical_score": row.get("gemini_similarity_score"),
            "category": "real", "tags": sorted(set(tags)),
            "group_id": group_ids[find(a)],
            "source": {"cache_index": index, "cache_sha256": cache_hash,
                       "music_sha256": music_hash},
        })
    # Reviewed cases first, then balanced round-robin historical strata.
    selected = sorted((x for x in candidates if x["label"] is not None),
                      key=lambda x: x["case_id"])
    strata = defaultdict(list)
    for case in candidates:
        if case["label"] is None:
            strata[str(case["historical_label"])].append(case)
    for bucket in strata.values(): bucket.sort(key=lambda x: x["case_id"])
    while len(selected) < limit and any(strata.values()):
        for name in sorted(strata):
            if strata[name] and len(selected) < limit: selected.append(strata[name].pop(0))
    selected = selected[:limit]
    # Assign connected album families together. Paths remain internal only.
    groups = sorted({case["group_id"] for case in selected})
    split = {group: ("calibration" if index % 2 == 0 else "test")
             for index, group in enumerate(groups)}
    for case in selected: case["split"] = split[case["group_id"]]
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--music", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args(argv)
    cases = build_dataset(args.cache, args.music, limit=args.limit, reviews_path=args.reviews)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n"
                                   for x in cases), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "reviewed": sum(x["label"] is not None for x in cases),
                      "pending_review": sum(x["label"] is None for x in cases),
                      "label_provenance": "independent_metadata_review, not user_verified"}))


if __name__ == "__main__":
    main()
