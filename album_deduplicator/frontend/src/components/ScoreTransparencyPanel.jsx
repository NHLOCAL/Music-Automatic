import React from "react";
import { Popover } from "antd";
import { Icon } from "./UI";
import { formatPercent, getRepresentativeClusterPair } from "../utils";

export function ScoreTransparencyPanel({ cluster, currentKeeperId }) {
  const pair = getRepresentativeClusterPair(cluster, currentKeeperId ?? cluster?.recommended_keeper_id);
  if (!pair) return null;

  const content = (
    <div style={{display:'flex', gap: 16, fontSize: 11, direction: 'rtl'}}>
      <div><strong>ציון סופי:</strong> {formatPercent(pair.final_score)}</div>
      <div><strong>אלגוריתם:</strong> {formatPercent(pair.algorithmic_score)}</div>
      <div><strong>ML:</strong> {pair.is_identical_by_hash ? "Hash זהה" : formatPercent(pair.ml_score)}</div>
      {pair.gemini_score && <div><strong>AI:</strong> {formatPercent(pair.gemini_score)}</div>}
    </div>
  );

  return (
    <Popover content={content} title="פירוט ציוני התאמה" placement="bottomRight">
      <div className="ide-transparency-inline" style={{cursor: 'pointer'}}>
        <Icon name="info" size={14} /> נתוני השוואה
      </div>
    </Popover>
  );
}