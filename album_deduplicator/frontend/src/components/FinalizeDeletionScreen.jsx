import React from "react";
import { Badge, Button } from "./UI";
import { formatSizeMb, getClusterDisplayTitle } from "../utils";

function FolderRow({ item, tone = "neutral", actionLabel, onAction, actionTitle, subtitle }) {
  return (
    <div className={`finalize-folder-row tone-${tone}`}>
      <div className="finalize-folder-copy">
        <div className="finalize-folder-title-row">
          <div className="finalize-folder-name">{item.name}</div>
          {item.status_label ? <Badge tone={item.status_tone ?? tone}>{item.status_label}</Badge> : null}
        </div>
        <div className="finalize-folder-path" title={item.path}>{item.path}</div>
        <div className="finalize-folder-meta">
          <span>{item.file_count} קבצים</span>
          <span>•</span>
          <span>{formatSizeMb(item.estimated_size_mb ?? item.total_size_mb)}</span>
          {subtitle ? (
            <>
              <span>•</span>
              <span>{subtitle}</span>
            </>
          ) : null}
        </div>
        {item.failure_message ? (
          <div className="finalize-folder-note">{item.failure_message}</div>
        ) : null}
      </div>
      {onAction ? (
        <Button variant="secondary" size="sm" onClick={onAction} title={actionTitle}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

function SectionCard({ title, count, tone = "neutral", children, emptyState }) {
  return (
    <section className={`finalize-section-card tone-${tone}`}>
      <div className="finalize-section-head">
        <h4>{title}</h4>
        <Badge tone={tone}>{count}</Badge>
      </div>
      {count > 0 ? children : <div className="finalize-empty-copy">{emptyState}</div>}
    </section>
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
  const { groups, summary } = workflow;
  const hasPending = summary.pendingCount > 0;

  return (
    <div className="finalize-shell">
      <div className="finalize-header">
        <div>
          <div className="finalize-eyebrow">שלב 3 מתוך 3</div>
          <h1>העברה סופית לסל המחזור</h1>
          <p>
            זהו שלב האישור העצמאי לפני ההעברה בפועל. כאן רואים בצורה מרוכזת מה יועבר,
            מה כבר הועבר בשלבים קודמים, ואיזה עותק נשאר בכל קבוצה.
          </p>
        </div>
        <div className="finalize-header-actions">
          <Button variant="secondary" size="lg" onClick={onBackToReview}>חזור לסקירה</Button>
          <Button variant="secondary" size="lg" onClick={onBackToSetup}>סריקה חדשה</Button>
        </div>
      </div>

      <div className="finalize-overview-grid">
        <div className="finalize-overview-card is-danger">
          <div className="finalize-overview-value">{summary.pendingCount}</div>
          <div className="finalize-overview-label">ממתינות להעברה</div>
          <div className="finalize-overview-subcopy">{formatSizeMb(summary.pendingSizeMb)}</div>
        </div>
        <div className="finalize-overview-card is-success">
          <div className="finalize-overview-value">{summary.deletedCount}</div>
          <div className="finalize-overview-label">כבר הועברו</div>
          <div className="finalize-overview-subcopy">{formatSizeMb(summary.deletedSizeMb)}</div>
        </div>
        <div className="finalize-overview-card">
          <div className="finalize-overview-value">{summary.keeperCount}</div>
          <div className="finalize-overview-label">עותקי keeper שנשמרים</div>
          <div className="finalize-overview-subcopy">עותק אחד פעיל לכל קבוצה מוכרעת</div>
        </div>
        <div className="finalize-overview-card">
          <div className="finalize-overview-value">{summary.additionalKeptCount}</div>
          <div className="finalize-overview-label">עותקים שנשארים כרגע</div>
          <div className="finalize-overview-subcopy">
            {summary.failedCount > 0
              ? `${summary.failedCount} ניסיונות העברה נכשלו ודורשים תשומת לב`
              : summary.partiallyCompletedClusters > 0
                ? `${summary.partiallyCompletedClusters} קבוצות בוצעו חלקית`
                : "נשארו מחוץ למחיקה המרוכזת"}
          </div>
        </div>
      </div>

      <div className="finalize-layout">
        <aside className="finalize-sidebar">
          <section className="finalize-sidebar-card">
            <h3>בדיקת בטיחות</h3>
            <p>כל ההעברות מתבצעות אל סל המחזור בלבד. אין מחיקה לצמיתות בשלב הזה.</p>
            <div className="finalize-kpi-list">
              <div className="finalize-kpi-row">
                <span>נבחרו אוטומטית</span>
                <strong>{summary.autoSelectedCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>נבחרו ידנית</span>
                <strong>{summary.manualSelectedCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>קבוצות ללא keeper</span>
                <strong>{summary.unresolvedClusters}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>כשלי העברה פתוחים</span>
                <strong>{summary.failedCount}</strong>
              </div>
            </div>
          </section>

          <section className="finalize-sidebar-card emphasize">
            <h3>הפעולה הבאה</h3>
            <p>
              {hasPending
                ? `בלחיצה אחת יועברו ${summary.pendingCount} תיקיות לסל המחזור.`
                : "אין כרגע תיקיות שממתינות להעברה. אפשר לחזור לסקירה או להתחיל סריקה חדשה."}
            </p>
            <Button
              variant="danger"
              size="lg"
              onClick={onExecute}
              disabled={!hasPending || isExecuting}
              style={{ width: "100%" }}
            >
              {isExecuting
                ? "מעביר לסל המחזור..."
                : hasPending
                  ? `העבר ${summary.pendingCount} תיקיות לסל המחזור`
                  : "אין פריטים להעברה"}
            </Button>
          </section>
        </aside>

        <div className="finalize-groups">
          {groups.map((group) => (
            <article key={group.cluster.cluster_id} className="finalize-group-card">
              <div className="finalize-group-head">
                <div>
                  <div className="finalize-group-title-row">
                    <h3>{getClusterDisplayTitle(group.cluster)}</h3>
                    <Badge tone={group.status.tone}>{group.status.label}</Badge>
                  </div>
                  <p>{group.cluster.human_summary}</p>
                </div>
                <div className="finalize-group-stats">
                  <span>{group.totalAlbums} עותקים בקבוצה</span>
                  <span>•</span>
                  <span>{group.pendingCount} ממתינים</span>
                  <span>•</span>
                  <span>{group.deletedCount} הועברו</span>
                </div>
              </div>

              <div className="finalize-sections-grid">
                <SectionCard title="יישארו" count={group.keeper ? 1 + group.additionalKeptCopies.length : group.additionalKeptCopies.length} tone="success" emptyState="לא סומן עותק לשמירה בקבוצה זו עדיין.">
                  <div className="finalize-section-list">
                    {group.keeper ? (
                      <FolderRow
                        item={{ ...group.keeper, status_label: "עותק נשמר", status_tone: "success" }}
                        tone="success"
                        actionLabel="פתח תיקייה"
                        actionTitle="פתח תיקייה באקספלורר"
                        onAction={() => openExplorer(group.keeper.path)}
                        subtitle="העותק הפעיל שנשמר"
                      />
                    ) : null}
                    {group.additionalKeptCopies.map((item) => (
                      <FolderRow
                        key={item.folder_id}
                        item={{ ...item, status_label: "נשאר כרגע", status_tone: "neutral" }}
                        actionLabel="פתח תיקייה"
                        actionTitle="פתח תיקייה באקספלורר"
                        onAction={() => openExplorer(item.path)}
                        subtitle="לא נכלל כרגע במחיקה"
                      />
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="ממתינות להעברה" count={group.pendingCount} tone="warning" emptyState="אין כרגע תיקיות ממתינות להעברה בקבוצה זו.">
                  <div className="finalize-section-list">
                    {group.pending.map((item) => (
                      <FolderRow
                        key={item.folder_id}
                        item={item}
                        tone="warning"
                        actionLabel="פתח תיקייה"
                        actionTitle="פתח תיקייה באקספלורר"
                        onAction={() => openExplorer(item.path)}
                        subtitle={`יישמר מול ${group.keeper?.name ?? item.keeper_folder_name ?? "עותק אחר"}`}
                      />
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="כבר הועברו" count={group.deletedCount + group.failedCount} tone={group.failedCount > 0 ? "danger" : "neutral"} emptyState="עדיין לא בוצעה העברה מתוך קבוצה זו.">
                  <div className="finalize-section-list">
                    {group.deleted.map((item) => (
                      <FolderRow
                        key={item.folder_id}
                        item={item}
                        tone="success"
                        actionLabel="פתח keeper"
                        actionTitle="פתח את התיקייה שנשמרה"
                        onAction={group.keeper ? () => openExplorer(group.keeper.path) : undefined}
                        subtitle="הועבר בהצלחה לסל המחזור"
                      />
                    ))}
                    {group.failed.map((item) => (
                      <FolderRow
                        key={item.folder_id}
                        item={item}
                        tone="danger"
                        actionLabel="פתח תיקייה"
                        actionTitle="פתח תיקייה באקספלורר"
                        onAction={() => openExplorer(item.path)}
                        subtitle="ההעברה נכשלה בניסיון האחרון"
                      />
                    ))}
                  </div>
                </SectionCard>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
