import React, { useEffect, useMemo, useRef, useState } from "react";
import { Button, Image, Popconfirm, Tooltip } from "antd";

import { buildApiUrl } from "../api";
import { buildTrackComparisonRows, formatBitrate, formatDuration, formatSizeMb, getTrackRowTone } from "../utils";
import { Icon, StatusTag } from "./UI";
import { ScoreTransparencyPanel } from "./ScoreTransparencyPanel";

function AlbumArtPreview({ album }) {
  if (album.album_art_preview_url) {
    return (
      <Image
        className="ide-album-cover-image"
        src={buildApiUrl(album.album_art_preview_url)}
        alt={`עטיפת ${album.name}`}
        width={72}
        height={72}
      />
    );
  }

  return (
    <div className="ide-album-cover-fallback" aria-label="אין עטיפה זמינה">
      <Icon name="music" size={18} />
      <span>אין עטיפה</span>
    </div>
  );
}

function AudioPreviewCard({ audioPreview, onDismiss, onPlaybackStateChange }) {
  const audioRef = useRef(null);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const handledToggleRef = useRef(0);

  useEffect(() => {
    setDuration(0);
    setCurrentTime(0);
    setIsPlaying(Boolean(audioPreview));
    handledToggleRef.current = audioPreview?.toggleRequest ?? 0;
  }, [audioPreview?.key]);

  useEffect(() => {
    onPlaybackStateChange?.(isPlaying);
  }, [isPlaying, onPlaybackStateChange]);

  const audioSource = buildApiUrl(audioPreview?.streamUrl);

  const togglePlayback = async () => {
    if (!audioRef.current) return;
    if (!isPlaying) {
      try {
        await audioRef.current.play();
      } catch {
        setIsPlaying(false);
      }
      return;
    }
    audioRef.current.pause();
  };

  const handleSeek = (event) => {
    const nextTime = Number(event.target.value);
    setCurrentTime(nextTime);
    if (audioRef.current) audioRef.current.currentTime = nextTime;
  };

  useEffect(() => {
    if (!audioRef.current) return;
    const nextToggleRequest = audioPreview?.toggleRequest ?? 0;
    if (nextToggleRequest === 0 || nextToggleRequest === handledToggleRef.current) return;
    handledToggleRef.current = nextToggleRequest;
    togglePlayback();
  }, [audioPreview?.toggleRequest]);

  if (!audioPreview) return null;

  return (
    <div className="ide-audio-preview" data-testid="audio-preview-card">
      <audio
        ref={audioRef}
        autoPlay
        key={audioSource}
        src={audioSource}
        onLoadedMetadata={(event) => {
          const nextDuration = event.currentTarget.duration;
          setDuration(Number.isFinite(nextDuration) ? nextDuration : 0);
        }}
        onTimeUpdate={(event) => {
          const nextCurrentTime = event.currentTarget.currentTime;
          setCurrentTime(Number.isFinite(nextCurrentTime) ? nextCurrentTime : 0);
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => {
          setIsPlaying(false);
          onDismiss();
        }}
      />
      <div className="ide-audio-preview-copy">
        <div className="ide-audio-preview-head">
          <strong>השמעת השוואה</strong>
          <StatusTag tone={isPlaying ? "primary" : "neutral"}>{isPlaying ? "מנגן" : "מושהה"}</StatusTag>
        </div>
        <div className="ide-audio-preview-track">{audioPreview.trackTitle}</div>
        <div className="ide-audio-preview-path" title={audioPreview.filePath}>
          {audioPreview.filePath}
        </div>
      </div>
      <div className="ide-audio-preview-controls">
        <Button
          size="small"
          type="text"
          className="ide-audio-toggle-button"
          icon={<Icon name={isPlaying ? "pause" : "play"} size={15} />}
          onClick={togglePlayback}
          aria-label={isPlaying ? `השהה את ${audioPreview.trackTitle}` : `נגן את ${audioPreview.trackTitle}`}
        />
        <input
          className="ide-audio-range"
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={Math.min(currentTime, duration || 0)}
          onChange={handleSeek}
          aria-label={`ציר הזמן של ${audioPreview.trackTitle}`}
        />
        <span className="ide-audio-time">{formatDuration(duration)}</span>
        <Button size="small" type="text" onClick={onDismiss} aria-label="סגור את נגן ההשוואה">
          סגור
        </Button>
      </div>
    </div>
  );
}

export function DiffWorkspace({
  cluster,
  currentKeeperId,
  handleDecision,
  openExplorer,
  previewCount,
  onOpenFinalize,
  onExecuteMassDelete,
  isExecuting,
}) {
  const [audioPreview, setAudioPreview] = useState(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);

  useEffect(() => {
    setAudioPreview(null);
    setIsAudioPlaying(false);
  }, [cluster?.cluster_id, currentKeeperId]);

  if (!cluster) {
    return (
      <div className="ide-main" data-testid="diff-shell" style={{ alignItems: "center", justifyContent: "center", color: "#888" }}>
        בחר קבוצה מהרשימה
      </div>
    );
  }

  const visibleAlbums = useMemo(() => cluster.albums.filter((album) => !album.is_deleted), [cluster]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const visibleAlbumIds = useMemo(() => visibleAlbums.map((album) => album.folder_id), [visibleAlbums]);
  const keeperAlbum = visibleAlbums.find((album) => album.folder_id === currentKeeperId) ?? null;
  const deleteCount = currentKeeperId ? Math.max(visibleAlbums.length - 1, 0) : 0;

  const handleTrackPreview = (album, entry) => {
    if (!entry?.stream_url) return;
    const nextKey = `${album.folder_id}:${entry.track_index ?? entry.filename}`;
    setAudioPreview((current) => {
      if (current?.key === nextKey) {
        return {
          ...current,
          toggleRequest: (current.toggleRequest ?? 0) + 1,
        };
      }
      return {
        key: nextKey,
        trackTitle: entry.title || entry.filename,
        filePath: entry.filepath || album.path,
        streamUrl: entry.stream_url,
        toggleRequest: 0,
      };
    });
  };

  return (
    <div className="ide-main ide-diff-shell" data-testid="diff-shell">
      <div className="ide-toolbar">
        <div className="ide-toolbar-main">
          <span className={`badge ${cluster.confidence_bucket === "safe" ? "success" : "warning"}`}>
            {cluster.confidence_bucket === "safe" ? "בטוח" : "לסקירה"}
          </span>
          <span className="ide-toolbar-summary">{cluster.human_summary}</span>
          <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />
        </div>
        <div className="ide-toolbar-actions">
          <StatusTag tone={keeperAlbum ? "success" : "neutral"}>
            נשמר: {keeperAlbum ? keeperAlbum.name : "לא נבחר"}
          </StatusTag>
          <StatusTag tone={deleteCount > 0 ? "warning" : "neutral"}>למחיקה: {deleteCount}</StatusTag>
          {previewCount > 0 ? (
            <>
              <Button size="small" onClick={onOpenFinalize}>עבור לשלב ההעברה</Button>
              <Popconfirm
                title="להעביר את כל הפריטים המסומנים לסל המחזור?"
                description="אפשר עדיין לעבור למסך ההעברה לפני ביצוע."
                okText="כן, להעביר"
                cancelText="ביטול"
                onConfirm={onExecuteMassDelete}
              >
                <Button size="small" type="primary" danger loading={isExecuting}>
                  העבר למחזור ({previewCount})
                </Button>
              </Popconfirm>
            </>
          ) : null}
        </div>
      </div>

      <div className={`ide-review-scroll-shell ${audioPreview ? "has-audio-preview" : ""}`} data-testid="review-scroll-shell">
        <div className="ide-diff-container" data-testid="comparison-scroller">
        {visibleAlbums.map((album, index) => {
          const isKeeper = currentKeeperId === album.folder_id;
          const isTrash = Boolean(currentKeeperId) && !isKeeper;

          return (
            <div key={album.folder_id} className={`ide-pane ${isKeeper ? "is-keeper" : isTrash ? "is-trash" : ""}`}>
              <div className="ide-pane-header">
                <div className="ide-pane-topline">
                  <strong style={{ fontSize: 13 }}>
                    {album.name || `עותק ${index + 1}`}
                  </strong>
                  <div className="ide-pane-topline-actions">
                    {cluster.recommended_keeper_id === album.folder_id ? <StatusTag tone="primary">מומלץ</StatusTag> : null}
                    <Tooltip title="פתח בתיקייה">
                      <Button
                        type="text"
                        size="small"
                        icon={<Icon name="folder" size={14} />}
                        onClick={() => openExplorer(album.path)}
                        aria-label={`פתח את ${album.name || `עותק ${index + 1}`}`}
                      />
                    </Tooltip>
                  </div>
                </div>

                <div className="ide-pane-media">
                  <AlbumArtPreview album={album} />
                  <div className="ide-pane-meta">
                    <div className="ide-pane-copy-index">עותק {index + 1}</div>
                    <div className="ide-pane-path" title={album.path}>{album.path}</div>
                    <div className="ide-pane-metrics">
                      <span>ביטרייט: <strong>{formatBitrate(album.avg_bitrate)}</strong></span>
                      <span>גודל: <strong>{formatSizeMb(album.total_size_mb)}</strong></span>
                      <span>איכות: <strong>{album.quality_score ? `${album.quality_score.toFixed(1)}/100` : "-"}</strong></span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="ide-pane-body">
                {trackRows.map((row) => {
                  const entry = row.entries[album.folder_id];
                  const tone = getTrackRowTone(row, visibleAlbumIds);
                  const isDiff = tone === "different";

                  if (!entry) {
                    return <div key={row.key} className="ide-track-row diff-err">חסר בעותק זה</div>;
                  }

                  const isActivePreview = audioPreview?.key === `${album.folder_id}:${entry.track_index ?? entry.filename}`;
                  const isPlaying = isActivePreview && isAudioPlaying;

                  return (
                    <div key={row.key} className={`ide-track-row ${isDiff ? "diff-warn" : ""}`}>
                      <div className="ide-track-copy">
                        <span className="ide-track-name" title={entry.filename}>{entry.filename}</span>
                        <span className="ide-track-duration">{formatDuration(entry.duration)}</span>
                      </div>
                      <Button
                        size="small"
                        type="text"
                        className={`ide-track-play-button ${isPlaying ? "is-playing" : ""}`}
                        icon={<Icon name={isPlaying ? "pause" : "play"} size={15} />}
                        onClick={() => handleTrackPreview(album, entry)}
                        disabled={!entry.stream_url}
                        aria-label={`${isPlaying ? "השהה" : "נגן"} את ${entry.filename}`}
                      />
                    </div>
                  );
                })}
              </div>

              <div className="ide-pane-footer">
                <Button
                  type={isKeeper ? "primary" : "default"}
                  danger={isTrash}
                  style={{ width: "100%" }}
                  onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                >
                  {isKeeper ? "נבחר לשמירה (Keeper)" : isTrash ? "יסומן למחיקה (Trash)" : "שמור עותק זה"}
                </Button>
              </div>
            </div>
          );
        })}
        </div>
      </div>

      {audioPreview ? (
        <AudioPreviewCard
          audioPreview={audioPreview}
          onDismiss={() => {
            setAudioPreview(null);
            setIsAudioPlaying(false);
          }}
          onPlaybackStateChange={setIsAudioPlaying}
        />
      ) : null}
    </div>
  );
}
