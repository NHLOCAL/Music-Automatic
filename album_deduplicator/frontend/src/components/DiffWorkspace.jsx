import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Empty, Flex, Progress, Segmented, Space, Table, Tag, Tooltip, Typography } from "antd";
import { StatusTag, Icon } from "./UI";
import { ScoreTransparencyPanel } from "./ScoreTransparencyPanel";
import {
  buildTrackComparisonRows,
  findClusterPair,
  formatBitrate,
  formatDuration,
  formatPercent,
  formatSizeMb,
  getMetricWinners,
  getTrackRowTone,
} from "../utils";

function MetricTile({ label, value, percent, isWinner = false, color = "#2572ff" }) {
  const normalizedPercent = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0;
  return (
    <Card className="metric-tile cartoon-panel" variant="borderless">
      <Typography.Text type="secondary" style={{ fontSize: "10px" }}>{label}</Typography.Text>
      <Typography.Text className="metric-value">{value}</Typography.Text>
      {percent > 0 && (
        <Progress
          percent={Math.round(normalizedPercent)}
          showInfo={false}
          strokeColor={isWinner ? "#1d9f5f" : color}
          railColor="rgba(37, 114, 255, 0.08)"
          size={["100%", 3]}
          style={{ margin: "2px 0 0" }}
        />
      )}
    </Card>
  );
}

function CompactDecisionItem({ label, value, tone, icon }) {
  return (
    <div className={`compact-decision-item tone-${tone}`}>
      <Icon name={icon} size={12} />
      <span className="decision-label">{label}:</span>
      <span className="decision-value" title={value}>{value}</span>
    </div>
  );
}

function getAlbumRibbon(album, currentKeeperId, recommendedKeeperId) {
  if (currentKeeperId === album.folder_id) return { color: "#1d9f5f", text: "נשמר" };
  if (currentKeeperId && currentKeeperId !== album.folder_id) return { color: "#ef5350", text: "למחיקה" };
  if (recommendedKeeperId === album.folder_id) return { color: "#2572ff", text: "המלצה" };
  return null;
}

export function DiffWorkspace({ cluster, currentKeeperId, handleDecision, openExplorer }) {
  const [comparisonTarget, setComparisonTarget] = useState("auto");

  useEffect(() => {
    setComparisonTarget("auto");
  }, [cluster?.cluster_id, currentKeeperId]);

  const visibleAlbums = useMemo(() => cluster?.albums?.filter((album) => !album.is_deleted) ?? [], [cluster]);
  const visibleAlbumIds = useMemo(() => visibleAlbums.map((album) => album.folder_id), [visibleAlbums]);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);

  const defaultComparisonId = currentKeeperId ?? cluster?.recommended_keeper_id ?? visibleAlbums[0]?.folder_id ?? null;
  const activeComparisonId = comparisonTarget === "auto" ? defaultComparisonId : comparisonTarget;
  const selectedDeleteCount = currentKeeperId ? Math.max(visibleAlbums.length - 1, 0) : 0;

  const activeComparisonAlbum = useMemo(() => visibleAlbums.find((album) => album.folder_id === activeComparisonId) ?? null, [activeComparisonId, visibleAlbums]);
  const activeComparisonIndex = useMemo(() => visibleAlbums.findIndex((album) => album.folder_id === activeComparisonId), [activeComparisonId, visibleAlbums]);
  const explicitKeeperAlbum = useMemo(() => visibleAlbums.find((album) => album.folder_id === currentKeeperId) ?? null, [currentKeeperId, visibleAlbums]);
  const recommendedAlbum = useMemo(() => visibleAlbums.find((album) => album.folder_id === cluster?.recommended_keeper_id) ?? null, [cluster?.recommended_keeper_id, visibleAlbums]);

  const comparisonOptions = useMemo(() => [
    { label: "אוטומטי", value: "auto" },
    ...visibleAlbums.map((album, index) => ({ label: `עותק ${index + 1}`, value: album.folder_id })),
  ], [visibleAlbums]);

  const maxValues = useMemo(() => {
    const maxes = { avg_bitrate: 0, total_size_mb: 0, file_count: 0, quality_score: 0 };
    visibleAlbums.forEach((album) => {
      maxes.avg_bitrate = Math.max(maxes.avg_bitrate, album.avg_bitrate || 0);
      maxes.total_size_mb = Math.max(maxes.total_size_mb, album.total_size_mb || 0);
      maxes.file_count = Math.max(maxes.file_count, album.file_count || 0);
      maxes.quality_score = Math.max(maxes.quality_score, album.quality_score || 0);
    });
    return maxes;
  }, [visibleAlbums]);

  const trackSummary = useMemo(() => {
    let differentRows = 0;
    trackRows.forEach((row) => {
      if (getTrackRowTone(row, visibleAlbumIds) === "different") differentRows += 1;
    });
    return { differentRows };
  }, [trackRows, visibleAlbumIds]);

  const overviewMetrics = useMemo(() => [
    { key: "albums", title: "עותקים", value: visibleAlbums.length },
    { key: "tracks", title: "שירים להשוואה", value: trackRows.length },
    { key: "different", title: "שורות שונות", value: trackSummary.differentRows },
  ], [trackRows.length, trackSummary.differentRows, visibleAlbums.length]);

  const trackColumns = useMemo(() => [
    {
      title: "שיר מקורי",
      key: "reference",
      fixed: "left",
      width: 200,
      render: (_, row) => (
        <div className="track-main-cell">
          <Typography.Text strong ellipsis={{ tooltip: row.title }}>
            <Icon name="music" size={10} style={{ marginInlineEnd: 4 }} />{row.title}
          </Typography.Text>
          <div style={{ display: "flex", gap: "6px", fontSize: "10px", color: "var(--text-secondary)" }}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.artist}</span>
            <span>•</span>
            <span>{formatDuration(row.duration)}</span>
          </div>
        </div>
      ),
    },
    ...visibleAlbums.map((album) => {
      const pairToActive = activeComparisonId && album.folder_id !== activeComparisonId ? findClusterPair(cluster, activeComparisonId, album.folder_id) : null;
      return {
        title: (
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
            <Typography.Text strong ellipsis={{ tooltip: album.name }}>{album.name}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: "10px", fontWeight: "normal" }}>
              {album.folder_id === activeComparisonId ? "בסיס השוואה" : pairToActive?.is_identical_by_hash ? "Hash זהה" : pairToActive ? formatPercent(pairToActive.final_score) : "ללא התאמה"}
            </Typography.Text>
          </div>
        ),
        key: album.folder_id,
        width: 180,
        render: (_, row) => {
          const entry = row.entries[album.folder_id];
          const referenceEntry = activeComparisonId ? row.entries[activeComparisonId] : null;
          if (!entry) {
            return <div style={{ color: "var(--colorError)", fontSize: "11px", fontWeight: "600" }}><Icon name="alert" size={10} style={{ marginInlineEnd: 4 }} /> חסר</div>;
          }
          const bitrateDifferent = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
          const durationDifferent = referenceEntry && Math.round(entry.duration || 0) !== Math.round(referenceEntry.duration || 0);
          const sizeDifferent = referenceEntry && Number(entry.size_mb || 0).toFixed(2) !== Number(referenceEntry.size_mb || 0).toFixed(2);
          return (
            <div className="track-entry">
              <Typography.Text ellipsis={{ tooltip: entry.filename }} style={{ fontWeight: 500, fontSize: "11px" }}>{entry.filename}</Typography.Text>
              <div className="track-entry-meta">
                <span className={`track-chip ${bitrateDifferent ? "is-different" : ""}`}>{formatBitrate(entry.bitrate)}</span>
                <span className={`track-chip ${durationDifferent ? "is-different" : ""}`}>{formatDuration(entry.duration)}</span>
                <span className={`track-chip ${sizeDifferent ? "is-different" : ""}`}>{formatSizeMb(entry.size_mb)}</span>
              </div>
            </div>
          );
        },
      };
    }),
  ], [activeComparisonId, cluster, visibleAlbums]);

  if (!cluster) {
    return (
      <Card className="workspace-empty cartoon-card" variant="borderless">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="בחר קבוצה מהרשימה להתחיל" />
      </Card>
    );
  }

  return (
    <div className="diff-shell" data-testid="diff-shell">
      <div className="diff-compact-header">
        <div className="diff-header-top">
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <Space align="center" size={8}>
              <StatusTag tone={cluster.confidence_bucket === "safe" ? "success" : "warning"} icon={cluster.confidence_bucket === "safe" ? "shield" : "alert"} style={{ minHeight: "22px", fontSize: "11px" }}>
                {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
              </StatusTag>
              {currentKeeperId && <StatusTag tone="success" icon="check-circle" style={{ minHeight: "22px", fontSize: "11px" }}>נבחר keeper</StatusTag>}
            </Space>
            <Typography.Title level={2} className="diff-header-title">{cluster.human_summary}</Typography.Title>
          </div>
          <div className="diff-kpi-row">
            {overviewMetrics.map((metric) => (
              <div key={metric.key} className="diff-kpi-item">
                <span className="diff-kpi-label">{metric.title}</span>
                <span className="diff-kpi-value">{metric.value}</span>
              </div>
            ))}
            <div className="diff-kpi-item" style={{ borderRight: "1px solid var(--border-subtle)", paddingRight: "16px", marginRight: "4px" }}>
               <span className="diff-kpi-label" style={{ color: "var(--color-danger)" }}>לסל המחזור</span>
               <span className="diff-kpi-value" style={{ color: "var(--color-danger)" }}>{selectedDeleteCount}</span>
            </div>
          </div>
        </div>
        <div className="decision-strip">
          <CompactDecisionItem
            icon="shield"
            label="נשמר כעת"
            tone={explicitKeeperAlbum ? "success" : "neutral"}
            value={explicitKeeperAlbum ? explicitKeeperAlbum.path : "לא נבחר"}
          />
          <CompactDecisionItem
            icon="sparkle"
            label="המלצה"
            tone={recommendedAlbum ? "primary" : "neutral"}
            value={recommendedAlbum ? recommendedAlbum.path : "אין"}
          />
          <CompactDecisionItem
            icon="compare"
            label="בסיס השוואה"
            tone={comparisonTarget === "auto" ? "primary" : "warning"}
            value={activeComparisonAlbum ? `עותק ${activeComparisonIndex + 1}` : "אין"}
          />
        </div>
        <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />
      </div>

      <section className="workspace-section">
        <div className="comparison-scroller" data-testid="comparison-scroller">
          {visibleAlbums.map((album, index) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isTrash = Boolean(currentKeeperId) && !isKeeper;
            const ribbon = getAlbumRibbon(album, currentKeeperId, cluster.recommended_keeper_id);
            const card = (
              <Card className={`album-card cartoon-panel ${isKeeper ? "is-keeper" : ""} ${isTrash ? "is-deleted" : ""}`} variant="borderless">
                <Flex justify="space-between" align="center">
                  <StatusTag tone={isKeeper ? "success" : isTrash ? "danger" : "neutral"} style={{ margin: 0, fontSize: "11px", minHeight: "20px" }}>
                    עותק {index + 1}
                  </StatusTag>
                  {album.in_preferred_root && <Icon name="sparkle" size={12} style={{ color: "var(--colorPrimary)" }} title="בתיקייה מועדפת" />}
                </Flex>
                <div>
                  <Typography.Title level={4} className="album-card-title" ellipsis={{ tooltip: album.name }}>{album.name}</Typography.Title>
                  <div className="album-path-inline" style={{ marginTop: "4px" }}>
                    <Icon name="folder" size={10} style={{ color: "var(--text-tertiary)" }} />
                    <Typography.Text className="album-inline-path" ellipsis={{ tooltip: album.path }}>{album.path}</Typography.Text>
                  </div>
                </div>
                <div className="album-actions">
                  <Button type={isKeeper ? "primary" : "default"} danger={isTrash} icon={<Icon name={isKeeper ? "check-circle" : isTrash ? "trash" : "shield"} size={12} />} onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}>
                    {isKeeper ? "נבחר לשמירה" : isTrash ? "למחיקה" : "שמור עותק זה"}
                  </Button>
                  <Tooltip title="פתח בתיקייה">
                    <Button icon={<Icon name="folder" size={12} />} onClick={() => openExplorer(album.path)} />
                  </Tooltip>
                </div>
                <div className="album-metrics">
                  <MetricTile label="איכות" value={album.quality_score ? formatPercent(album.quality_score) : "-"} percent={maxValues.quality_score ? ((album.quality_score || 0) / maxValues.quality_score) * 100 : 0} isWinner={metricWinners.quality_score === album.folder_id} />
                  <MetricTile label="ביטרייט" value={formatBitrate(album.avg_bitrate)} percent={maxValues.avg_bitrate ? ((album.avg_bitrate || 0) / maxValues.avg_bitrate) * 100 : 0} isWinner={metricWinners.avg_bitrate === album.folder_id} />
                  <MetricTile label="נפח" value={formatSizeMb(album.total_size_mb)} percent={0} color="transparent" />
                  <MetricTile label="קבצים" value={album.file_count} percent={0} color="transparent" />
                </div>
              </Card>
            );
            return (
              <div key={album.folder_id} className="album-card-shell">
                {ribbon ? <Badge.Ribbon text={ribbon.text} color={ribbon.color} placement="end" style={{ fontSize: "10px", padding: "0 6px", height: "18px", lineHeight: "18px" }}>{card}</Badge.Ribbon> : card}
              </div>
            );
          })}
        </div>
      </section>

      <section className="workspace-section" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
        <Card className="comparison-control-card cartoon-panel" variant="borderless" style={{ marginBottom: "10px" }}>
          <Flex align="center" gap={12}>
             <Typography.Text strong style={{ fontSize: "12px" }}>בסיס השוואה בטבלה:</Typography.Text>
             <Segmented size="small" options={comparisonOptions} value={comparisonTarget} onChange={setComparisonTarget} />
          </Flex>
          <div style={{ display: "flex", gap: "6px" }}>
             <Tag color="success" style={{ margin: 0, fontSize: "10px", border: "none" }}>תואם</Tag>
             <Tag color="warning" style={{ margin: 0, fontSize: "10px", border: "none" }}>שונה</Tag>
             <Tag color="error" style={{ margin: 0, fontSize: "10px", border: "none" }}>חסר</Tag>
          </div>
        </Card>
        <Card className="track-table-card cartoon-panel" variant="borderless">
          <Table
            className="tracks-table"
            columns={trackColumns}
            dataSource={trackRows}
            pagination={false}
            rowKey="key"
            size="small"
            scroll={{ x: 'max-content', y: 400 }}
            sticky
          />
        </Card>
      </section>
    </div>
  );
}