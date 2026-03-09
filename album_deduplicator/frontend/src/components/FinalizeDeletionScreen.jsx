import React from "react";
import { Alert, Button, Card, Empty, Flex, Space, Statistic, Typography } from "antd";

import { Icon, StatusTag } from "./UI";
import { formatSizeMb, getClusterDisplayTitle } from "../utils";

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
      <Space orientation="vertical" size={10} style={{ width: "100%" }}>
        <Typography.Text type="secondary">העותק שנשמר</Typography.Text>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {keeper.name}
        </Typography.Title>
        <div className="finalize-path" title={keeper.path}>{keeper.path}</div>
        <div className="finalize-item-meta">
          <span>{keeper.file_count} קבצים</span>
          <span>{formatSizeMb(keeper.total_size_mb)}</span>
        </div>
        <Button type="default" icon={<Icon name="folder" size={14} />} onClick={() => openExplorer(keeper.path)}>
          פתח keeper
        </Button>
      </Space>
    </Card>
  );
}

function ItemCard({ item, keeper, variant = "pending", openExplorer }) {
  const isHistory = variant === "history";

  return (
    <Card className={`finalize-item-card cartoon-panel ${isHistory ? "is-history" : ""}`} variant="borderless">
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

  return (
    <Card className="finalize-group-card cartoon-card" variant="borderless">
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

      <Space orientation="vertical" size={16} style={{ width: "100%" }}>
        <KeeperPanel keeper={group.keeper} openExplorer={openExplorer} />
        <Alert
          type={showHistoryHint ? "success" : "warning"}
          showIcon
          title={sectionTitle}
          description={
            showHistoryHint
              ? "אלו תיקיות שכבר הועברו לסל המחזור, לצד העותק שנשמר להשוואה והקשר."
              : "אלו התיקיות שייכנסו עכשיו לסל המחזור אם תאשר את הפעולה."
          }
        />
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

  return (
    <div className="finalize-shell">
      <Card className="cartoon-card" variant="borderless" style={{ marginBottom: 18 }}>
        <Flex justify="space-between" align="flex-start" gap={18} wrap>
          <div>
            <div className="soft-kicker">
              <Icon name="compare" size={14} />
              שלב 3 מתוך 3
            </div>
            <Typography.Title level={1} style={{ marginBottom: 8 }}>
              מרכז ההעברה וההשוואה
            </Typography.Title>
            <Typography.Paragraph className="page-subtitle" style={{ marginBottom: 0, maxWidth: 760 }}>
              כאן רואים גם מה עומד להימחק עכשיו וגם מה כבר נמחק קודם, תמיד לצד העותק שנשמר.
              כך אפשר לאשר בביטחון, או לחזור לבדוק את ההחלטות לפני ההעברה.
            </Typography.Paragraph>
          </div>
          <div className="screen-actions">
            <Button type="default" size="large" icon={<Icon name="compare" size={16} />} onClick={onBackToReview}>
              חזור לסקירה
            </Button>
            <Button type="default" size="large" icon={<Icon name="arrow-left" size={16} />} onClick={onBackToSetup}>
              סריקה חדשה
            </Button>
          </div>
        </Flex>
      </Card>

      <div className="finalize-layout">
        <aside className="finalize-sidebar">
          <Card className="cartoon-card" variant="borderless">
            <Space orientation="vertical" size={14} style={{ width: "100%" }}>
              <div className="soft-kicker">
                <Icon name="trash" size={14} />
                מבט מהיר
              </div>
              <Statistic title="תיקיות ממתינות להעברה" value={summary.pendingCount} />
              <Typography.Text type="secondary">
                {formatSizeMb(summary.pendingSizeMb)} • {summary.pendingGroupCount} קבוצות פעילות
              </Typography.Text>
              <Typography.Text type="secondary">
                {summary.autoSelectedCount > 0 ? `${summary.autoSelectedCount} נבחרו אוטומטית` : "אין כרגע בחירות אוטומטיות"}
                {summary.manualSelectedCount > 0 ? ` • ${summary.manualSelectedCount} נבחרו ידנית` : ""}
              </Typography.Text>
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
            </Space>
          </Card>

          <Card className="cartoon-card" variant="borderless">
            <Typography.Title level={4}>מה כבר קרה</Typography.Title>
            <div className="finalize-kpi-grid">
              {[
                ["תיקיות שכבר הועברו", summary.deletedCount],
                ["קבוצות עם היסטוריית מחיקה", summary.historyGroupCount],
                ["עותקי keeper שנשמרו", summary.keeperCount],
                ["העברות שנכשלו", summary.failedCount],
              ].map(([label, value]) => (
                <Card key={label} className="finalize-kpi-card cartoon-panel" variant="borderless">
                  <Typography.Text>{label}</Typography.Text>
                  <Typography.Text strong>{value}</Typography.Text>
                </Card>
              ))}
            </div>
          </Card>
        </aside>

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
