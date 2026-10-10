"""Small controlled rule fixtures, reported separately from reviewed real data.

These are authored examples of the existing rules, not observed library pairs or
user decisions. Their labels must never be included in real-data rankings.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path


RULES = {
    "same_content": "Same artist, album, and content; minor tag/format variations are okay",
    "distinct_release": "Distinct albums, different editions (Deluxe/Live/Studio), or different volumes",
    "insufficient": "Ambiguous, conflicting data, or insufficient metadata",
}


def album(name="Harbor", artist="Mira", *, songs=None, extension="mp3", edition=None,
          disc=None, volume=None):
    """Every filename, title and duration stays visible, including missing values."""
    if songs is None:
        songs = [("Dawn", 180), ("River", 210), ("Home", 240)]
    result = {
        "folder_name": name or "Unknown",
        "artists": [] if artist is None else [artist],
        "albums": [] if name is None else [name],
        "track_fields": ["filename", "title", "seconds"],
        "tracks": [[f"{i:02d}-{title or 'Track'}.{extension}", title, seconds]
                   for i, (title, seconds) in enumerate(songs, 1)],
    }
    if edition is not None:
        result["edition"] = edition
    if disc is not None:
        result["discnumber"] = disc
    if volume is not None:
        result["volume"] = volume
    return result


def build_challenges():
    rows = []

    def add(slug, verdict, tags, a, b, rule, evidence):
        rows.append({
            "case_id": "synthetic-" + slug, "category": "synthetic",
            "split": "test", "group_id": "synthetic-" + slug,
            "input": {"album1": deepcopy(a), "album2": deepcopy(b)},
            "label": verdict, "label_provenance": "synthetic_rule_fixture",
            "tags": ["synthetic", *tags],
            "review": {"verdict": verdict, "provenance": "synthetic_rule_fixture",
                       "reviewer": "controlled_fixture_author",
                       "reference_rule": RULES[rule], "reason": evidence},
            "source": {"kind": "authored_controlled_challenge", "fixture_version": 1},
        })

    base = album()
    add("exact", "duplicate", ["exact_duplicate"], base, base, "same_content",
        "Artist, album, all three titles and durations are identical")
    reordered = album(songs=[("Home", 240), ("Dawn", 180), ("River", 210)])
    add("reordered", "duplicate", ["reordered_tracks"], base, reordered, "same_content",
        "All three recordings are represented by equal titles and durations, reordered")
    add("format", "duplicate", ["format_variation"], base, album(extension="flac"),
        "same_content", "Only filename extensions change; all identity and track content agrees")
    renamed = deepcopy(base)
    renamed["folder_name"] = "Mira - Harbor copy"
    renamed["tracks"] = [[f"song{i}.mp3", row[1], row[2]]
                         for i, row in enumerate(base["tracks"], 1)]
    add("filenames", "duplicate", ["filename_variation"], base, renamed, "same_content",
        "Descriptive metadata and every duration agree despite filename and folder changes")
    spelling = album(artist=" Mira ")
    add("whitespace", "duplicate", ["minor_tag_variation"], base, spelling, "same_content",
        "Artist whitespace is a minor tag difference with identical album and track content")
    add("deluxe", "different", ["edition_standard_deluxe"], album(edition="Standard"),
        album(edition="Deluxe"), "distinct_release",
        "Explicit Standard versus Deluxe editions are different under the existing edition rule even with shared songs")
    add("live-studio", "different", ["edition_live_studio"], album(edition="Studio"),
        album(edition="Live"), "distinct_release",
        "Explicit Live and Studio editions are different even when song titles coincide")
    add("volumes", "different", ["different_volumes"], album(volume=1), album(volume=2),
        "distinct_release", "Same series name with explicit different volume numbers")
    other = [("Night", 170), ("Road", 205), ("Sky", 260)]
    add("set-discs", "different", ["same_named_set", "different_discs"], album(disc=1),
        album(disc=2, songs=other), "distinct_release",
        "Same named set, different disc identifiers and wholly different contents")
    add("missing-subset", "different", ["missing_tracks", "subset"], base,
        album(songs=[("Dawn", 180), ("River", 210)]), "same_content",
        "A complete three-track input and a two-track subset do not have the same content; this interprets the same-content requirement")
    add("extra-track", "different", ["extra_track"], base,
        album(songs=[("Dawn", 180), ("River", 210), ("Home", 240), ("Bonus", 120)]),
        "same_content", "One input contains a fourth unique recording; complete contents differ")
    add("missing-identity", "uncertain", ["missing_metadata", "insufficient_identity"],
        album(None, None, songs=[(None, None), (None, None)]),
        album(None, None, songs=[(None, None), (None, None)]), "insufficient",
        "No artist, album, real title or duration exists; matching generic filenames do not establish identity")
    add("corrupt-identity", "uncertain", ["corrupt_metadata", "insufficient_identity"],
        album("Unknown", "artist", songs=[("Track 1", 180), ("Track 2", 210)]),
        album("???", "???", songs=[("Track 1", 180), ("Track 2", 210)]), "insufficient",
        "Placeholder and corrupted identities plus generic titles cannot identify a release")
    add("generic-name-disjoint", "different", ["generic_album_name", "disjoint_content"],
        album("Collection"), album("Collection", songs=other), "distinct_release",
        "Same generic album name and artist cannot override completely different song contents")
    add("same-songs-durations", "uncertain", ["same_titles", "duration_conflict"], base,
        album(songs=[("Dawn", 230), ("River", 165), ("Home", 310)]), "insufficient",
        "All titles and album identities agree but durations conflict materially; edition or corrupted timing is unresolved")
    add("artist-conflict", "uncertain", ["artist_conflict"], base, album(artist="Nolan"),
        "insufficient", "Identical album and track titles/durations conflict with different artist identities")
    add("distinct-albums", "different", ["same_artist", "distinct_albums"], base,
        album("Skyline", songs=other), "distinct_release",
        "Same artist released differently named albums with different song contents")
    partial = album(songs=[("Dawn", 180), ("Road", 205), ("Sky", 260)])
    add("partial-overlap", "different", ["partial_overlap", "mixed_compilation"], base,
        partial, "same_content", "One shared recording does not make two three-track collections with two unique recordings each the same content")
    return rows


def write_challenges(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = build_challenges()
    output.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                              for row in rows), encoding="utf-8")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    rows = write_challenges(args.output)
    print(f"Wrote {len(rows)} synthetic rule fixtures to {args.output}; report separately from real data")


if __name__ == "__main__":
    main()
