import React from "react";
import { Badge } from "./UI";

function getCurrentKeeperId(cluster, decisions) {
  return decisions[cluster.cluster_id]
    ?? (cluster.resolution_state === "auto" ? cluster.recommended_keeper_id : null);
}

export function ClusterList({
  clusters,
  selectedClusterId,
  setSelectedClusterId,
  decisions,
  deleteSelections,
  handleDecision,
}) {
  if (!clusters.length) {
    return <div className="empty-list">אין תוצאות להצגה בקטגוריה זו.</div>;
  }

  return (
    <div className="cluster-list">
      {clusters.map((cluster) => {
        const isActive = cluster.cluster_id === selectedClusterId;
        const currentKeeperId = getCurrentKeeperId(cluster, decisions);
        const currentDeleteSelection = deleteSelections[cluster.cluster_id] ?? cluster.selected_delete_folder_ids ?? [];
        const albums = cluster.albums.filter((album) => !album.is_deleted);
        const keeperAlbum = albums.find((album) => album.folder_id === currentKeeperId) ?? null;

        return (
          <div
            key={cluster.cluster_id}
            className={`cluster-card card ${isActive ? "active" : ""}`}
            role="button"
            tabIndex={0}
            onClick={() => setSelectedClusterId(cluster.cluster_id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setSelectedClusterId(cluster.cluster_id);
              }
            }}
          >
            <div className="cluster-card-header">
              <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
                {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
              </Badge>
              <span className="highlight-text">
                {keeperAlbum ? `נשמר: ${keeperAlbum.name}` : "טרם נבחר Keeper"}
              </span>
            </div>

            <h3 className="cluster-title">{cluster.human_summary}</h3>
            <p className="cluster-summary-line">
              {albums.length} עותקים פעילים, {currentDeleteSelection.length} מסומנים למחיקה.
            </p>

            <div className="cluster-chip-row">
              {albums.slice(0, 3).map((album) => {
                const isSelected = currentKeeperId === album.folder_id;
                return (
                  <span key={album.folder_id} className={`cluster-mini-chip ${isSelected ? "selected" : ""}`}>
                    {album.name}
                  </span>
                );
              })}
              {albums.length > 3 && <span className="cluster-mini-chip">+{albums.length - 3}</span>}
            </div>

            <div className="cluster-actions" onClick={(event) => event.stopPropagation()}>
              {albums.map((album) => {
                const isSelected = currentKeeperId === album.folder_id;
                return (
                  <button
                    key={album.folder_id}
                    type="button"
                    className={`choice-btn ${isSelected ? "selected" : ""}`}
                    onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                  >
                    {isSelected ? `נשמר: ${album.name}` : `שמור ${album.name}`}
                  </button>
                );
              })}
              <button
                type="button"
                className={`choice-btn ${!currentKeeperId ? "selected" : ""}`}
                onClick={() => handleDecision(cluster.cluster_id, null, [])}
              >
                דלג
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
