import React from "react";
import { Badge, Button, Icon } from "./UI";
import { formatSizeMb, getClusterDisplayTitle } from "../utils";

function KeeperPanel({ keeper, openExplorer }) {
  if (!keeper) {
    return (
      <div className="finalize-keeper-panel is-warning">
        <div className="finalize-keeper-copy">
          <div className="finalize-keeper-label">עותק נשמר</div>
          <div className="finalize-keeper-name">עדיין לא נבחר keeper לקבוצה זו</div>
        </div>
      </div>
    );
  }

  return (
    <div className="finalize-keeper-panel">
      <div className="finalize-keeper-copy">
        <div className="finalize-keeper-label">העותק שנשמר</div>
        <div className="finalize-keeper-name">{keeper.name}</div>
        <div className="finalize-keeper-path" title={keeper.path}>{keeper.path}</div>
      </div>
      <div className="finalize-keeper-meta">
        <span>{keeper.file_count} קבצים</span>
        <span>•</span>
        <span>{formatSizeMb(keeper.total_size_mb)}</span>
      </div>
      <Button variant="secondary" size="sm" onClick={() => openExplorer(keeper.path)}>
        <Icon name="folder" size={14} />
        פתח keeper
      </Button>
    </div>
  );
}

function ItemRow({ item, keeper, variant = "pending", openExplorer }) {
  const isHistory = variant === "history";
  const rowClass = isHistory ? "finalize-item-row is-history" : "finalize-item-row";

  return (
    <div className={rowClass}>
      <div className="finalize-item-copy">
        <div className="finalize-item-title-row">
          <div className="finalize-item-name">{item.name}</div>
          <Badge tone={item.status_tone ?? (isHistory ? "success" : "warning")}>{item.status_label}</Badge>
        </div>
        <div className="finalize-item-path" title={item.path}>{item.path}</div>
        <div className="finalize-item-meta">
          <span>{item.file_count} קבצים</span>
          <span>•</span>
          <span>{formatSizeMb(item.estimated_size_mb ?? item.total_size_mb)}</span>
          {keeper ? (
            <>
              <span>•</span>
              <span>{isHistory ? `נמחק מול ${keeper.name}` : `יישמר מול ${keeper.name}`}</span>
            </>
          ) : null}
        </div>
        {item.failure_message ? (
          <div className="finalize-item-note">{item.failure_message}</div>
        ) : null}
      </div>
      <div className="finalize-item-actions">
        {!isHistory ? (
          <Button variant="secondary" size="sm" onClick={() => openExplorer(item.path)}>
            <Icon name="folder" size={14} />
            פתח תיקייה
          </Button>
        ) : null}
        {keeper ? (
          <Button variant="ghost" size="sm" onClick={() => openExplorer(keeper.path)}>
            <Icon name="shield" size={14} />
            פתח keeper
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function GroupCard({ group, sectionTitle, sectionTone, items, openExplorer, showHistoryHint = false }) {
  if (!items.length) return null;

  return (
    <article className="finalize-group-card rich">
      <div className="finalize-group-head rich">
        <div className="finalize-group-copy">
          <div className="finalize-group-title-row">
            <h3>{getClusterDisplayTitle(group.cluster)}</h3>
            <Badge tone={group.status.tone}>{group.status.label}</Badge>
          </div>
          <div className="finalize-group-summary-row">
            <span>{group.cluster.human_summary}</span>
          </div>
        </div>
        <div className="finalize-group-side-meta">
          <div>{sectionTitle}</div>
          <strong>{items.length}</strong>
        </div>
      </div>

      <div className="finalize-group-body">
        <KeeperPanel keeper={group.keeper} openExplorer={openExplorer} />

        <div className={`finalize-section-block tone-${sectionTone}`}>
          <div className="finalize-section-block-head">
            <h4>{sectionTitle}</h4>
            <Badge tone={sectionTone}>{items.length}</Badge>
          </div>
          {showHistoryHint ? (
            <p className="finalize-section-hint">אלו תיקיות שכבר הועברו לסל המחזור, לצד העותק שנשמר להשוואה והקשר.</p>
          ) : (
            <p className="finalize-section-hint">אלו התיקיות שייכנסו עכשיו לסל המחזור אם תאשר את הפעולה.</p>
          )}
          <div className="finalize-item-list">
            {items.map((item) => (
              <ItemRow
                key={item.folder_id}
                item={item}
                keeper={group.keeper}
                variant={showHistoryHint ? "history" : "pending"}
                openExplorer={openExplorer}
              />
            ))}
          </div>
        </div>
      </div>
    </article>
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
      <div className="finalize-header rich">
        <div>
          <div className="finalize-eyebrow">שלב 3 מתוך 3</div>
          <h1>מרכז ההעברה וההשוואה</h1>
          <p>
            כאן רואים גם מה עומד להימחק עכשיו וגם מה כבר נמחק קודם, תמיד לצד העותק שנשמר.
            כך אפשר לאשר בביטחון, או לחזור לבדוק את ההחלטות לפני ההעברה.
          </p>
        </div>
        <div className="finalize-header-actions">
          <Button variant="secondary" size="lg" onClick={onBackToReview}>
            <Icon name="compare" size={16} />
            חזור לסקירה
          </Button>
          <Button variant="secondary" size="lg" onClick={onBackToSetup}>
            <Icon name="arrow-left" size={16} />
            סריקה חדשה
          </Button>
        </div>
      </div>

      <div className="finalize-layout rich">
        <aside className="finalize-sidebar">
          <section className="finalize-sidebar-card rich emphasize">
            <div className="finalize-sidebar-kicker">מבט מהיר</div>
            <div className="finalize-sidebar-primary">
              <strong>{summary.pendingCount}</strong>
              <span>תיקיות ממתינות להעברה</span>
            </div>
            <div className="finalize-sidebar-secondary">
              <span>{formatSizeMb(summary.pendingSizeMb)}</span>
              <span>•</span>
              <span>{summary.pendingGroupCount} קבוצות פעילות</span>
            </div>
            <div className="finalize-sidebar-note">
              {summary.autoSelectedCount > 0 ? `${summary.autoSelectedCount} נבחרו אוטומטית` : "אין כרגע בחירות אוטומטיות"}
              {summary.manualSelectedCount > 0 ? ` • ${summary.manualSelectedCount} נבחרו ידנית` : ""}
            </div>
            <Button
              variant="danger"
              size="lg"
              onClick={onExecute}
              disabled={!hasPending || isExecuting}
              style={{ width: "100%" }}
            >
              <Icon name="trash" size={16} />
              {isExecuting
                ? "מעביר לסל המחזור..."
                : hasPending
                  ? `העבר ${summary.pendingCount} תיקיות לסל המחזור`
                  : "אין פריטים להעברה"}
            </Button>
          </section>

          <section className="finalize-sidebar-card rich">
            <h3>מה כבר קרה</h3>
            <div className="finalize-kpi-list">
              <div className="finalize-kpi-row">
                <span>תיקיות שכבר הועברו</span>
                <strong>{summary.deletedCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>קבוצות עם היסטוריית מחיקה</span>
                <strong>{summary.historyGroupCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>עותקי keeper שנשמרו</span>
                <strong>{summary.keeperCount}</strong>
              </div>
              <div className="finalize-kpi-row">
                <span>העברות שנכשלו</span>
                <strong>{summary.failedCount}</strong>
              </div>
            </div>
          </section>
        </aside>

        <div className="finalize-content">
          <section className="finalize-major-section">
            <div className="finalize-major-head">
              <div>
                <h2>ממתינות להעברה עכשיו</h2>
                <p>החלק היחיד שיבוצע בלחיצה על אישור. כל פריט מופיע מול התיקייה שנשמרת במקומו.</p>
              </div>
              <Badge tone="warning">{summary.pendingCount}</Badge>
            </div>
            {pendingGroups.length === 0 ? (
              <div className="finalize-empty-state-card">
                <h3>אין כרגע קבוצות שממתינות למחיקה</h3>
                <p>הכל כבר טופל, או שאין כרגע תיקיות שסומנו להעברה המרוכזת.</p>
              </div>
            ) : (
              <div className="finalize-group-list">
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
              </div>
            )}
          </section>

          <section className="finalize-major-section">
            <div className="finalize-major-head">
              <div>
                <h2>כבר הועברו קודם</h2>
                <p>היסטוריית הפעולות שבוצעו עד כה, יחד עם ה־keeper שנשאר בכל קבוצה כדי לאפשר השוואה חוזרת.</p>
              </div>
              <Badge tone="success">{summary.deletedCount}</Badge>
            </div>
            {historyGroups.length === 0 ? (
              <div className="finalize-empty-state-card subtle">
                <h3>עדיין אין היסטוריית מחיקות להצגה</h3>
                <p>ברגע שתבוצע העברה, תראה כאן את הפריטים שנמחקו ואת התיקיות שנשמרו מולם.</p>
              </div>
            ) : (
              <div className="finalize-group-list">
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
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
