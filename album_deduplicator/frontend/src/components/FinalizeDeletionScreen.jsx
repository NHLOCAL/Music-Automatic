import React from "react";
import { Alert, Button, Card, Empty, Flex, Space, Statistic, Typography } from "antd";

import { Icon, StatusTag } from "./UI";
import { formatSizeMb, getClusterDisplayTitle } from "../utils";

function buildOverviewStats(summary) {
  return [
    {
      key: "pending",
      title: "ממתינות להעברה",
      value: summary.pendingCount,
      icon: "trash",
      copy: `${formatSizeMb(summary.pendingSizeMb)} • ${summary.pendingGroupCount} קבוצות פעילות`,
    },
    {
      key: "selected",
      title: "בחירה אוטומטית",
      value: summary.autoSelectedCount,
      icon: "sparkle",
      copy: summary.manualSelectedCount > 0
        ? `${summary.manualSelectedCount} בחירות ידניות נוספו לסבב הנוכחי`
        : "אין כרגע בחירות ידניות נוספות",
    },
    {
      key: "deleted",
      title: "כבר הועברו",
      value: summary.deletedCount,
      icon: "check-circle",
      copy: `${formatSizeMb(summary.deletedSizeMb)} • ${summary.historyGroupCount} קבוצות עם היסטוריה`,
    },
    {
      key: "keepers",
      title: "עותקים שנשמרו",
      value: summary.keeperCount,
      icon: "shield",
      copy: summary.failedCount > 0
        ? `${summary.failedCount} העברות נכשלו ודורשות בדיקה`
        : "לא זוהו כשלים בהעברות שבוצעו",
    },
  ];
}

function KeeperPanel({ keeper, openExplorer }) {
  if (!keeper) {
    return (
      <Alert
        type="warning"
        showIcon
        title="העותק שנשמר"
        description="עדיין לא נבחר keeper לקבוצה זו"
      />
    );
  }

  return (
    <Card className="finalize-keeper-card cartoon-panel" variant="borderless">
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space orientation="vertical" size={8} style={{ flex: 1 }}>
          <Typography.Text type="secondary">העותק שנשמר</Typography.Text>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {keeper.name}
          </Typography.Title>
          <div className="finalize-path" title={keeper.path}>{keeper.path}</div>
          <div className="finalize-item-meta">
            <span>{keeper.file_count} קבצים</span>
            <span>{formatSizeMb(keeper.total_size_mb)}</span>
          </div>
        </Space>
        <Button type="default" icon={<Icon name="folder" size={14} />} onClick={() => openExplorer(keeper.path)}>
          פתח keeper
        </Button>
      </Flex>
    </Card>
  );
}

function ItemCard({ item, keeper, variant = "pending", openExplorer }) {
  const isHistory = variant === "history";
  const isFailed = variant === "failed";

  return (
    <Card
      className={`finalize-item-card cartoon-panel ${isHistory ? "is-history" : ""} ${isFailed ? "is-failed" : ""}`.trim()}
      variant="borderless"
    >
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space orientation="vertical" size={8} style={{ flex: 1 }}>
          <Space align="center" wrap>
            <Typography.Text strong>{item.name}</Typography.Text>
            <StatusTag tone={item.status_tone ?? (isHistory ? "success" : "warning")}>
              {item.status_label}
            </StatusTag>
          </Space>
          <div className="finalize-path" title={item.path}>{item.path}</div>
          <div className="finalize-item-meta">
            <span>{item.file_count} קבצים</span>
            <span>{formatSizeMb(item.estimated_size_mb ?? item.total_size_mb)}</span>
            {keeper ? <span>{isHistory ? `נמחק מול ${keeper.name}` : `יישמר מול ${keeper.name}`}</span> : null}
          </div>
          {item.failure_message ? (
            <Typography.Text type="danger">{item.failure_message}</Typography.Text>
          ) : null}
        </Space>

        <Space wrap>
          {!isHistory ? (
            <Button type="default" icon={<Icon name="folder" size={14} />} onClick={() => openExplorer(item.path)}>
              פתח תיקייה
            </Button>
          ) : null}
          {keeper ? (
            <Button type="default" icon={<Icon name="shield" size={14} />} onClick={() => openExplorer(keeper.path)}>
              פתח keeper
            </Button>
          ) : null}
        </Space>
      </Flex>
    </Card>
  );
}

function GroupCard({ group, sectionTitle, sectionTone, items, openExplorer, showHistoryHint = false }) {
  if (!items.length) return null;
  const sectionDescription = showHistoryHint
    ? "תיקיות שכבר הועברו לסל המחזור, יחד עם העותק שנשמר להשוואה."
    : "תיקיות שייכנסו עכשיו לסל המחזור אם תאשר את הפעולה.";

  return (
    <Card className="finalize-group-card cartoon-panel" variant="borderless">
      <div className="finalize-group-head">
        <div>
          <Space align="center" wrap>
            <Typography.Title level={3} style={{ margin: 0 }}>
              {getClusterDisplayTitle(group.cluster)}
            </Typography.Title>
            <StatusTag tone={group.status.tone}>{group.status.label}</StatusTag>
          </Space>
          <Typography.Paragraph className="muted-copy" style={{ margin: "8px 0 0" }}>
            {group.cluster.human_summary}
          </Typography.Paragraph>
        </div>
        <StatusTag tone={sectionTone}>{items.length}</StatusTag>
      </div>

      <div className="finalize-group-summary">
        <KeeperPanel keeper={group.keeper} openExplorer={openExplorer} />
        <div className={`finalize-group-banner is-${sectionTone}`}>
          <Typography.Text strong>{sectionTitle}</Typography.Text>
          <Typography.Text type="secondary">{sectionDescription}</Typography.Text>
        </div>
      </div>
      <Space orientation="vertical" size={12} style={{ width: "100%" }}>
        <Space orientation="vertical" size={12} style={{ width: "100%" }}>
          {items.map((item) => (
            <ItemCard
              key={item.folder_id}
              item={item}
              keeper={group.keeper}
              variant={showHistoryHint ? "history" : "pending"}
              openExplorer={openExplorer}
            />
          ))}
        </Space>
      </Space>
    </Card>
  );
}

export function FinalizeDeletionScreen({
  workflow,
  onBackToReview,
  onBackToSetup,
  onExecute,
  isExecuting,
  openExplorer,
}) {
  const { pendingGroups, historyGroups, summary } = workflow;
  const hasPending = summary.pendingCount > 0;
  const overviewStats = buildOverviewStats(summary);
  const readinessTone = summary.failedCount > 0 ? "danger" : hasPending ? "warning" : "success";
  const readinessLabel = summary.failedCount > 0
    ? "יש פריטים שדורשים טיפול"
    : hasPending
      ? "מוכן להעברה"
      : "אין כרגע פריטים להעברה";
  const readinessCopy = hasPending
    ? "כל הפריטים כאן כבר מקושרים לעותק שנשמר, כך שאפשר לאשר או לחזור לסקירה בלי לחפש הקשר נוסף."
    : "אין כרגע פריטים שממתינים למחיקה, אבל ההיסטוריה נשארת זמינה להשוואה ולבקרה.";

  return (
    <div className="screen-center">
      <div className="finalize-shell">
        <Card className="finalize-overview-card cartoon-card" variant="borderless">
          <div className="finalize-hero">
            <div>
              <div className="soft-kicker">
                <Icon name="compare" size={14} />
                שלב 3 מתוך 3
              </div>
              <Typography.Title level={1} style={{ marginBottom: 8 }}>
                מרכז ההעברה וההשוואה
              </Typography.Title>
              <Typography.Paragraph className="page-subtitle" style={{ marginBottom: 0, maxWidth: 760 }}>
                כאן רואים מה עומד לעבור לסל המחזור ומה כבר הועבר קודם, תמיד מול העותק שנשמר.
                המבנה נשאר קצר וברור כדי לאשר או לחזור לסקירה בלי עומס נוסף.
              </Typography.Paragraph>
            </div>
            <div className="screen-actions finalize-hero-actions">
              <Button type="default" size="large" icon={<Icon name="compare" size={16} />} onClick={onBackToReview}>
                חזור לסקירה
              </Button>
              <Button type="default" size="large" icon={<Icon name="arrow-left" size={16} />} onClick={onBackToSetup}>
                סריקה חדשה
              </Button>
              <Button
                type="primary"
                danger
                size="large"
                icon={<Icon name="trash" size={16} />}
                onClick={onExecute}
                disabled={!hasPending || isExecuting}
              >
                {isExecuting
                  ? "מעביר לסל המחזור..."
                  : hasPending
                    ? `העבר ${summary.pendingCount} תיקיות לסל המחזור`
                    : "אין פריטים להעברה"}
              </Button>
            </div>
          </div>

          <div className="finalize-topline summary-topline">
            <StatusTag tone={readinessTone} icon={summary.failedCount > 0 ? "alert" : hasPending ? "trash" : "check-circle"}>
              {readinessLabel}
            </StatusTag>
            <Typography.Text type="secondary">{readinessCopy}</Typography.Text>
          </div>

          <div className="finalize-summary-grid" data-testid="finalize-summary-grid">
            {overviewStats.map((item) => (
              <Card key={item.key} className="finalize-summary-card cartoon-panel" variant="borderless">
                <Statistic title={item.title} value={item.value} prefix={<Icon name={item.icon} size={18} />} />
                <div className="muted-copy">{item.copy}</div>
              </Card>
            ))}
          </div>

          <Alert
            className="finalize-note"
            type={summary.failedCount > 0 ? "warning" : "info"}
            showIcon
            icon={<Icon name={summary.failedCount > 0 ? "alert" : "info"} size={16} />}
            title={summary.failedCount > 0
              ? "יש העברות שנכשלו. כדאי לפתוח את הקבוצות הרלוונטיות ולבדוק את ההודעה לפני ניסיון נוסף."
              : "רק הפריטים באזור \"ממתינות להעברה עכשיו\" ייכנסו לסל המחזור בלחיצה על אישור."}
          />
        </Card>

        <div className="finalize-content">
          <Card className="finalize-section-card cartoon-card" variant="borderless">
            <Flex justify="space-between" align="flex-start" gap={12} wrap>
              <div>
                <Typography.Title level={2} style={{ marginBottom: 6 }}>
                  ממתינות להעברה עכשיו
                </Typography.Title>
                <Typography.Paragraph className="muted-copy" style={{ marginBottom: 0 }}>
                  החלק היחיד שיבוצע בלחיצה על אישור. כל פריט מופיע מול התיקייה שנשמרת במקומו.
                </Typography.Paragraph>
              </div>
              <StatusTag tone="warning">{summary.pendingCount}</StatusTag>
            </Flex>

            {pendingGroups.length === 0 ? (
              <Empty
                className="desktop-empty"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="אין כרגע קבוצות שממתינות למחיקה"
              />
            ) : (
              <Space orientation="vertical" size={16} style={{ width: "100%" }}>
                {pendingGroups.map((group) => (
                  <GroupCard
                    key={`pending-${group.cluster.cluster_id}`}
                    group={group}
                    sectionTitle="תיקיות שממתינות למחיקה"
                    sectionTone="warning"
                    items={group.pending}
                    openExplorer={openExplorer}
                  />
                ))}
              </Space>
            )}
          </Card>

          <Card className="finalize-section-card cartoon-card" variant="borderless">
            <Flex justify="space-between" align="flex-start" gap={12} wrap>
              <div>
                <Typography.Title level={2} style={{ marginBottom: 6 }}>
                  כבר הועברו קודם
                </Typography.Title>
                <Typography.Paragraph className="muted-copy" style={{ marginBottom: 0 }}>
                  היסטוריית הפעולות שבוצעו עד כה, יחד עם ה־keeper שנשאר בכל קבוצה כדי לאפשר השוואה חוזרת.
                </Typography.Paragraph>
              </div>
              <StatusTag tone="success">{summary.deletedCount}</StatusTag>
            </Flex>

            {historyGroups.length === 0 ? (
              <Empty
                className="desktop-empty"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="עדיין אין היסטוריית מחיקות להצגה"
              />
            ) : (
              <Space orientation="vertical" size={16} style={{ width: "100%" }}>
                {historyGroups.map((group) => (
                  <GroupCard
                    key={`history-${group.cluster.cluster_id}`}
                    group={group}
                    sectionTitle="תיקיות שכבר הועברו"
                    sectionTone="success"
                    items={group.deleted}
                    openExplorer={openExplorer}
                    showHistoryHint
                  />
                ))}
              </Space>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
