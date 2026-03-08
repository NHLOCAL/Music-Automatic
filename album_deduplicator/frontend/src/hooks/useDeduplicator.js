import { useState, useEffect, useCallback, startTransition } from "react";
import * as api from "../api";
export function useDeduplicator() {
  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState({
    step: "queued", stage: "queued", message: "ממתין", human_message: "ממתין לתחילת הניתוח.", current: 0, total: 1, percent: 0, warnings: []
  });
  const [summary, setSummary] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [decisions, setDecisions] = useState({});
  const [deleteSelections, setDeleteSelections] = useState({});
  const [preview, setPreview] = useState({ items: [], total_count: 0, total_size_mb: 0, auto_selected_count: 0, manual_selected_count: 0 });
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [error, setError] = useState("");
  const [successSummary, setSuccessSummary] = useState(null);
  const [selectedTab, setSelectedTab] = useState("safe");
  const refreshData = useCallback(async (sid, tab) => {
    try {
      const [sessionData, clustersData, previewData] = await Promise.all([
        api.getAnalysisSession(sid),
        api.getClusters(sid, tab),
        api.getDeletePreview(sid)
      ]);
      startTransition(() => {
        setSummary(sessionData);
        setProgress(sessionData.progress);
        setClusters(clustersData.clusters);
        setPreview(previewData);
        setDecisions((prev) => {
          const next = { ...prev };
          clustersData.clusters.forEach(c => {
            if (!(c.cluster_id in next)) {
              next[c.cluster_id] = c.resolution_state === "auto" ? c.recommended_keeper_id : null;
            }
          });
          return next;
        });
        setDeleteSelections((prev) => {
          const next = { ...prev };
          clustersData.clusters.forEach((cluster) => {
            next[cluster.cluster_id] = cluster.selected_delete_folder_ids ?? [];
          });
          return next;
        });
        setSelectedClusterId(prev => clustersData.clusters.some(c => c.cluster_id === prev) ? prev : clustersData.clusters[0]?.cluster_id ?? null);
      });
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => {
    if (!sessionId) return;
    const events = api.getEventSource(sessionId);
    events.addEventListener("progress", (e) => {
      setProgress(JSON.parse(e.data));
      setStatus("running");
    });
    events.addEventListener("completed", async () => {
      setStatus("completed");
      await refreshData(sessionId, selectedTab);
    });
    events.addEventListener("failed", (e) => {
      setStatus("failed");
      setError(JSON.parse(e.data).error ?? "הניתוח נכשל.");
    });
    events.addEventListener("delete_execution", async (e) => {
      const data = JSON.parse(e.data);
      setSuccessSummary({ moved_count: data.moved_count, total_size_mb: data.total_size_mb ?? 0 });
      await refreshData(sessionId, selectedTab);
    });
    events.addEventListener("end", () => events.close());
    return () => events.close();
  }, [sessionId, selectedTab, refreshData]);
  useEffect(() => {
    if (sessionId && status === "completed") {
      refreshData(sessionId, selectedTab);
    }
  }, [selectedTab, sessionId, status, refreshData]);
  const handleDecision = async (clusterId, keeperId, deleteFolderIds = null) => {
    if (!sessionId) return;
    const cluster = clusters.find((item) => item.cluster_id === clusterId);
    const currentKeeperId = decisions[clusterId] ?? (cluster?.resolution_state === "auto" ? cluster?.recommended_keeper_id : null);
    const visibleFolderIds = cluster
      ? cluster.albums.filter((album) => !album.is_deleted).map((album) => album.folder_id)
      : [];
    const nextDecisions = { ...decisions, [clusterId]: keeperId };
    let nextDeleteFolderIds = [];
    if (keeperId) {
      if (deleteFolderIds !== null) {
        nextDeleteFolderIds = deleteFolderIds.filter((folderId) => folderId !== keeperId);
      } else if (currentKeeperId === keeperId && Object.prototype.hasOwnProperty.call(deleteSelections, clusterId)) {
        nextDeleteFolderIds = (deleteSelections[clusterId] ?? []).filter((folderId) => folderId !== keeperId);
      } else {
        nextDeleteFolderIds = visibleFolderIds.filter((folderId) => folderId !== keeperId);
      }
    }
    const nextDeleteSelections = { ...deleteSelections, [clusterId]: nextDeleteFolderIds };
    setDecisions(nextDecisions);
    setDeleteSelections(nextDeleteSelections);
    try {
      const payload = {
        decisions: Object.entries(nextDecisions).map(([cid, kid]) => ({
          cluster_id: cid,
          keeper_id: kid,
          delete_folder_ids: kid ? (nextDeleteSelections[cid] ?? []) : [],
        })),
      };
      const nextPreview = await api.updateDecisions(sessionId, payload);
      setPreview(nextPreview);
      await refreshData(sessionId, selectedTab);
    } catch (err) {
      setError(err.message);
    }
  };
  return {
    sessionId, setSessionId, status, setStatus, progress, summary, clusters, setClusters,
    decisions, setDecisions, deleteSelections, setDeleteSelections, preview, setPreview, selectedClusterId, setSelectedClusterId,
    error, setError, successSummary, setSuccessSummary, selectedTab, setSelectedTab,
    refreshData, handleDecision
  };
}
