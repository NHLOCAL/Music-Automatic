from pathlib import Path

from music_dup_lib.core.quality_analyzer import QualityAnalyzer
from music_dup_lib.models import FileInfo, FolderInfo


def make_quality_folder(path_str: str, artist: str, album: str) -> FolderInfo:
    path = Path(path_str)
    files = [
        FileInfo(
            filename=f"song-{index}.flac",
            filepath=path / f"song-{index}.flac",
            extension=".flac",
            size_mb=20.0,
            duration=180.0,
            bitrate=320,
            title=f"Song {index}",
            artist=artist,
            album=album,
            albumartist=artist,
            metadata_complete=True,
            has_lyrics=True,
            is_lossless=True,
        )
        for index in range(3)
    ]
    return FolderInfo(
        path=path,
        folder_name=path.name,
        parent_folder_name=path.parent.name,
        files=files,
        album_art_hash="cover-hash",
        avg_bitrate=320.0,
        unique_artists={artist},
        unique_albums={album},
        generic_filename_score=0.0,
        generic_title_score=0.0,
        hebrew_metadata_ratio=1.0,
        metadata_completeness_ratio=1.0,
        lossless_ratio=1.0,
        lyrics_ratio=1.0,
    )


def test_unknown_artist_and_album_metadata_reduces_quality_score():
    analyzer = QualityAnalyzer(preferred_bitrate="high")
    known_folder = make_quality_folder("C:/music/known", "Known Artist", "Known Album")
    unknown_folder = make_quality_folder("C:/music/unknown", "Unknown Artist", "Unknown Album")

    known_score, known_breakdown = analyzer.calculate_quality(known_folder)
    unknown_score, unknown_breakdown = analyzer.calculate_quality(unknown_folder)

    assert known_score == 100.0
    assert unknown_score < known_score
    assert unknown_breakdown["known_metadata_values"] == 0.0
    assert unknown_breakdown["consistent_artist"] == 0.0
    assert unknown_breakdown["consistent_album"] == 0.0
    assert known_breakdown["known_metadata_values"] == 100.0


def test_hebrew_unknown_artist_and_album_metadata_reduces_quality_score():
    analyzer = QualityAnalyzer(preferred_bitrate="high")
    unknown_folder = make_quality_folder("C:/music/hebrew-unknown", "אמן לא ידוע", "אלבום לא ידוע")

    _, breakdown = analyzer.calculate_quality(unknown_folder)

    assert breakdown["known_metadata_values"] == 0.0
    assert breakdown["consistent_artist"] == 0.0
    assert breakdown["consistent_album"] == 0.0
