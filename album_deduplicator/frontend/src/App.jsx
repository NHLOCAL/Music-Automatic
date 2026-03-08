import React, { useEffect, useState } from "react";
import { useDeduplicator } from "./hooks/useDeduplicator";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import * as api from "./api";
import { getRuntimeInfo, getRuntimeSnapshot, openDesktopPath, pickPreferredRoot, pickScanFolders } from "./desktop";
import { formatSizeMb } from "./utils";
import { ScanPanel } from "./components/ScanPanel";
import { ClusterList } from "./components/ClusterList";
import { DiffWorkspace } from "./components/DiffWorkspace";
import { DeletePreview } from "./components/DeletePreview";
import { ConfirmModal } from "./components/UI";

const TABS = [
  { id: "safe", label: "בטוח למחיקה" },
  { id: "review", label: "דורש סקירה" },
  { id: "all", label: "כל התוצאות" },
];

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
  if (!uniqueNextPaths.length) {
    return currentEntries;
  }
  const nextEntries = [...currentEntries];
  const existingPaths = new Set(nextEntries.map((entry) => entry.path.trim()).filter(Boolean));

  uniqueNextPaths.forEach((path) => {
    if (existingPaths.has(path)) {
      return;
    }
    const emptyEntry = nextEntries.find((entry) => !entry.path.trim());
    if (emptyEntry) {
      emptyEntry.path = path;
    } else {
      nextEntries.push(createFolderInput(path));
    }
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
  const [loading, setLoading] = useState(false);
  const [executingDelete, setExecutingDelete] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const [focusedAlbumId, setFocusedAlbumId] = useState(null);
  const [runtimeInfo, setRuntimeInfo] = useState(getRuntimeSnapshot());

  const d = useDeduplicator();
  const selectedCluster = d.clusters.find((cluster) => cluster.cluster_id === d.selectedClusterId) || null;
  const currentKeeperId = selectedCluster
    ? (d.decisions[selectedCluster.cluster_id]
      ?? (selectedCluster.resolution_state === "auto" ? selectedCluster.recommended_keeper_id : null))
    : null;
  const selectedDeleteFolderIds = selectedCluster
    ? (d.deleteSelections[selectedCluster.cluster_id] ?? selectedCluster.selected_delete_folder_ids ?? [])
    : [];
  const normalizedFolderPaths = normalizeFolderPaths(form.folders);

  useEffect(() => {
    let active = true;
    getRuntimeInfo()
      .then((info) => {
        if (active) {
          setRuntimeInfo(info);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCluster) {
      setFocusedAlbumId(null);
      return;
    }
    const visibleAlbums = selectedCluster.albums.filter((album) => !album.is_deleted);
    const focusTarget = visibleAlbums.find((album) => album.folder_id === currentKeeperId) ?? visibleAlbums[0] ?? null;
    setFocusedAlbumId((current) => {
      if (current && visibleAlbums.some((album) => album.folder_id === current)) {
        return current;
      }
      return focusTarget?.folder_id ?? null;
    });
  }, [currentKeeperId, selectedCluster]);

  const handleScanSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    d.setError("");
    d.setSuccessSummary(null);
    try {
      const folders = normalizeFolderPaths(form.folders);
      const payload = {
        ...form,
        folders,
        preferred_root: form.preferred_root || null,
      };
      const created = await api.createAnalysisSession(payload);
      d.setSessionId(created.session_id);
      d.setStatus(created.status);
      d.setClusters([]);
      d.setDecisions({});
      d.setDeleteSelections({});
      d.setPreview({ items: [], total_count: 0, total_size_mb: 0, auto_selected_count: 0, manual_selected_count: 0 });
      d.setSelectedClusterId(null);
    } catch (err) {
      d.setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateFolderPath = (folderId, path) => {
    setForm((current) => ({
      ...current,
      folders: current.folders.map((entry) => (
        entry.id === folderId ? { ...entry, path } : entry
      )),
      preferred_root: current.preferred_root && current.preferred_root === current.folders.find((entry) => entry.id === folderId)?.path
        ? path
        : current.preferred_root,
    }));
  };

  const addFolderRow = (path = "") => {
    setForm((current) => ({
      ...current,
      folders: [...current.folders, createFolderInput(path)],
    }));
  };

  const removeFolderRow = (folderId) => {
    setForm((current) => {
      const entry = current.folders.find((item) => item.id === folderId);
      const remaining = current.folders.filter((item) => item.id !== folderId);
      const nextFolders = remaining.length ? remaining : createInitialFolderInputs();
      return {
        ...current,
        folders: nextFolders,
        preferred_root: current.preferred_root && entry?.path.trim() === current.preferred_root ? "" : current.preferred_root,
      };
    });
  };

  const handlePickFolders = async () => {
    const selectedPaths = await pickScanFolders();
    if (!selectedPaths.length) return;
    setForm((current) => ({
      ...current,
      folders: mergeFolderInputs(current.folders, selectedPaths),
    }));
  };

  const handlePickPreferredRoot = async () => {
    const selectedPath = await pickPreferredRoot();
    if (!selectedPath) return;
    setForm((current) => ({
      ...current,
      folders: mergeFolderInputs(current.folders, [selectedPath]),
      preferred_root: selectedPath,
    }));
  };

  const executeDelete = async () => {
    if (!d.sessionId || d.preview.total_count === 0) return;
    setExecutingDelete(true);
    try {
      const execution = await api.executeDelete(d.sessionId, d.preview.items.map((item) => item.folder_id));
      await d.refreshData(d.sessionId, d.selectedTab);
      d.setSuccessSummary({ moved_count: execution.moved_count, total_size_mb: execution.total_size_mb });
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
      const execution = await api.executeSingleDelete(d.sessionId, target.clusterId, target.folderId);
      await d.refreshData(d.sessionId, d.selectedTab);
      d.setSuccessSummary({ moved_count: execution.moved_count, total_size_mb: execution.total_size_mb });
    } catch (err) {
      d.setError(err.message);
    }
  };

  const openExplorer = async (path) => {
    try {
      const openedViaDesktop = await openDesktopPath(path);
      if (!openedViaDesktop) {
        await api.openInExplorer(path);
      }
    } catch (err) {
      d.setError(err.message);
    }
  };

  const updateClusterDecision = async (clusterId, keeperId, deleteFolderIds = null) => {
    await d.handleDecision(clusterId, keeperId, deleteFolderIds);
  };

  const toggleDeleteSelection = async (clusterId, folderId) => {
    if (!selectedCluster || !currentKeeperId || folderId === currentKeeperId) {
      return;
    }
    const currentSelection = new Set(selectedDeleteFolderIds);
    if (currentSelection.has(folderId)) {
      currentSelection.delete(folderId);
    } else {
      currentSelection.add(folderId);
    }
    await updateClusterDecision(clusterId, currentKeeperId, Array.from(currentSelection));
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
          error={d.error}
          runtimeInfo={runtimeInfo}
          onPickFolders={handlePickFolders}
          onPickPreferredRoot={handlePickPreferredRoot}
          onAddFolderRow={addFolderRow}
          onRemoveFolderRow={removeFolderRow}
          onUpdateFolderPath={updateFolderPath}
        />

        <main className="main-workspace">
          <div className="tabs-header">
            <div className="tabs-group">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  className={`tab-btn ${d.selectedTab === tab.id ? "active" : ""}`}
                  onClick={() => d.setSelectedTab(tab.id)}
                  disabled={d.status !== "completed"}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="workspace-caption">
              {d.status === "completed"
                ? "בחר קבוצה, סמן מה יישמר ומה יועבר לסל, ובצע אישור מרוכז בסיום."
                : "המערכת תבנה קבוצות עותקים ותציג רק את ההבדלים המשמעותיים."}
            </div>
          </div>

          <div className="workspace-topbar">
            <div className="runtime-status">
              <span className={`runtime-pill ${runtimeInfo.isElectron ? "runtime-pill-desktop" : "runtime-pill-browser"}`}>
                {runtimeInfo.isElectron ? "Electron Desktop" : "Browser Preview"}
              </span>
              <span className="runtime-caption">{runtimeInfo.backendBaseUrl}</span>
            </div>
            {d.successSummary && (
              <div className="workspace-success">
                {`הועברו ${d.successSummary.moved_count} תיקיות לסל המחזור, כ-${formatSizeMb(d.successSummary.total_size_mb)}.`}
              </div>
            )}
          </div>

          <div className="workspace-grid">
            <div className="list-pane">
              {d.status === "completed" ? (
                <ClusterList
                  clusters={d.clusters}
                  selectedClusterId={d.selectedClusterId}
                  setSelectedClusterId={d.setSelectedClusterId}
                  decisions={d.decisions}
                  deleteSelections={d.deleteSelections}
                  handleDecision={updateClusterDecision}
                />
              ) : (
                <div className="empty-list">הוסף roots לסריקה כדי להתחיל.</div>
              )}
            </div>

            <div className="diff-pane">
              <DiffWorkspace
                cluster={selectedCluster}
                currentKeeperId={currentKeeperId}
                selectedDeleteFolderIds={selectedDeleteFolderIds}
                focusedAlbumId={focusedAlbumId}
                setFocusedAlbumId={setFocusedAlbumId}
                handleDecision={updateClusterDecision}
                toggleDeleteSelection={toggleDeleteSelection}
                openExplorer={openExplorer}
                setSingleDeleteTarget={setSingleDeleteTarget}
              />
            </div>
          </div>
        </main>
      </div>

      <DeletePreview preview={d.preview} onConfirm={() => setBulkConfirmOpen(true)} isExecuting={executingDelete} />

      {bulkConfirmOpen && (
        <ConfirmModal
          title="העברה לסל המחזור"
          body={`פעולה זו תעביר ${d.preview.total_count} תיקיות לסל המחזור ותפנה כ-${formatSizeMb(d.preview.total_size_mb)}. הקבצים לא יימחקו לצמיתות בשלב זה.`}
          confirmText="העבר לסל"
          onConfirm={executeDelete}
          onCancel={() => setBulkConfirmOpen(false)}
          isDanger
        />
      )}

      {singleDeleteTarget && (
        <ConfirmModal
          title="העברה בודדת לסל המחזור"
          body={`התיקייה "${singleDeleteTarget.name}" תועבר מיד לסל המחזור בלי להמתין לאישור המרוכז.`}
          confirmText="העבר תיקייה זו"
          onConfirm={() => executeSingleDelete(singleDeleteTarget)}
          onCancel={() => setSingleDeleteTarget(null)}
          isDanger
        />
      )}
    </div>
  );
}
