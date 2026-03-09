import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Flex,
  Progress,
  Segmented,
  Space,
  Table,
  Tag,
  Tooltip,
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
      <Typography.Text type="secondary" style={{ fontSize: "12px" }}>{label}</Typography.Text>
      <Typography.Text className="metric-value">{value}</Typography.Text>
      <Progress
        percent={Math.round(normalizedPercent)}
        showInfo={false}
        strokeColor={isWinner ? "#1d9f5f" : color}
        railColor="rgba(37, 114, 255, 0.08)"
        size="small"
        style={{ margin: "4px 0" }}
      />
      {hint ? (
        <Typography.Text type="secondary" style={{ fontSize: "11px", minHeight: "16px" }}>
          {hint}
        </Typography.Text>
      ) : <div style={{ minHeight: "16px" }} />}
    </Card>
  );
}

function DecisionCard({ icon, label, tone = "primary", children }) {
  return (
    <Card className="decision-card" variant="borderless">
      <StatusTag tone={tone} icon={icon} style={{ marginBottom: "12px", width: "fit-content" }}>
        {label}
      </StatusTag>
      <div className="decision-card-body">{children}</div>
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
    <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
      <Typography.Text strong ellipsis={{ tooltip: name }}>
        {name}
      </Typography.Text>
      <Typography.Paragraph
        type="secondary"
        style={{ margin: 0, fontSize: "12px", direction: "ltr", textAlign: "right" }}
        ellipsis={{ rows: 2, tooltip: path }}
      >
        {path}
      </Typography.Paragraph>
    </div>
  );
}

export function DiffWorkspace({ cluster, currentKeeperId, handleDecision, openExplorer }) {
  const[comparisonTarget, setComparisonTarget] = useState("auto");

  useEffect(() => {
    setComparisonTarget("auto");
  }, [cluster?.cluster_id, currentKeeperId]);

  const visibleAlbums = useMemo(
    () => cluster?.albums?.filter((album) => !album.is_deleted) ?? [],[cluster],
  );

  const visibleAlbumIds = useMemo(
    () => visibleAlbums.map((album) => album.folder_id),
    [visibleAlbums],
  );

  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);

  const defaultComparisonId = currentKeeperId ?? cluster?.recommended_keeper_id ?? visibleAlbums[0]?.folder_id ?? null;
  const activeComparisonId = comparisonTarget === "auto" ? defaultComparisonId : comparisonTarget;
  const selectedDeleteCount = currentKeeperId ? Math.max(visibleAlbums.length - 1, 0) : 0;

  const activeComparisonAlbum = useMemo(
    () => visibleAlbums.find((album) => album.folder_id === activeComparisonId) ?? null,
    [activeComparisonId, visibleAlbums],
  );
  
  const activeComparisonIndex = useMemo(
    () => visibleAlbums.findIndex((album) => album.folder_id === activeComparisonId),
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

  const comparisonOptions = useMemo(
    () =>[
      { label: "אוטומטי", value: "auto" },
      ...visibleAlbums.map((album, index) => ({
        label: `עותק ${index + 1}`,
        value: album.folder_id,
      })),
    ],
    [visibleAlbums],
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

  const overviewMetrics = useMemo(
    () =>[
      { key: "albums", title: "עותקים", value: visibleAlbums.length },
      { key: "tracks", title: "שירים להשוואה", value: trackRows.length },
      { key: "different", title: "שורות שונות", value: trackSummary.differentRows },
      { key: "delete", title: "יסומנו למחיקה", value: selectedDeleteCount },
    ],[selectedDeleteCount, trackRows.length, trackSummary.differentRows, visibleAlbums.length],
  );

  const comparisonSummaryText = useMemo(() => {
    if (!activeComparisonAlbum) return "אין עותק פעיל כרגע.";
    if (comparisonTarget !== "auto" && activeComparisonIndex >= 0) return `הטבלה מציגה כעת את כל ההבדלים מול עותק ${activeComparisonIndex + 1}.`;
    if (currentKeeperId) return "הטבלה עוקבת אוטומטית אחרי העותק שנבחר לשמירה.";
    if (recommendedAlbum) return "הטבלה עוקבת אוטומטית אחרי המלצת המערכת.";
    return "הטבלה עוקבת אוטומטית אחרי העותק הראשון בקבוצה.";
  },[activeComparisonAlbum, activeComparisonIndex, comparisonTarget, currentKeeperId, recommendedAlbum]);

  const trackColumns = useMemo(
    () =>[
      {
        title: "שיר מקורי",
        key: "reference",
        fixed: "left",
        width: 250,
        render: (_, row) => (
          <div className="track-main-cell">
            <Typography.Text strong ellipsis={{ tooltip: row.title }}>
              <Icon name="music" size={12} style={{ marginInlineEnd: 4 }} /> 
              {row.title}
            </Typography.Text>
            <div style={{ display: "flex", gap: "8px", fontSize: "12px", color: "var(--text-secondary)" }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {row.artist}
              </span>
              <span>•</span>
              <span>{formatDuration(row.duration)}</span>
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
            <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
              <Typography.Text strong ellipsis={{ tooltip: album.name }}>
                {album.name}
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: "12px", fontWeight: "normal" }}>
                {album.folder_id === activeComparisonId
                  ? (comparisonTarget === "auto" ? "בסיס אוטומטי" : "בסיס ידני")
                  : pairToActive?.is_identical_by_hash
                    ? "Hash זהה"
                    : pairToActive
                      ? formatPercent(pairToActive.final_score)
                      : "ללא התאמה"}
              </Typography.Text>
            </div>
          ),
          key: album.folder_id,
          width: 240,
          render: (_, row) => {
            const entry = row.entries[album.folder_id];
            const referenceEntry = activeComparisonId ? row.entries[activeComparisonId] : null;
            
            if (!entry) {
              return (
                <div style={{ color: "var(--colorError)", fontSize: "12px", fontWeight: "600" }}>
                  <Icon name="alert" size={12} style={{ marginInlineEnd: 4 }} /> חסר בעותק זה
                </div>
              );
            }
            
            const bitrateDifferent = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
            const durationDifferent = referenceEntry && Math.round(entry.duration || 0) !== Math.round(referenceEntry.duration || 0);
            const sizeDifferent = referenceEntry && Number(entry.size_mb || 0).toFixed(2) !== Number(referenceEntry.size_mb || 0).toFixed(2);
            
            return (
              <div className="track-entry">
                <Typography.Text ellipsis={{ tooltip: entry.filename }} style={{ fontWeight: 500 }}>
                  {entry.filename}
                </Typography.Text>
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
    ],[activeComparisonId, cluster, comparisonTarget, visibleAlbums],
  );

  if (!cluster) {
    return (
      <Card className="workspace-empty cartoon-card" variant="borderless">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="בחר קבוצה מהרשימה להתחיל" />
      </Card>
    );
  }

  const decisionItems =[
    {
      key: "current",
      label: "העותק שיישמר כעת",
      icon: "shield",
      tone: explicitKeeperAlbum ? "success" : "neutral",
      children: explicitKeeperAlbum 
        ? <PathSummary name={explicitKeeperAlbum.name} path={explicitKeeperAlbum.path} />
        : <Typography.Text type="secondary">לא נבחר עותק ידני לשמירה.</Typography.Text>
    },
    {
      key: "recommended",
      label: "המלצת מערכת",
      icon: "sparkle",
      tone: recommendedAlbum ? "primary" : "neutral",
      children: recommendedAlbum
        ? <PathSummary name={recommendedAlbum.name} path={recommendedAlbum.path} />
        : <Typography.Text type="secondary">אין המלצה חד-משמעית.</Typography.Text>
    },
    {
      key: "comparison",
      label: "בסיס השוואה",
      icon: "compare",
      tone: comparisonTarget === "auto" ? "primary" : "warning",
      children: activeComparisonAlbum ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
           <Typography.Text type="secondary" style={{ fontSize: "12px" }}>{comparisonSummaryText}</Typography.Text>
           <PathSummary name={`עותק ${activeComparisonIndex + 1}`} path={activeComparisonAlbum.path} />
        </div>
      ) : <Typography.Text type="secondary">אין בסיס פעיל.</Typography.Text>
    },
    {
      key: "delete",
      label: "לסל המחזור",
      icon: "trash",
      tone: selectedDeleteCount ? "warning" : "neutral",
      children: (
        <Space align="center" size={8}>
          <Typography.Title level={3} style={{ margin: 0 }}>{selectedDeleteCount}</Typography.Title>
          <Typography.Text type="secondary">עותקים יועברו אם תשמור עכשיו.</Typography.Text>
        </Space>
      )
    },
  ];

  return (
    <div className="diff-shell" data-testid="diff-shell">
      
      {/* 1. OVERVIEW & DECISION CENTER */}
      <section className="diff-overview-grid">
        <Card className="diff-overview-card cartoon-card" variant="borderless">
          <div className="diff-overview-copy-head">
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div className="soft-kicker">
                <Icon name="compare" size={14} />
                מרכז ההחלטה
              </div>
              <Typography.Title level={2} className="diff-header-title">
                {cluster.human_summary}
              </Typography.Title>
            </div>
            
            <Space wrap size={8}>
              <StatusTag tone={cluster.confidence_bucket === "safe" ? "success" : "warning"} icon={cluster.confidence_bucket === "safe" ? "shield" : "alert"}>
                {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
              </StatusTag>
              {currentKeeperId ? (
                <StatusTag tone="success" icon="check-circle">נבחר keeper</StatusTag>
              ) : recommendedAlbum ? (
                <StatusTag tone="primary" icon="sparkle">יש המלצה</StatusTag>
              ) : (
                <StatusTag tone="neutral" icon="alert">ממתין להכרעה</StatusTag>
              )}
            </Space>
          </div>

          <div className="diff-trust-strip">
             <Icon name="shield" size={14} />
             כל המחיקות מתבצעות דרך סל המחזור בלבד (Recycle Bin).
          </div>

          <div className="decision-card-grid">
            {decisionItems.map(item => (
              <DecisionCard key={item.key} icon={item.icon} label={item.label} tone={item.tone}>
                {item.children}
              </DecisionCard>
            ))}
          </div>
        </Card>

        {/* SIDE RAIL: KPIS & SCORE */}
        <div className="diff-side-rail">
          <Card className="diff-state-card cartoon-card" variant="borderless">
            <Typography.Title level={4} style={{ margin: "0 0 16px" }}>תמונת מצב מהירה</Typography.Title>
            <div className="diff-kpi-row">
              {overviewMetrics.map((metric) => (
                <Card key={metric.key} className="diff-kpi-card cartoon-panel" variant="borderless">
                   <Typography.Text type="secondary" style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                     {metric.title}
                   </Typography.Text>
                   <Typography.Text strong style={{ fontSize: "1.4rem" }}>
                     {metric.value}
                   </Typography.Text>
                </Card>
              ))}
            </div>
          </Card>
          <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />
        </div>
      </section>

      {/* 2. ALBUM CARDS (HORIZONTAL SCROLL) */}
      <section className="workspace-section">
        <div className="section-head">
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
             <div className="soft-kicker"><Icon name="layers" size={14} /> השוואת עותקים</div>
             <Typography.Title level={3} style={{ margin: 0 }}>כרטיסי אלבומים</Typography.Title>
          </div>
          <Space wrap>
            <StatusTag tone="primary" icon="layers">{visibleAlbums.length} עותקים</StatusTag>
          </Space>
        </div>

        <div className="comparison-scroller" data-testid="comparison-scroller">
          {visibleAlbums.map((album, index) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isTrash = Boolean(currentKeeperId) && !isKeeper;
            const isRecommended = cluster.recommended_keeper_id === album.folder_id;
            const ribbon = getAlbumRibbon(album, currentKeeperId, cluster.recommended_keeper_id);
            
            const card = (
              <Card className={`album-card cartoon-card ${isKeeper ? "is-keeper" : ""} ${isTrash ? "is-deleted" : ""}`} variant="borderless">
                <div className="album-card-heading">
                  <Flex justify="space-between" align="center" style={{ marginBottom: 4 }}>
                    <StatusTag tone={isKeeper ? "success" : isTrash ? "danger" : "neutral"} style={{ margin: 0 }}>
                      עותק {index + 1}
                    </StatusTag>
                    {album.in_preferred_root && <Icon name="sparkle" style={{ color: "var(--colorPrimary)" }} title="בתיקייה מועדפת" />}
                  </Flex>
                  <Typography.Title level={4} className="album-card-title" ellipsis={{ tooltip: album.name }}>
                    {album.name}
                  </Typography.Title>
                </div>

                <div className="album-path-inline">
                  <Icon name="folder" size={14} style={{ color: "var(--text-tertiary)" }} />
                  <Typography.Text className="album-inline-path" ellipsis={{ tooltip: album.path }}>
                    {album.path}
                  </Typography.Text>
                </div>

                <div className="album-actions">
                  <Button
                    type={isKeeper ? "primary" : "default"}
                    danger={isTrash}
                    size="middle"
                    icon={<Icon name={isKeeper ? "check-circle" : isTrash ? "trash" : "shield"} size={14} />}
                    onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                  >
                    {isKeeper ? "נבחר לשמירה" : isTrash ? "מיועד למחיקה" : "שמור עותק זה"}
                  </Button>
                  <Tooltip title="פתח בתיקייה">
                    <Button size="middle" icon={<Icon name="folder" size={14} />} onClick={() => openExplorer(album.path)} />
                  </Tooltip>
                </div>

                <div className="album-metrics">
                  <MetricTile
                    label="דירוג איכות"
                    value={album.quality_score ? formatPercent(album.quality_score) : "ללא נתון"}
                    percent={maxValues.quality_score ? ((album.quality_score || 0) / maxValues.quality_score) * 100 : 0}
                    isWinner={metricWinners.quality_score === album.folder_id}
                  />
                  <MetricTile
                    label="ביטרייט"
                    value={formatBitrate(album.avg_bitrate)}
                    percent={maxValues.avg_bitrate ? ((album.avg_bitrate || 0) / maxValues.avg_bitrate) * 100 : 0}
                    isWinner={metricWinners.avg_bitrate === album.folder_id}
                  />
                  <MetricTile label="נפח" value={formatSizeMb(album.total_size_mb)} percent={0} color="transparent" />
                  <MetricTile label="קבצים" value={album.file_count} percent={0} color="transparent" />
                </div>
              </Card>
            );

            return (
              <div key={album.folder_id} className="album-card-shell">
                {ribbon ? (
                  <Badge.Ribbon text={ribbon.text} color={ribbon.color} placement="end">
                    {card}
                  </Badge.Ribbon>
                ) : card}
              </div>
            );
          })}
        </div>
      </section>

      {/* 3. TRACKS TABLE */}
      <section className="workspace-section">
        <div className="section-head">
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <div className="soft-kicker"><Icon name="music" size={14} /> טבלת שירים</div>
            <Typography.Title level={3} style={{ margin: 0 }}>השוואה פרטנית</Typography.Title>
          </div>
        </div>

        <Card className="comparison-control-card cartoon-panel" variant="borderless">
          <Flex justify="space-between" align="center" wrap="wrap" gap={16}>
             <Typography.Text strong>בחר בסיס השוואה:</Typography.Text>
             <Segmented options={comparisonOptions} value={comparisonTarget} onChange={setComparisonTarget} />
          </Flex>
          
          <Alert
            type={comparisonTarget === "auto" ? "info" : "warning"}
            showIcon
            message={comparisonTarget === "auto" ? "מעקב אוטומטי פעיל" : "השוואה ידנית מקובעת"}
            description={comparisonSummaryText}
            style={{ borderRadius: "12px" }}
          />

          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "8px" }}>
             <Tag color="success" style={{ borderRadius: "12px" }}>תואם לעותק הבסיס</Tag>
             <Tag color="warning" style={{ borderRadius: "12px" }}>ערך שונה</Tag>
             <Tag color="error" style={{ borderRadius: "12px" }}>חסר בעותק</Tag>
          </div>
        </Card>

        <Card className="track-table-card cartoon-card" variant="borderless">
          <Table
            className="tracks-table"
            columns={trackColumns}
            dataSource={trackRows}
            pagination={false}
            rowKey="key"
            size="small"
            scroll={{ x: 'max-content', y: 440 }}
            sticky
          />
        </Card>
      </section>

    </div>
  );
}