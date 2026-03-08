import React, { useEffect, useState } from "react";
import { useDeduplicator } from "./hooks/useDeduplicator";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import * as api from "./api";
import { getRuntimeInfo, getRuntimeSnapshot, openDesktopPath, pickPreferredRoot, pickScanFolders } from "./desktop";
import { ScanPanel } from "./components/ScanPanel";
import { ClusterList } from "./components/ClusterList";
import { DiffWorkspace } from "./components/DiffWorkspace";
import { DeletePreview } from "./components/DeletePreview";
import { ConfirmModal } from "./components/UI";

let folderInputCounter = 0;
function createFolderInput(path = "") {
  folderInputCounter += 1;
  return { id: `folder-input-${folderInputCounter}`, path };
}
function createInitialFolderInputs() {
  return [createFolderInput(""), createFolderInput("")];
}
function normalizeFolderPaths(entries) {
  return entries.map((entry) => entry.path.trim()).filter(Boolean);
}
function mergeFolderInputs(currentEntries, nextPaths) {
  const uniqueNextPaths = Array.from(new Set(nextPaths.map((item) => item.trim()).filter(Boolean)));
  if (!uniqueNextPaths.length) return currentEntries;
  const nextEntries = [...currentEntries];
  const existingPaths = new Set(nextEntries.map((entry) => entry.path.trim()).filter(Boolean));
  uniqueNextPaths.forEach((path) => {
    if (existingPaths.has(path)) return;
    const emptyEntry = nextEntries.find((entry) => !entry.path.trim());
    if (emptyEntry) emptyEntry.path = path;
    else nextEntries.push(createFolderInput(path));
    existingPaths.add(path);
  });
  return nextEntries;
}

export default function App() {
  const [form, setForm] = useState({
    folders: createInitialFolderInputs(),
    preferred_root: "",
    force_rescan: false,
    clear_cache: false,
    bitrate_mode: "128",
    gemini_enabled: false,
  });
  const[loading, setLoading] = useState(false);
  const [executingDelete, setExecutingDelete] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const[singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const[focusedAlbumId, setFocusedAlbumId] = useState(null);
  const [runtimeInfo, setRuntimeInfo] = useState(getRuntimeSnapshot());
  const d = useDeduplicator();

  const selectedCluster = d.clusters.find((cluster) => cluster.cluster_id === d.selectedClusterId) || null;
  const currentKeeperId = selectedCluster
    ? (d.decisions[selectedCluster.cluster_id] ?? (selectedCluster.resolution_state === "auto" ? selectedCluster.recommended_keeper_id : null))
    : null;
  const selectedDeleteFolderIds = selectedCluster
    ? (d.deleteSelections[selectedCluster.cluster_id] ?? selectedCluster.selected_delete_folder_ids ?? [])
    :[];

  const normalizedFolderPaths = normalizeFolderPaths(form.folders);

  useEffect(() => {
    let active = true;
    getRuntimeInfo().then((info) => { if (active) setRuntimeInfo(info); }).catch(() => {});
    return () => { active = false; };
  },[]);

  const handleScanSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
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
      d.setSelectedClusterId(null);
    } catch (err) {
      d.setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const executeDelete = async () => {
    if (!d.sessionId || d.preview.total_count === 0) return;
    setExecutingDelete(true);
    try {
      await api.executeDelete(d.sessionId, d.preview.items.map((item) => item.folder_id));
      await d.refreshData(d.sessionId, d.selectedTab);
      setBulkConfirmOpen(false);
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
      await api.executeSingleDelete(d.sessionId, target.clusterId, target.folderId);
      await d.refreshData(d.sessionId, d.selectedTab);
    } catch (err) { d.setError(err.message); }
  };

  const updateClusterDecision = async (clusterId, keeperId, deleteFolderIds = null) => {
    await d.handleDecision(clusterId, keeperId, deleteFolderIds);
  };

  const toggleDeleteSelection = async (clusterId, folderId) => {
    if (!selectedCluster || !currentKeeperId || folderId === currentKeeperId) return;
    const currentSelection = new Set(selectedDeleteFolderIds);
    if (currentSelection.has(folderId)) currentSelection.delete(folderId);
    else currentSelection.add(folderId);
    await updateClusterDecision(clusterId, currentKeeperId, Array.from(currentSelection));
  };

  const openExplorer = async (path) => {
    try {
      const opened = await openDesktopPath(path);
      if (!opened) await api.openInExplorer(path);
    } catch (err) { d.setError(err.message); }
  };

  useKeyboardShortcuts({
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
    setBulkConfirmOpen,
    singleDeleteTarget,
    setSingleDeleteTarget,
    executeSingleDelete,
    openExplorer,
    toggleDeleteSelection,
  });

  return (
    <div className="app-shell" dir="rtl">
      <div className="app-layout">
        <ScanPanel
          form={form}
          normalizedFolderPaths={normalizedFolderPaths}
          setForm={setForm}
          onSubmit={handleScanSubmit}
          loading={loading}
          progress={d.progress}
          summary={d.summary}
          runtimeInfo={runtimeInfo}
          onPickFolders={async () => { const p = await pickScanFolders(); if(p.length) setForm(c => ({...c, folders: mergeFolderInputs(c.folders, p)})); }}
          onPickPreferredRoot={async () => { const p = await pickPreferredRoot(); if(p) setForm(c => ({...c, folders: mergeFolderInputs(c.folders, [p]), preferred_root: p})); }}
          onAddFolderRow={(path) => setForm(c => ({...c, folders:[...c.folders, createFolderInput(path)]}))}
          onRemoveFolderRow={(id) => setForm(c => { const rem = c.folders.filter(f => f.id !== id); return {...c, folders: rem.length ? rem : createInitialFolderInputs()}; })}
          onUpdateFolderPath={(id, path) => setForm(c => ({...c, folders: c.folders.map(f => f.id === id ? {...f, path} : f)}))}
        />
        
        <main className="main-workspace">
          <header className="workspace-header">
            <div className="tabs">
              <button className={`tab ${d.selectedTab === "safe" ? "active" : ""}`} onClick={() => d.setSelectedTab("safe")} disabled={d.status !== "completed"}>בטוח למחיקה</button>
              <button className={`tab ${d.selectedTab === "review" ? "active" : ""}`} onClick={() => d.setSelectedTab("review")} disabled={d.status !== "completed"}>דורש סקירה</button>
              <button className={`tab ${d.selectedTab === "all" ? "active" : ""}`} onClick={() => d.setSelectedTab("all")} disabled={d.status !== "completed"}>כל התוצאות</button>
            </div>
          </header>

          <div className="workspace-body">
            {d.status === "completed" && (
              <ClusterList
                clusters={d.clusters}
                selectedClusterId={d.selectedClusterId}
                setSelectedClusterId={d.setSelectedClusterId}
                decisions={d.decisions}
              />
            )}
            <DiffWorkspace
              cluster={selectedCluster}
              currentKeeperId={currentKeeperId}
              selectedDeleteFolderIds={selectedDeleteFolderIds}
              handleDecision={updateClusterDecision}
              toggleDeleteSelection={toggleDeleteSelection}
              openExplorer={openExplorer}
              setSingleDeleteTarget={setSingleDeleteTarget}
            />
          </div>
        </main>
      </div>

      <DeletePreview preview={d.preview} onConfirm={() => setBulkConfirmOpen(true)} isExecuting={executingDelete} />

      {bulkConfirmOpen && (
        <ConfirmModal
          title="העברה לסל המחזור"
          body={`פעולה זו תעביר ${d.preview.total_count} תיקיות לסל המחזור. הקבצים לא יימחקו לצמיתות בשלב זה.`}
          confirmText="העבר לסל"
          onConfirm={executeDelete}
          onCancel={() => setBulkConfirmOpen(false)}
          isDanger
        />
      )}

      {singleDeleteTarget && (
        <ConfirmModal
          title="העברה בודדת"
          body={`התיקייה "${singleDeleteTarget.name}" תועבר לסל המחזור מיד.`}
          confirmText="מחק עכשיו"
          onConfirm={() => executeSingleDelete(singleDeleteTarget)}
          onCancel={() => setSingleDeleteTarget(null)}
          isDanger
        />
      )}
    </div>
  );
}