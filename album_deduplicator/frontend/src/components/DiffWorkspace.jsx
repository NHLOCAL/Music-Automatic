import React, { useMemo } from "react";
import { Button, Card, Empty, Progress, Space, Statistic, Table, Typography } from "antd";

import { StatusTag, Icon } from "./UI";
import { ScoreTransparencyPanel } from "./ScoreTransparencyPanel";
import {
  buildTrackComparisonRows,
  formatBitrate,
  formatDuration,
  formatSizeMb,
  getMetricWinners,
} from "../utils";

function MetricTile({ label, value, percent, isWinner = false, color = "#2572ff" }) {
  const normalizedPercent = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0;

  return (
    <Card className="metric-tile cartoon-panel" variant="borderless">
      <Typography.Text type="secondary">{label}</Typography.Text>
      <Typography.Text className="metric-value">{value}</Typography.Text>
      <Progress
        percent={Math.round(normalizedPercent)}
        showInfo={false}
        strokeColor={isWinner ? "#1d9f5f" : color}
        railColor="rgba(37, 114, 255, 0.12)"
      />
    </Card>
  );
}

export function DiffWorkspace({ cluster, currentKeeperId, handleDecision, openExplorer }) {
  if (!cluster) {
    return (
      <Card className="workspace-empty cartoon-card" variant="borderless">
        <Empty
          className="desktop-empty"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="בחר קבוצה מהרשימה להתחיל"
        />
      </Card>
    );
  }

  const visibleAlbums = cluster.albums.filter((album) => !album.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const activeKeeperOrFirst = currentKeeperId || visibleAlbums[0]?.folder_id;
  const selectedDeleteCount = currentKeeperId ? Math.max(visibleAlbums.length - 1, 0) : 0;

  const maxValues = useMemo(() => {
    const maxes = { avg_bitrate: 0, total_size_mb: 0, file_count: 0 };
    visibleAlbums.forEach((album) => {
      maxes.avg_bitrate = Math.max(maxes.avg_bitrate, album.avg_bitrate || 0);
      maxes.total_size_mb = Math.max(maxes.total_size_mb, album.total_size_mb || 0);
      maxes.file_count = Math.max(maxes.file_count, album.file_count || 0);
    });
    return maxes;
  }, [visibleAlbums]);

  const trackColumns = useMemo(() => (
    [
      {
        title: "שיר מקורי",
        key: "reference",
        fixed: "right",
        width: 260,
        render: (_, row) => (
          <div className="track-main-cell">
            <Typography.Text strong>
              <Icon name="music" size={14} /> {row.title}
            </Typography.Text>
            <Typography.Text type="secondary">{row.artist}</Typography.Text>
          </div>
        ),
      },
      ...visibleAlbums.map((album) => ({
        title: album.name,
        key: album.folder_id,
        width: 250,
        render: (_, row) => {
          const entry = row.entries[album.folder_id];
          const referenceEntry = row.entries[activeKeeperOrFirst];

          if (!entry) {
            return (
              <div className="track-missing">
                <Icon name="alert" size={14} /> חסר
              </div>
            );
          }

          const bitrateDifferent = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
          const durationDifferent = referenceEntry && entry.duration !== referenceEntry.duration;

          return (
            <div className="track-entry">
              <span className="track-entry-name">
                <Icon name="music" size={14} />
                {entry.filename}
              </span>
              <div className="track-entry-meta">
                <span className={`track-chip ${bitrateDifferent ? "is-different" : ""}`}>
                  {formatBitrate(entry.bitrate)}
                </span>
                <span className={`track-chip ${durationDifferent ? "is-different" : ""}`}>
                  {formatDuration(entry.duration)}
                </span>
              </div>
            </div>
          );
        },
      })),
    ]
  ), [activeKeeperOrFirst, visibleAlbums]);

  return (
    <div className="diff-shell">
      <Card className="diff-header-card cartoon-card" variant="borderless">
        <div className="diff-header-grid">
          <div>
            <Space wrap size={12}>
              <Typography.Title level={2} style={{ margin: 0 }}>
                {cluster.human_summary}
              </Typography.Title>
              <StatusTag
                tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}
                icon={cluster.confidence_bucket === "safe" ? "shield" : "alert"}
              >
                {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
              </StatusTag>
            </Space>
            <Typography.Paragraph className="muted-copy" style={{ margin: "8px 0 0" }}>
              בחר עותק אחד לשמירה. שאר העותקים יסומנו להעברה לסל המחזור.
            </Typography.Paragraph>
          </div>

          <div className="diff-kpi-row">
            <Card className="diff-kpi-card cartoon-panel" variant="borderless">
              <Statistic title="עותקים" value={visibleAlbums.length} prefix={<Icon name="layers" size={16} />} />
            </Card>
            <Card className="diff-kpi-card cartoon-panel" variant="borderless">
              <Statistic title="שירים" value={trackRows.length} prefix={<Icon name="music" size={16} />} />
            </Card>
            <Card className="diff-kpi-card cartoon-panel" variant="borderless">
              <Statistic title="יסומנו למחיקה" value={selectedDeleteCount} prefix={<Icon name="trash" size={16} />} />
            </Card>
          </div>
        </div>
      </Card>

      <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />

      <section className="workspace-section">
        <div className="section-head">
          <div>
            <div className="soft-kicker">
              <Icon name="compare" size={14} />
              תצוגת השוואה
            </div>
            <Typography.Title level={3} style={{ margin: "10px 0 0" }}>
              עותקי האלבום זה לצד זה
            </Typography.Title>
          </div>
          <StatusTag tone="primary" icon="layers">
            {visibleAlbums.length} עותקים
          </StatusTag>
        </div>

        <div className="comparison-scroller">
          <div
            className="album-grid"
            style={{
              gridTemplateColumns: `repeat(${visibleAlbums.length}, minmax(280px, 1fr))`,
              minWidth: `${visibleAlbums.length * 296}px`,
            }}
          >
            {visibleAlbums.map((album, index) => {
              const isKeeper = currentKeeperId === album.folder_id;
              const isTrash = currentKeeperId && !isKeeper;
              const isRecommended = cluster.recommended_keeper_id === album.folder_id;

              return (
                <Card
                  key={album.folder_id}
                  className={`album-card cartoon-card ${isKeeper ? "is-keeper" : ""} ${isTrash ? "is-deleted" : ""}`}
                  variant="borderless"
                >
                  <div className="album-card-topline">
                    <StatusTag tone={isKeeper ? "success" : isTrash ? "danger" : "neutral"}>
                      עותק {index + 1}
                    </StatusTag>
                    {isRecommended && !isKeeper ? (
                      <StatusTag tone="primary" icon="sparkle">
                        מומלץ
                      </StatusTag>
                    ) : null}
                  </div>

                  <div className="album-actions">
                    <Button
                      type={isKeeper ? "primary" : "default"}
                      danger={Boolean(isTrash)}
                      icon={<Icon name={isKeeper ? "check-circle" : isTrash ? "trash" : "shield"} size={16} />}
                      onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                    >
                      {isKeeper ? "נבחר לשמירה" : isTrash ? "מיועד למחיקה" : "שמור עותק זה"}
                    </Button>
                    <Button
                      icon={<Icon name="folder" size={16} />}
                      title="פתח בתיקייה"
                      aria-label="פתח בתיקייה"
                      onClick={() => openExplorer(album.path)}
                    />
                  </div>

                  <Space orientation="vertical" size={12} style={{ width: "100%" }}>
                    <Space wrap>
                      <Typography.Title level={4} style={{ margin: 0 }}>
                        {album.name}
                      </Typography.Title>
                      {isKeeper ? (
                        <StatusTag tone="success" icon="shield">
                          Keeper
                        </StatusTag>
                      ) : null}
                    </Space>

                    <div className="album-path-box" title={album.path}>{album.path}</div>

                    <div className="album-path-flags">
                      {album.in_preferred_root ? (
                        <StatusTag tone="primary" icon="shield">
                          בתיקייה מועדפת
                        </StatusTag>
                      ) : null}
                      {album.has_album_art ? (
                        <StatusTag tone="neutral" icon="eye">
                          עטיפה זמינה
                        </StatusTag>
                      ) : null}
                    </div>
                  </Space>

                  <div className="album-metrics">
                    <MetricTile
                      label="דירוג איכות"
                      value={album.quality_score ? album.quality_score.toFixed(1) : "N/A"}
                      percent={album.quality_score || 0}
                      isWinner={metricWinners.quality_score === album.folder_id}
                    />
                    <MetricTile
                      label="ביטרייט ממוצע"
                      value={`${Math.round(album.avg_bitrate || 0)} kbps`}
                      percent={maxValues.avg_bitrate ? ((album.avg_bitrate || 0) / maxValues.avg_bitrate) * 100 : 0}
                      isWinner={metricWinners.avg_bitrate === album.folder_id}
                    />
                    <MetricTile
                      label="נפח תיקייה"
                      value={formatSizeMb(album.total_size_mb)}
                      percent={maxValues.total_size_mb ? ((album.total_size_mb || 0) / maxValues.total_size_mb) * 100 : 0}
                      color="#7f8bb3"
                    />
                    <MetricTile
                      label="מספר קבצים"
                      value={album.file_count}
                      percent={maxValues.file_count ? (album.file_count / maxValues.file_count) * 100 : 0}
                      color="#7f8bb3"
                    />
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      <section className="workspace-section">
        <div className="section-head">
          <div>
            <div className="soft-kicker">
              <Icon name="music" size={14} />
              תוצאות שירים
            </div>
            <Typography.Title level={3} style={{ margin: "10px 0 0" }}>
              רשימת השוואה מפורטת
            </Typography.Title>
          </div>
          <StatusTag tone="primary" icon="music">
            {trackRows.length} שורות
          </StatusTag>
        </div>

        <Card className="track-table-card cartoon-card" variant="borderless">
          <Table
            className="tracks-table"
            columns={trackColumns}
            dataSource={trackRows}
            pagination={false}
            rowKey="key"
            scroll={{ x: Math.max(920, visibleAlbums.length * 250 + 260), y: 520 }}
          />
        </Card>
      </section>
    </div>
  );
}
