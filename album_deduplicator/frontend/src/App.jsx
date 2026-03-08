import React, { useEffect, useState } from "react";
import { useDeduplicator } from "./hooks/useDeduplicator";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import * as api from "./api";
import { getRuntimeInfo, getRuntimeSnapshot, openDesktopPath, pickPreferredRoot, pickScanFolders } from "./desktop";
import { SetupScreen } from "./components/SetupScreen";
import { ScanningScreen } from "./components/ScanningScreen";
import { SummaryScreen } from "./components/SummaryScreen";
import { ClusterList } from "./components/ClusterList";
import { DiffWorkspace } from "./components/DiffWorkspace";
import { DeletePreview } from "./components/DeletePreview";
import { FinalizeDeletionScreen } from "./components/FinalizeDeletionScreen";
import { ConfirmModal } from "./components/UI";
import { buildDeletionWorkflowModel, getActiveKeeperId, hasClusterDecision, mergeDeleteAttemptResults } from "./utils";

function normalizeFolderPaths(entries) {
  return entries.map((entry) => entry.path.trim()).filter(Boolean);
}

function mergeFolderInputs(currentEntries, nextPaths) {
  const uniqueNextPaths = Array.from(new Set(nextPaths.map((item) => item.trim()).filter(Boolean)));
  if (!uniqueNextPaths.length) return currentEntries;
  const nextEntries = currentEntries.map((entry) => ({ ...entry }));
  const existingPaths = new Set(nextEntries.map((entry) => entry.path.trim()).filter(Boolean));
  
  uniqueNextPaths.forEach((path) => {
    if (existingPaths.has(path)) return;
    const emptyEntry = nextEntries.find((entry) => !entry.path.trim());
    if (emptyEntry) emptyEntry.path = path;
    else nextEntries.push({ id: `folder-${Date.now()}-${Math.random()}`, path });
    existingPaths.add(path);
  });
  
  return nextEntries;
}

export default function App() {
  const [appView, setAppView] = useState('setup');
  
  const [form, setForm] = useState({
    folders:[{ id: 'f1', path: "" }, { id: 'f2', path: "" }],
    preferred_root: "",
    force_rescan: false,
    clear_cache: false,
    full_hash_scan: false,
    bitrate_mode: "128",
    gemini_enabled: false,
  });

  const[executingDelete, setExecutingDelete] = useState(false);
  const [singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const[focusedAlbumId, setFocusedAlbumId] = useState(null);
  const [runtimeInfo, setRuntimeInfo] = useState(getRuntimeSnapshot());
  const [deleteAttemptResults, setDeleteAttemptResults] = useState({});
  
  const d = useDeduplicator();
  
  const selectedCluster = d.clusters.find((cluster) => cluster.cluster_id === d.selectedClusterId) || null;
  const currentKeeperId = getActiveKeeperId(selectedCluster, d.decisions);
  const hasSelectedClusterDecision = selectedCluster
    ? hasClusterDecision(d.decisions, selectedCluster.cluster_id)
    : false;
  const selectedDeleteFolderIds = selectedCluster
    ? (d.deleteSelections[selectedCluster.cluster_id] ?? selectedCluster.selected_delete_folder_ids ??[])
    :[];
  const deletionWorkflow = buildDeletionWorkflowModel(d.allClusters, d.preview, d.decisions, deleteAttemptResults);

  useEffect(() => {
    let active = true;
    getRuntimeInfo().then((info) => { if (active) setRuntimeInfo(info); }).catch(() => {});
    return () => { active = false; };
  },[]);

  useEffect(() => {
    if (d.status === 'running') setAppView('scanning');
    if (d.status === 'completed' && d.summary && appView === 'scanning') setAppView('summary');
  }, [d.status, d.summary, appView]);

  useEffect(() => {
    setFocusedAlbumId(null);
  }, [d.selectedClusterId, d.selectedTab]);

  const handleScanSubmit = async (event) => {
    event.preventDefault();
    d.setError("");
    d.setSuccessSummary(null);
    try {
      const payload = { ...form, folders: normalizeFolderPaths(form.folders), preferred_root: form.preferred_root || null };
      const created = await api.createAnalysisSession(payload);
      d.setSessionId(created.session_id);
      d.setStatus(created.status);
      d.setClusters([]);
      d.setDecisions({});
      d.setDeleteSelections({});
      d.setPreview({ items:[], total_count: 0, total_size_mb: 0 });
      d.setAllClusters([]);
      d.setSelectedClusterId(null);
      setDeleteAttemptResults({});
      setAppView('scanning');
    } catch (err) {
      d.setError(err.message);
    }
  };

  const executeDelete = async () => {
    if (!d.sessionId || d.preview.total_count === 0) return;
    setExecutingDelete(true);
    try {
      const execution = await api.executeDelete(d.sessionId, d.preview.items.map((item) => item.folder_id));
      setDeleteAttemptResults((prev) => mergeDeleteAttemptResults(prev, execution.results));
      await d.refreshData(d.sessionId, d.selectedTab);
    } catch (err) {
      d.setError(err.message);
    } finally {
      setExecutingDelete(false);
    }
  };

  const executeSingleDelete = async (target) => {
    if (!d.sessionId || !target) return;
    setSingleDeleteTarget(null);
    try {
      const execution = await api.executeSingleDelete(d.sessionId, target.clusterId, target.folderId);
      setDeleteAttemptResults((prev) => mergeDeleteAttemptResults(prev, execution.results));
      await d.refreshData(d.sessionId, d.selectedTab);
    } catch (err) { 
      d.setError(err.message); 
    }
  };

  const updateClusterDecision = async (clusterId, keeperId, deleteFolderIds = null) => {
    await d.handleDecision(clusterId, keeperId, deleteFolderIds);
  };

  const toggleDeleteSelection = async (clusterId, folderId) => {
    const cluster = d.clusters.find((item) => item.cluster_id === clusterId);
    const keeperId = getActiveKeeperId(cluster, d.decisions);
    if (!cluster || !keeperId || folderId === keeperId) return;
    const currentSelection = new Set(d.deleteSelections[clusterId] ?? cluster.selected_delete_folder_ids ?? []);
    if (currentSelection.has(folderId)) currentSelection.delete(folderId);
    else currentSelection.add(folderId);
    await updateClusterDecision(clusterId, keeperId, Array.from(currentSelection));
  };

  const goToSetup = () => {
    setSingleDeleteTarget(null);
    d.setError("");
    d.setSuccessSummary(null);
    setDeleteAttemptResults({});
    setAppView("setup");
  };

  const openExplorer = async (path) => {
    try {
      const opened = await openDesktopPath(path);
      if (!opened) await api.openInExplorer(path);
    } catch (err) { 
      d.setError(err.message); 
    }
  };

  const handlePickFolders = async () => {
    const [defaultPath] = normalizeFolderPaths(form.folders);
    const paths = await pickScanFolders({ defaultPath });
    if (paths.length) setForm(prev => ({...prev, folders: mergeFolderInputs(prev.folders, paths)}));
  };

  const handlePickPreferredRoot = async () => {
    const path = await pickPreferredRoot();
    if (path) setForm(prev => ({...prev, folders: mergeFolderInputs(prev.folders, [path]), preferred_root: path}));
  };

  useKeyboardShortcuts({
    appView,
    status: d.status,
    clusters: d.clusters,
    selectedCluster,
    selectedClusterId: d.selectedClusterId,
    setSelectedClusterId: d.setSelectedClusterId,
    currentKeeperId,
    focusedAlbumId,
    setFocusedAlbumId,
    handleDecision: updateClusterDecision,
    preview: d.preview,
    openFinalize: () => setAppView("finalize"),
    singleDeleteTarget,
    setSingleDeleteTarget,
    executeSingleDelete,
    openExplorer,
    toggleDeleteSelection,
  });

  return (
    <div className="app-container" dir="rtl">
      <div className="window-content">
        {appView === 'setup' && (
          <SetupScreen 
            form={form} 
            setForm={setForm} 
            onSubmit={handleScanSubmit} 
            onPickFolders={handlePickFolders}
            onPickPreferredRoot={handlePickPreferredRoot}
            runtimeInfo={runtimeInfo}
          />
        )}

        {appView === 'scanning' && (
          <ScanningScreen progress={d.progress} />
        )}

        {appView === 'summary' && d.summary && (
          <SummaryScreen summary={d.summary} onStartReview={() => setAppView('review')} onBackToSetup={goToSetup} />
        )}

        {appView === 'review' && d.status === 'completed' && (
          <div className="workspace-layout">
            <ClusterList
              clusters={d.clusters}
              selectedClusterId={d.selectedClusterId}
              setSelectedClusterId={d.setSelectedClusterId}
              decisions={d.decisions}
              selectedTab={d.selectedTab}
              setSelectedTab={d.setSelectedTab}
            />
            <div className="workspace-main">
              <DiffWorkspace
                key={`${d.selectedTab}-${d.selectedClusterId ?? "empty"}`}
                cluster={selectedCluster}
                currentKeeperId={currentKeeperId}
                hasUserDecision={hasSelectedClusterDecision}
                selectedDeleteFolderIds={selectedDeleteFolderIds}
                handleDecision={updateClusterDecision}
                toggleDeleteSelection={toggleDeleteSelection}
                openExplorer={openExplorer}
                setSingleDeleteTarget={setSingleDeleteTarget}
                onBackToSetup={goToSetup}
              />

              {(deletionWorkflow.summary.pendingCount > 0 || deletionWorkflow.summary.deletedCount > 0 || deletionWorkflow.summary.failedCount > 0) && (
                <DeletePreview 
                  workflowSummary={deletionWorkflow.summary}
                  onOpenFinalize={() => setAppView("finalize")}
                  isExecuting={executingDelete} 
                />
              )}
            </div>
          </div>
        )}

        {appView === "finalize" && d.status === "completed" && (
          <FinalizeDeletionScreen
            workflow={deletionWorkflow}
            onBackToReview={() => setAppView("review")}
            onBackToSetup={goToSetup}
            onExecute={executeDelete}
            isExecuting={executingDelete}
            openExplorer={openExplorer}
          />
        )}
      </div>

      {singleDeleteTarget && (
        <ConfirmModal
          title="העברה בודדת לסל המחזור"
          body={`התיקייה "${singleDeleteTarget.name}" תועבר מיד לסל המחזור בלי להמתין לאישור המרוכז.`}
          confirmText="מחק עכשיו"
          onConfirm={() => executeSingleDelete(singleDeleteTarget)}
          onCancel={() => setSingleDeleteTarget(null)}
          isDanger
        />
      )}

      {d.error && (
        <div style={{ position: 'fixed', bottom: 20, right: 20, background: 'var(--accent-danger)', color: 'white', padding: '12px 24px', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-float)', zIndex: 9999, display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span>{d.error}</span>
          <button style={{ textDecoration: 'underline', opacity: 0.8 }} onClick={() => d.setError("")}>סגור</button>
        </div>
      )}
    </div>
  );
}
