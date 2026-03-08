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

function mergeFolderLines(currentValue, nextPaths) {
  const items = [
    ...currentValue.split("\n").map((item) => item.trim()).filter(Boolean),
    ...nextPaths.map((item) => item.trim()).filter(Boolean),
  ];
  return Array.from(new Set(items));
}

export default function App() {
  const [form, setForm] = useState({ folders: "", preferred_root: "", force_rescan: false, clear_cache: false, bitrate_mode: "128", gemini_enabled: false });
  const [loading, setLoading] = useState(false);
  const [executingDelete, setExecutingDelete] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const [focusedAlbumId, setFocusedAlbumId] = useState(null);
  const [runtimeInfo, setRuntimeInfo] = useState(getRuntimeSnapshot());
  
  const d = useDeduplicator();
  const selectedCluster = d.clusters.find(c => c.cluster_id === d.selectedClusterId) || null;
  const currentKeeperId = selectedCluster ? (d.decisions[selectedCluster.cluster_id] ?? (selectedCluster.resolution_state === "auto" ? selectedCluster.recommended_keeper_id : null)) : null;

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

  const handleScanSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    d.setError("");
    d.setSuccessSummary(null);
    try {
      const payload = { ...form, folders: form.folders.split("\n").map(i => i.trim()).filter(Boolean), preferred_root: form.preferred_root || null };
      const created = await api.createAnalysisSession(payload);
      d.setSessionId(created.session_id);
      d.setStatus(created.status);
      d.setClusters([]);
      d.setDecisions({});
      d.setPreview({ items: [], total_count: 0, total_size_mb: 0 });
      d.setSelectedClusterId(null);
    } catch (err) {
      d.setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePickFolders = async () => {
    const selectedPaths = await pickScanFolders();
    if (!selectedPaths.length) return;
    setForm((current) => ({
      ...current,
      folders: mergeFolderLines(current.folders, selectedPaths).join("\n"),
    }));
  };

  const handlePickPreferredRoot = async () => {
    const selectedPath = await pickPreferredRoot();
    if (!selectedPath) return;
    setForm((current) => ({ ...current, preferred_root: selectedPath }));
  };

  const executeDelete = async () => {
    if (!d.sessionId || d.preview.total_count === 0) return;
    setExecutingDelete(true);
    try {
      const exec = await api.executeDelete(d.sessionId, d.preview.items.map(i => i.folder_id));
      await d.refreshData(d.sessionId, d.selectedTab);
      d.setSuccessSummary({ moved_count: exec.moved_count, total_size_mb: exec.total_size_mb });
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
      const exec = await api.executeSingleDelete(d.sessionId, target.clusterId, target.folderId);
      await d.refreshData(d.sessionId, d.selectedTab);
      d.setSuccessSummary({ moved_count: exec.moved_count, total_size_mb: exec.total_size_mb });
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
  useKeyboardShortcuts({
    status: d.status, clusters: d.clusters, selectedCluster, selectedClusterId: d.selectedClusterId,
    setSelectedClusterId: d.setSelectedClusterId, currentKeeperId, focusedAlbumId, setFocusedAlbumId,
    handleDecision: d.handleDecision, preview: d.preview, setBulkConfirmOpen, singleDeleteTarget,
    setSingleDeleteTarget, executeSingleDelete, openExplorer
  });
  return (
    <div className="app-layout" dir="rtl">
      <ScanPanel
        form={form}
        setForm={setForm}
        onSubmit={handleScanSubmit}
        loading={loading}
        progress={d.progress}
        summary={d.summary}
        error={d.error}
        runtimeInfo={runtimeInfo}
        onPickFolders={handlePickFolders}
        onPickPreferredRoot={handlePickPreferredRoot}
      />
      
      <main className="main-workspace">
        <div className="tabs-header">
          {TABS.map(t => (
            <button key={t.id} className={`tab-btn ${d.selectedTab === t.id ? 'active' : ''}`} onClick={() => d.setSelectedTab(t.id)} disabled={d.status !== "completed"}>
              {t.label}
            </button>
          ))}
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
              <ClusterList clusters={d.clusters} selectedClusterId={d.selectedClusterId} setSelectedClusterId={d.setSelectedClusterId} decisions={d.decisions} handleDecision={d.handleDecision} />
            ) : (
              <div className="empty-list">הזן תיקיות כדי להתחיל</div>
            )}
          </div>
          <div className="diff-pane">
            <DiffWorkspace cluster={selectedCluster} currentKeeperId={currentKeeperId} focusedAlbumId={focusedAlbumId} setFocusedAlbumId={setFocusedAlbumId} handleDecision={d.handleDecision} openExplorer={openExplorer} setSingleDeleteTarget={setSingleDeleteTarget} />
          </div>
        </div>
      </main>
      <DeletePreview preview={d.preview} onConfirm={() => setBulkConfirmOpen(true)} isExecuting={executingDelete} />
      {bulkConfirmOpen && <ConfirmModal title="העברה לסל המחזור" body={`פעולה זו תעביר ${d.preview.total_count} תיקיות לסל המחזור. המידע לא יימחק לצמיתות עדיין.`} confirmText="העבר לסל" onConfirm={executeDelete} onCancel={() => setBulkConfirmOpen(false)} isDanger />}
      {singleDeleteTarget && <ConfirmModal title="העברה בודדת לסל המחזור" body={`התיקייה "${singleDeleteTarget.name}" תועבר מיד לסל המחזור.`} confirmText="העבר תיקייה זו" onConfirm={() => executeSingleDelete(singleDeleteTarget)} onCancel={() => setSingleDeleteTarget(null)} isDanger />}
    </div>
  );
}
