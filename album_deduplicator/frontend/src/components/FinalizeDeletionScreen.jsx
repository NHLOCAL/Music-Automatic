import React from "react";
import { Button, Popconfirm, Tooltip } from "antd";
import { Icon, StatusTag } from "./UI";
import { formatSizeMb, getClusterDisplayTitle } from "../utils";

export function FinalizeDeletionScreen({ workflow, onBackToReview, onBackToSetup, onExecute, isExecuting, openExplorer }) {
  const { pendingGroups, summary } = workflow;

  return (
    <div className="data-table-container">
      <div className="data-table-header">
        <div>
          <h2>אישור העברה לסל המחזור ({summary.pendingCount} תיקיות)</h2>
          <div className="finalize-header-note">הפריטים יסומנו לסל המחזור בלבד, ללא מחיקה לצמיתות.</div>
        </div>
        <div style={{display:'flex', gap: 12}}>
          <Button onClick={onBackToReview}>חזור לעריכה</Button>
          {onBackToSetup ? <Button onClick={onBackToSetup}>סריקה חדשה</Button> : null}
          <Popconfirm
            title="להעביר את הפריטים המסומנים לסל המחזור?"
            description="אפשר לחזור לעריכה אם צריך לשנות keeper או סימון מחיקה."
            okText="כן, להעביר"
            cancelText="ביטול"
            onConfirm={() => onExecute()}
            disabled={summary.pendingCount === 0}
          >
            <Button type="primary" danger loading={isExecuting} disabled={summary.pendingCount === 0}>
              בצע מחיקה למסומנים
            </Button>
          </Popconfirm>
        </div>
      </div>

      <div className="data-table-wrapper">
        <table className="pro-table">
          <thead>
            <tr>
              <th width="30%">זיהוי קבוצה</th>
              <th width="15%">איכות התאמה</th>
              <th width="25%">העותק שיישמר (Keeper)</th>
              <th width="30%">תיקייה מיועדת למחיקה (Trash)</th>
            </tr>
          </thead>
          <tbody>
            {pendingGroups.length === 0 ? (
              <tr><td colSpan="4" style={{textAlign:'center', padding: 40}}>אין פריטים להעברה.</td></tr>
            ) : (
              pendingGroups.map((group) => {
                const score = group.cluster.pairs?.[0] ? `${group.cluster.pairs[0].final_score.toFixed(1)}%` : "N/A";
                
                return group.pending.map((item, idx) => (
                  <tr key={item.folder_id}>
                    {idx === 0 && (
                      <>
                        <td rowSpan={group.pending.length}>
                          <div style={{fontWeight: 600}}>{getClusterDisplayTitle(group.cluster)}</div>
                          <div style={{fontSize: 11, color: '#666', marginTop: 4}}>{group.cluster.human_summary}</div>
                        </td>
                        <td rowSpan={group.pending.length}>
                          <StatusTag tone={group.cluster.confidence_bucket === 'safe' ? 'success' : 'warning'}>{score}</StatusTag>
                        </td>
                        <td rowSpan={group.pending.length}>
                          <div style={{display:'flex', flexDirection:'column', gap:4}}>
                            <strong>{group.keeper.name}</strong>
                            <div className="path-cell">{group.keeper.path}</div>
                            <Tooltip title="פתח בתיקייה"><Icon name="folder" size={14} style={{cursor:'pointer', color:'#0060df'}} onClick={() => openExplorer(group.keeper.path)}/></Tooltip>
                          </div>
                        </td>
                      </>
                    )}
                    <td>
                      <div style={{display:'flex', flexDirection:'column', gap:4}}>
                        <span style={{textDecoration: 'line-through', color: '#cf222e'}}>{item.name}</span>
                        <div className="path-cell">{item.path}</div>
                        <div style={{fontSize: 11, color: '#666'}}>
                          {formatSizeMb(item.estimated_size_mb)} • {item.file_count} קבצים
                        </div>
                      </div>
                    </td>
                  </tr>
                ));
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
