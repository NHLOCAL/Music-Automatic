import React, { useMemo } from "react";
import {
  Badge,
  Button,
  Card,
  Descriptions,
  Empty,
  Flex,
  Progress,
  Space,
  Statistic,
  Table,
  Typography,
} from "antd";

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

function MetricTile({ label, value, percent, isWinner = false, color = "#2572ff", hint = null }) {
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
      {hint ? (
        <Typography.Text className="metric-hint" type="secondary">
          {hint}
        </Typography.Text>
      ) : null}
    </Card>
  );
}

function getAlbumRibbon(album, currentKeeperId, recommendedKeeperId) {
  if (currentKeeperId === album.folder_id) {
    return { color: "#1d9f5f", text: "העותק שנשמר" };
  }
  if (currentKeeperId && currentKeeperId !== album.folder_id) {
    return { color: "#ef5350", text: "יסומן למחיקה" };
  }
  if (recommendedKeeperId === album.folder_id) {
    return { color: "#2572ff", text: "המלצת מערכת" };
  }
  return null;
}

function PathSummary({ name, path }) {
  return (
    <Space orientation="vertical" size={2} style={{ width: "100%" }}>
      <Typography.Text strong ellipsis={{ tooltip: name }}>
        {name}
      </Typography.Text>
      <Typography.Paragraph
        className="decision-path"
        ellipsis={{ rows: 2, tooltip: path, expandable: "collapsible", symbol: "עוד" }}
      >
        {path}
      </Typography.Paragraph>
    </Space>
  );
}

export function DiffWorkspace({ cluster, currentKeeperId, handleDecision, openExplorer }) {
  const visibleAlbums = useMemo(
    () => cluster?.albums?.filter((album) => !album.is_deleted) ?? [],
    [cluster],
  );
  const visibleAlbumIds = useMemo(
    () => visibleAlbums.map((album) => album.folder_id),
    [visibleAlbums],
  );
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const activeComparisonId = currentKeeperId ?? cluster?.recommended_keeper_id ?? visibleAlbums[0]?.folder_id ?? null;
  const selectedDeleteCount = currentKeeperId ? Math.max(visibleAlbums.length - 1, 0) : 0;

  const activeComparisonAlbum = useMemo(
    () => visibleAlbums.find((album) => album.folder_id === activeComparisonId) ?? null,
    [activeComparisonId, visibleAlbums],
  );
  const explicitKeeperAlbum = useMemo(
    () => visibleAlbums.find((album) => album.folder_id === currentKeeperId) ?? null,
    [currentKeeperId, visibleAlbums],
  );
  const recommendedAlbum = useMemo(
    () => visibleAlbums.find((album) => album.folder_id === cluster?.recommended_keeper_id) ?? null,
    [cluster?.recommended_keeper_id, visibleAlbums],
  );

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
    let missingRows = 0;

    trackRows.forEach((row) => {
      if (getTrackRowTone(row, visibleAlbumIds) === "different") {
        differentRows += 1;
      }
      if (visibleAlbumIds.some((albumId) => !row.entries[albumId])) {
        missingRows += 1;
      }
    });

    return { differentRows, missingRows };
  }, [trackRows, visibleAlbumIds]);

  const trackColumns = useMemo(
    () => [
      {
        title: "שיר מקורי",
        key: "reference",
        fixed: "right",
        width: 280,
        render: (_, row) => (
          <div className="track-main-cell">
            <Typography.Text strong className="track-main-title" ellipsis={{ tooltip: row.title }}>
              <Icon name="music" size={14} /> {row.title}
            </Typography.Text>
            <div className="track-main-meta">
              <Typography.Text type="secondary" ellipsis={{ tooltip: row.artist }}>
                {row.artist}
              </Typography.Text>
              <span className="track-chip">{formatDuration(row.duration)}</span>
            </div>
          </div>
        ),
      },
      ...visibleAlbums.map((album) => {
        const pairToActive = activeComparisonId && album.folder_id !== activeComparisonId
          ? findClusterPair(cluster, activeComparisonId, album.folder_id)
          : null;

        return {
          title: (
            <div className="track-column-title">
              <Typography.Text strong className="track-column-name" ellipsis={{ tooltip: album.name }}>
                {album.name}
              </Typography.Text>
              <Typography.Text type="secondary" className="track-column-subtitle">
                {album.folder_id === activeComparisonId
                  ? "בסיס ההשוואה"
                  : pairToActive?.is_identical_by_hash
                    ? "Hash זהה"
                    : pairToActive
                      ? formatPercent(pairToActive.final_score)
                      : "ללא pair"}
              </Typography.Text>
            </div>
          ),
          key: album.folder_id,
          width: 228,
          render: (_, row) => {
            const entry = row.entries[album.folder_id];
            const referenceEntry = activeComparisonId ? row.entries[activeComparisonId] : null;

            if (!entry) {
              return (
                <div className="track-missing">
                  <Icon name="alert" size={14} /> חסר בעותק זה
                </div>
              );
            }

            const bitrateDifferent = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
            const durationDifferent = referenceEntry && Math.round(entry.duration || 0) !== Math.round(referenceEntry.duration || 0);
            const sizeDifferent = referenceEntry && Number(entry.size_mb || 0).toFixed(2) !== Number(referenceEntry.size_mb || 0).toFixed(2);

            return (
              <div className="track-entry">
                <span className="track-entry-name">
                  <Icon name="music" size={14} />
                  <Typography.Text className="track-entry-filename" ellipsis={{ tooltip: entry.filename }}>
                    {entry.filename}
                  </Typography.Text>
                </span>
                <div className="track-entry-meta">
                  <span className={`track-chip ${bitrateDifferent ? "is-different" : ""}`}>
                    {formatBitrate(entry.bitrate)}
                  </span>
                  <span className={`track-chip ${durationDifferent ? "is-different" : ""}`}>
                    {formatDuration(entry.duration)}
                  </span>
                  <span className={`track-chip ${sizeDifferent ? "is-different" : ""}`}>
                    {formatSizeMb(entry.size_mb)}
                  </span>
                </div>
              </div>
            );
          },
        };
      }),
    ],
    [activeComparisonId, cluster, visibleAlbums],
  );

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

  const decisionItems = [
    {
      key: "current",
      label: "העותק שיישמר כעת",
      children: explicitKeeperAlbum ? (
        <PathSummary name={explicitKeeperAlbum.name} path={explicitKeeperAlbum.path} />
      ) : (
        <Typography.Text type="secondary">עדיין לא נבחר keeper ידני</Typography.Text>
      ),
    },
    {
      key: "recommended",
      label: "המלצת המערכת",
      children: recommendedAlbum ? (
        <PathSummary name={recommendedAlbum.name} path={recommendedAlbum.path} />
      ) : (
        <Typography.Text type="secondary">אין המלצה חד-משמעית לקבוצה הזאת</Typography.Text>
      ),
    },
    {
      key: "comparison",
      label: "בסיס ההשוואה בטבלת השירים",
      children: activeComparisonAlbum ? (
        <Space align="center" size={8}>
          <StatusTag tone="primary" icon="compare">
            {activeComparisonAlbum.name}
          </StatusTag>
          <Typography.Text type="secondary">ההבדלים מוצגים ביחס לעותק זה</Typography.Text>
        </Space>
      ) : (
        <Typography.Text type="secondary">אין עותק פעיל להשוואה</Typography.Text>
      ),
    },
    {
      key: "delete",
      label: "מה יועבר לסל המחזור",
      children: (
        <Space align="center" size={8}>
          <StatusTag tone={selectedDeleteCount ? "warning" : "neutral"} icon="trash">
            {selectedDeleteCount} עותקים
          </StatusTag>
          <Typography.Text type="secondary">
            המחיקה תמיד מתבצעת דרך סל המחזור בלבד
          </Typography.Text>
        </Space>
      ),
    },
  ];

  return (
    <div className="diff-shell" data-testid="diff-shell">
      <div className="diff-primary-stack">
        <Card className="diff-header-card cartoon-card" variant="borderless">
          <Flex className="diff-header-grid" justify="space-between" align="flex-start" gap={16} wrap>
            <div className="diff-header-copy">
              <Space wrap size={12}>
                <Typography.Title
                  level={2}
                  style={{ margin: 0 }}
                  className="diff-header-title"
                  ellipsis={{ tooltip: cluster.human_summary }}
                >
                  {cluster.human_summary}
                </Typography.Title>
                <StatusTag
                  tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}
                  icon={cluster.confidence_bucket === "safe" ? "shield" : "alert"}
                >
                  {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
                </StatusTag>
                {currentKeeperId ? (
                  <StatusTag tone="success" icon="check-circle">
                    נבחר keeper
                  </StatusTag>
                ) : recommendedAlbum ? (
                  <StatusTag tone="primary" icon="sparkle">
                    קיימת המלצת מערכת
                  </StatusTag>
                ) : null}
              </Space>
              <Typography.Paragraph className="muted-copy diff-header-summary">
                בחר עותק אחד לשמירה. שאר העותקים יסומנו להעברה לסל המחזור, ותוכל לאמת כל נתיב לפני הפעולה.
              </Typography.Paragraph>
              <div className="diff-trust-strip">
                <Icon name="shield" size={16} />
                שום דבר לא נמחק לצמיתות. כל ההעברות נעשות אל סל המחזור בלבד.
              </div>
            </div>

            <div className="diff-kpi-row">
              <Card className="diff-kpi-card cartoon-panel" variant="borderless">
                <Statistic title="עותקים בקבוצה" value={visibleAlbums.length} prefix={<Icon name="layers" size={16} />} />
              </Card>
              <Card className="diff-kpi-card cartoon-panel" variant="borderless">
                <Statistic title="שירים להשוואה" value={trackRows.length} prefix={<Icon name="music" size={16} />} />
              </Card>
              <Card className="diff-kpi-card cartoon-panel" variant="borderless">
                <Statistic title="שורות שונות" value={trackSummary.differentRows} prefix={<Icon name="compare" size={16} />} />
              </Card>
              <Card className="diff-kpi-card cartoon-panel" variant="borderless">
                <Statistic title="יסומנו למחיקה" value={selectedDeleteCount} prefix={<Icon name="trash" size={16} />} />
              </Card>
            </div>
          </Flex>

          <Card className="decision-strip cartoon-panel" variant="borderless">
            <Descriptions
              bordered
              column={{ xs: 1, sm: 1, lg: 2, xxl: 4 }}
              size="small"
              className="decision-descriptions"
              items={decisionItems}
            />
          </Card>
        </Card>

        <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />
      </div>

      <div className="diff-content-stack">
        <section className="workspace-section">
          <div className="section-head">
            <div>
              <div className="soft-kicker">
                <Icon name="compare" size={14} />
                תצוגת החלטה
              </div>
              <Typography.Title level={3} style={{ margin: "10px 0 0" }}>
                עותקי האלבום זה לצד זה
              </Typography.Title>
              <Typography.Paragraph className="muted-copy section-subcopy">
                כל כרטיס מציג מצב עותק, metadata מרכזי, ומדדי איכות כדי להכריע במהירות איזה עותק נשאר.
              </Typography.Paragraph>
            </div>
            <Space wrap size={8}>
              <StatusTag tone="primary" icon="layers">
                {visibleAlbums.length} עותקים
              </StatusTag>
              <StatusTag tone={trackSummary.missingRows ? "warning" : "success"} icon="music">
                {trackSummary.missingRows ? `${trackSummary.missingRows} שורות עם חוסרים` : "כל השירים קיימים"}
              </StatusTag>
            </Space>
          </div>

          <div className="comparison-scroller" data-testid="comparison-scroller">
            <div
              className="album-grid"
              style={{
                gridTemplateColumns: `repeat(${visibleAlbums.length}, minmax(280px, 1fr))`,
                minWidth: `${visibleAlbums.length * 296}px`,
              }}
            >
              {visibleAlbums.map((album, index) => {
                const isKeeper = currentKeeperId === album.folder_id;
                const isTrash = Boolean(currentKeeperId) && !isKeeper;
                const isRecommended = cluster.recommended_keeper_id === album.folder_id;
                const ribbon = getAlbumRibbon(album, currentKeeperId, cluster.recommended_keeper_id);
                const pairToActive = activeComparisonId && album.folder_id !== activeComparisonId
                  ? findClusterPair(cluster, activeComparisonId, album.folder_id)
                  : null;

                const card = (
                  <Card
                    className={`album-card cartoon-card ${isKeeper ? "is-keeper" : ""} ${isTrash ? "is-deleted" : ""}`}
                    variant="borderless"
                  >
                    <Flex justify="space-between" align="flex-start" gap={12} wrap>
                      <div className="album-card-heading">
                        <Space wrap size={8}>
                          <Typography.Title
                            level={4}
                            style={{ margin: 0 }}
                            className="album-card-title"
                            ellipsis={{ tooltip: album.name }}
                          >
                            {album.name}
                          </Typography.Title>
                          <StatusTag tone={isKeeper ? "success" : isTrash ? "danger" : "neutral"}>
                            עותק {index + 1}
                          </StatusTag>
                        </Space>
                        <Typography.Paragraph
                          className="album-heading-path"
                          type="secondary"
                          ellipsis={{ rows: 2, tooltip: album.path, expandable: "collapsible", symbol: "עוד" }}
                        >
                          {album.path}
                        </Typography.Paragraph>
                      </div>

                      <div className="album-actions">
                        <Button
                          type={isKeeper ? "primary" : "default"}
                          danger={isTrash}
                          size="middle"
                          icon={<Icon name={isKeeper ? "check-circle" : isTrash ? "trash" : "shield"} size={16} />}
                          onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                        >
                          {isKeeper ? "נבחר לשמירה" : isTrash ? "מיועד למחיקה" : "שמור עותק זה"}
                        </Button>
                        <Button
                          size="middle"
                          icon={<Icon name="folder" size={16} />}
                          title="פתח בתיקייה"
                          aria-label="פתח בתיקייה"
                          onClick={() => openExplorer(album.path)}
                        />
                      </div>
                    </Flex>

                    <div className="album-relationship-banner">
                      <Icon name={isKeeper ? "check-circle" : isRecommended ? "sparkle" : "compare"} size={15} />
                      <span>
                        {isKeeper
                          ? "זהו העותק שנשמר כרגע."
                          : isRecommended
                            ? "זהו העותק שהמערכת ממליצה לשמור."
                            : pairToActive?.is_identical_by_hash
                              ? "זהה לחלוטין לעותק הפעיל לפי hash."
                              : pairToActive
                                ? `ציון התאמה ${formatPercent(pairToActive.final_score)} מול העותק הפעיל.`
                                : "אין כרגע keeper ידני, ולכן ההשוואה מוצגת מול העותק הפעיל בממשק."}
                      </span>
                    </div>

                    <div className="album-path-box" title={album.path}>{album.path}</div>

                    <div className="album-path-flags">
                      {album.in_preferred_root ? (
                        <StatusTag tone="primary" icon="shield">
                          בתיקייה מועדפת
                        </StatusTag>
                      ) : null}
                      {album.has_album_art ? (
                        <StatusTag tone="success" icon="eye">
                          עטיפה זמינה
                        </StatusTag>
                      ) : (
                        <StatusTag tone="neutral" icon="alert">
                          ללא עטיפה
                        </StatusTag>
                      )}
                      {pairToActive?.is_identical_by_hash ? (
                        <StatusTag tone="success" icon="check-circle">
                          Hash זהה
                        </StatusTag>
                      ) : null}
                    </div>

                    <Descriptions
                      className="album-descriptions"
                      size="small"
                      bordered
                      column={{ xs: 1, sm: 2 }}
                      items={[
                        {
                          key: "quality",
                          label: "דירוג איכות",
                          children: formatPercent(album.quality_score),
                        },
                        {
                          key: "bitrate",
                          label: "ביטרייט ממוצע",
                          children: formatBitrate(album.avg_bitrate),
                        },
                        {
                          key: "size",
                          label: "נפח תיקייה",
                          children: formatSizeMb(album.total_size_mb),
                        },
                        {
                          key: "files",
                          label: "מספר קבצים",
                          children: `${album.file_count} קבצים`,
                        },
                      ]}
                    />

                    <div className="album-metrics">
                      <MetricTile
                        label="דירוג איכות"
                        value={album.quality_score ? formatPercent(album.quality_score) : "ללא נתון"}
                        percent={maxValues.quality_score ? ((album.quality_score || 0) / maxValues.quality_score) * 100 : 0}
                        isWinner={metricWinners.quality_score === album.folder_id}
                        hint={metricWinners.quality_score === album.folder_id ? "הגבוה ביותר בקבוצה" : null}
                      />
                      <MetricTile
                        label="ביטרייט ממוצע"
                        value={formatBitrate(album.avg_bitrate)}
                        percent={maxValues.avg_bitrate ? ((album.avg_bitrate || 0) / maxValues.avg_bitrate) * 100 : 0}
                        isWinner={metricWinners.avg_bitrate === album.folder_id}
                        hint={metricWinners.avg_bitrate === album.folder_id ? "איכות שמע מובילה" : null}
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

                return (
                  <div key={album.folder_id} className="album-card-shell">
                    {ribbon ? (
                      <Badge.Ribbon text={ribbon.text} color={ribbon.color} placement="start">
                        {card}
                      </Badge.Ribbon>
                    ) : card}
                  </div>
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
              <Typography.Paragraph className="muted-copy section-subcopy">
                ה-header נשאר דביק בזמן גלילה, והבדלים בין שירים מודגשים כדי למנוע מעבר ידני על כל תא.
              </Typography.Paragraph>
            </div>
            <Space wrap size={8}>
              <StatusTag tone={trackSummary.differentRows ? "warning" : "success"} icon="compare">
                {trackSummary.differentRows} שורות שונות
              </StatusTag>
              <StatusTag tone={trackSummary.missingRows ? "warning" : "primary"} icon="music">
                {trackSummary.missingRows} שורות עם חוסרים
              </StatusTag>
            </Space>
          </div>

          <Card className="track-table-card cartoon-card" variant="borderless" data-testid="track-table-card">
            <Table
              className="tracks-table"
              columns={trackColumns}
              dataSource={trackRows}
              pagination={false}
              rowKey="key"
              rowClassName={(row) => `track-row-${getTrackRowTone(row, visibleAlbumIds)}`}
              size="small"
              tableLayout="fixed"
              scroll={{ x: Math.max(920, visibleAlbums.length * 228 + 240), y: 440 }}
              sticky={{ offsetHeader: 8 }}
              summary={() => (
                <Table.Summary fixed>
                  <Table.Summary.Row>
                    <Table.Summary.Cell index={0}>
                      <div className="track-summary-cell">
                        <Typography.Text strong>סיכום זמינות</Typography.Text>
                        <Typography.Text type="secondary">
                          {trackRows.length} שורות השוואה
                        </Typography.Text>
                      </div>
                    </Table.Summary.Cell>
                    {visibleAlbums.map((album, index) => {
                      const presentCount = trackRows.filter((row) => row.entries[album.folder_id]).length;
                      const missingCount = trackRows.length - presentCount;

                      return (
                        <Table.Summary.Cell key={album.folder_id} index={index + 1}>
                          <div className="track-summary-cell">
                            <Typography.Text strong>{presentCount} שירים זמינים</Typography.Text>
                            <Typography.Text type="secondary">
                              {missingCount > 0 ? `${missingCount} חסרים` : "כיסוי מלא"}
                            </Typography.Text>
                          </div>
                        </Table.Summary.Cell>
                      );
                    })}
                  </Table.Summary.Row>
                </Table.Summary>
              )}
            />
          </Card>
        </section>
      </div>
    </div>
  );
}
