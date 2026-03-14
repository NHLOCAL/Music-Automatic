import { useState, useEffect, useCallback, startTransition } from "react";
import * as api from "../api";
import { getActiveKeeperId, hasExplicitKeeperDecision } from "../utils";

const INITIAL_PROGRESS = {
  step: "queued",
  stage: "queued",
  message: "ממתין",
  human_message: "ממתין לתחילת הניתוח.",
  current: 0,
  total: 1,
  percent: 0,
  warnings: [],
};

const INITIAL_PREVIEW = {
  items: [],
  total_count: 0,
  total_size_mb: 0,
  auto_selected_count: 0,
  manual_selected_count: 0,
};

function buildOptimisticPreviewAfterKeepAll(currentPreview, clusterId) {
  const safePreview = currentPreview ?? INITIAL_PREVIEW;
  const currentItems = Array.isArray(safePreview.items) ? safePreview.items : [];
  const nextItems = currentItems.filter((item) => item.cluster_id !== clusterId);

  if (nextItems.length === currentItems.length) {
    return safePreview;
  }

  const totalSizeMb = nextItems.reduce((sum, item) => sum + Number(item.estimated_size_mb ?? 0), 0);
  const autoSelectedCount = nextItems.filter((item) => item.selection_source === "auto").length;
  const manualSelectedCount = nextItems.filter((item) => item.selection_source === "user_selected").length;

  return {
    ...safePreview,
    items: nextItems,
    total_count: nextItems.length,
    total_size_mb: Number(totalSizeMb.toFixed(2)),
    auto_selected_count: autoSelectedCount,
    manual_selected_count: manualSelectedCount,
  };
}

export function useDeduplicator() {
  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(INITIAL_PROGRESS);
  const [summary, setSummary] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [allClusters, setAllClusters] = useState([]);
  const [decisions, setDecisions] = useState({});
  const [deleteSelections, setDeleteSelections] = useState({});
  const [preview, setPreview] = useState(INITIAL_PREVIEW);
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [error, setError] = useState("");
  const [successSummary, setSuccessSummary] = useState(null);
  const [selectedTab, setSelectedTab] = useState("safe");
  const refreshData = useCallback(async (sid, tab) => {
    try {
      const clusterRequests = tab === "all"
        ? [api.getClusters(sid, "all"), Promise.resolve(null)]
        : [api.getClusters(sid, tab), api.getClusters(sid, "all")];
      const [sessionData, clustersData, previewData, allClustersData] = await Promise.all([
        api.getAnalysisSession(sid),
        clusterRequests[0],
        api.getDeletePreview(sid),
        clusterRequests[1],
      ]);
      const fullClusters = tab === "all" ? clustersData.clusters : (allClustersData?.clusters ?? []);
      startTransition(() => {
        setSummary(sessionData);
        setProgress(sessionData.progress);
        setClusters(clustersData.clusters);
        setAllClusters(fullClusters);
        setPreview(previewData);
        setDecisions((prev) => {
          const next = { ...prev };
          fullClusters.forEach(c => {
            if (!(c.cluster_id in next) && c.resolution_state === "auto" && c.recommended_keeper_id) {
              next[c.cluster_id] = c.recommended_keeper_id;
            }
          });
          return next;
        });
        setDeleteSelections((prev) => {
          const next = { ...prev };
          fullClusters.forEach((cluster) => {
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
  const resetSession = useCallback(() => {
    startTransition(() => {
      setSessionId(null);
      setStatus("idle");
      setProgress(INITIAL_PROGRESS);
      setSummary(null);
      setClusters([]);
      setAllClusters([]);
      setDecisions({});
      setDeleteSelections({});
      setPreview(INITIAL_PREVIEW);
      setSelectedClusterId(null);
      setSelectedTab("safe");
      setError("");
      setSuccessSummary(null);
    });
  }, []);
  const handleDecision = async (clusterId, keeperId, deleteFolderIds = null) => {
    if (!sessionId) return;
    const cluster = clusters.find((item) => item.cluster_id === clusterId);
    const currentKeeperId = getActiveKeeperId(cluster, decisions);
    const hadExplicitDecision = hasExplicitKeeperDecision(cluster, decisions);
    const visibleFolderIds = cluster
      ? cluster.albums.filter((album) => !album.is_deleted).map((album) => album.folder_id)
      : [];
    const nextDecisions = { ...decisions, [clusterId]: keeperId };
    let nextDeleteFolderIds = [];
    if (keeperId) {
      if (deleteFolderIds !== null) {
        nextDeleteFolderIds = deleteFolderIds.filter((folderId) => folderId !== keeperId);
      } else if (
        hadExplicitDecision
        && currentKeeperId === keeperId
        && Object.prototype.hasOwnProperty.call(deleteSelections, clusterId)
      ) {
        nextDeleteFolderIds = (deleteSelections[clusterId] ?? []).filter((folderId) => folderId !== keeperId);
      } else {
        nextDeleteFolderIds = visibleFolderIds.filter((folderId) => folderId !== keeperId);
      }
    }
    const nextDeleteSelections = { ...deleteSelections, [clusterId]: nextDeleteFolderIds };
    setDecisions(nextDecisions);
    setDeleteSelections(nextDeleteSelections);
    if (!keeperId) {
      setPreview((currentPreview) => buildOptimisticPreviewAfterKeepAll(currentPreview, clusterId));
    }
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
    sessionId, setSessionId, status, setStatus, progress, summary, clusters, setClusters, allClusters, setAllClusters,
    decisions, setDecisions, deleteSelections, setDeleteSelections, preview, setPreview, selectedClusterId, setSelectedClusterId,
    error, setError, successSummary, setSuccessSummary, selectedTab, setSelectedTab, setSummary, setProgress,
    refreshData, handleDecision, resetSession
  };
}
