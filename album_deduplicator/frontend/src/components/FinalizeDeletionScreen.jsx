import React from "react";
import { Badge, Button } from "./UI";
import { formatSizeMb, getClusterDisplayTitle } from "../utils";

function PendingFolderRow({ item, keeperName, openExplorer }) {
  return (
    <div className="finalize-pending-row">
      <div className="finalize-pending-main">
        <div className="finalize-pending-title-row">
          <div className="finalize-pending-name">{item.name}</div>
          <Badge tone={item.status_tone ?? "warning"}>{item.status_label}</Badge>
        </div>
        <div className="finalize-pending-path" title={item.path}>{item.path}</div>
        <div className="finalize-pending-meta">
          <span>{item.file_count} קבצים</span>
          <span>•</span>
          <span>{formatSizeMb(item.estimated_size_mb ?? item.total_size_mb)}</span>
          {keeperName ? (
            <>
              <span>•</span>
              <span>יישמר מול {keeperName}</span>
            </>
          ) : null}
        </div>
      </div>
      <Button variant="secondary" size="sm" onClick={() => openExplorer(item.path)}>
        פתח
      </Button>
    </div>
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
      <div className="finalize-header compact">
        <div>
          <div className="finalize-eyebrow">שלב 3 מתוך 3</div>
          <h1>אישור העברה לסל המחזור</h1>
          <p>מוצגות כאן רק הקבוצות שיש בהן תיקיות שממתינות כרגע למחיקה המרוכזת.</p>
        </div>
        <div className="finalize-header-actions">
          <Button variant="secondary" size="lg" onClick={onBackToReview}>חזור לסקירה</Button>
          <Button variant="secondary" size="lg" onClick={onBackToSetup}>סריקה חדשה</Button>
        </div>
      </div>

      <div className="finalize-layout compact">
        <aside className="finalize-sidebar">
          <section className="finalize-sidebar-card compact emphasize">
            <div className="finalize-sidebar-kicker">מוכנות למחיקה</div>
            <div className="finalize-sidebar-primary">
              <strong>{summary.pendingCount}</strong>
              <span>תיקיות ממתינות</span>
            </div>
            <div className="finalize-sidebar-secondary">
              <span>{formatSizeMb(summary.pendingSizeMb)}</span>
              <span>•</span>
              <span>{summary.visibleGroupCount} קבוצות פעילות</span>
            </div>
            <div className="finalize-sidebar-note">
              {summary.autoSelectedCount > 0 ? `${summary.autoSelectedCount} נבחרו אוטומטית` : "כל הפריטים נבחרו ידנית"}
              {summary.manualSelectedCount > 0 ? ` • ${summary.manualSelectedCount} נבחרו ידנית` : ""}
            </div>
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

          <section className="finalize-sidebar-card compact">
            <h3>מה לא מוצג כאן</h3>
            <div className="finalize-kpi-list compact">
              <div className="finalize-kpi-row">
                <span>קבוצות שכבר הושלמו</span>
                <strong>{summary.allGroupCount - summary.visibleGroupCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>תיקיות שכבר הועברו</span>
                <strong>{summary.deletedCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>עותקי keeper שנשארים</span>
                <strong>{summary.keeperCount}</strong>
              </div>
            </div>
          </section>
        </aside>

        <div className="finalize-groups compact">
          {groups.length === 0 ? (
            <div className="finalize-empty-state-card">
              <h3>אין כרגע קבוצות שממתינות למחיקה</h3>
              <p>כל הקבוצות הפעילות כבר טופלו, או שאין כרגע תיקיות שסומנו להעברה המרוכזת.</p>
            </div>
          ) : (
            groups.map((group) => (
              <article key={group.cluster.cluster_id} className="finalize-group-card compact">
                <div className="finalize-group-head compact">
                  <div className="finalize-group-copy">
                    <div className="finalize-group-title-row">
                      <h3>{getClusterDisplayTitle(group.cluster)}</h3>
                      <Badge tone={group.status.tone}>{group.status.label}</Badge>
                    </div>
                    <div className="finalize-group-summary-row">
                      <span>{group.pendingCount} ממתינות</span>
                      <span>•</span>
                      <span>{formatSizeMb(group.pendingSizeMb)}</span>
                      {group.keeper ? (
                        <>
                          <span>•</span>
                          <span>נשמר: {group.keeper.name}</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="finalize-pending-list">
                  {group.pending.map((item) => (
                    <PendingFolderRow
                      key={item.folder_id}
                      item={item}
                      keeperName={group.keeper?.name ?? item.keeper_folder_name ?? null}
                      openExplorer={openExplorer}
                    />
                  ))}
                </div>
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
