import React, { useEffect, useMemo, useState } from "react";
import { App as AntApp, ConfigProvider, Layout } from "antd";
import { ExclamationCircleOutlined } from "@ant-design/icons";
import heIL from "antd/locale/he_IL";
import { useDeduplicator } from "./hooks/useDeduplicator";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import * as api from "./api";
import { exportFeedbackFile, getRuntimeInfo, getRuntimeSnapshot, openDesktopPath, pickScanFolders } from "./desktop";
import { SetupScreen } from "./components/SetupScreen";
import { ScanningScreen } from "./components/ScanningScreen";
import { SummaryScreen } from "./components/SummaryScreen";
import { ClusterList } from "./components/ClusterList";
import { DiffWorkspace } from "./components/DiffWorkspace";
import { FinalizeDeletionScreen } from "./components/FinalizeDeletionScreen";
import { WorkflowRail } from "./components/WorkflowRail";
import { buildDeletionWorkflowModel, getActiveKeeperId, hasExplicitKeeperDecision, mergeDeleteAttemptResults } from "./utils";
import { antTheme } from "./theme/antdTheme";
import { getWorkflowStepState } from "./workflow";

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

function AppContent() {
  const antContext = AntApp.useApp();
  const [appView, setAppView] = useState("setup");
  const [form, setForm] = useState({
    folders: [{ id: "f1", path: "" }],
    use_preferred_roots: true,
    force_rescan: false,
    clear_cache: false,
    full_hash_scan: false,
    bitrate_mode: "128",
    gemini_enabled: false,
  });
  const [executingDelete, setExecutingDelete] = useState(false);
  const [focusedAlbumId, setFocusedAlbumId] = useState(null);
  const [runtimeInfo, setRuntimeInfo] = useState(getRuntimeSnapshot());
  const [deleteAttemptResults, setDeleteAttemptResults] = useState({});
  const [feedbackSummary, setFeedbackSummary] = useState(null);
  const d = useDeduplicator();

  const selectedCluster = d.clusters.find((cluster) => cluster.cluster_id === d.selectedClusterId) || null;
  const currentKeeperId = getActiveKeeperId(selectedCluster, d.decisions);
  const hasExplicitDecision = hasExplicitKeeperDecision(selectedCluster, d.decisions);
  const deletionWorkflow = buildDeletionWorkflowModel(d.allClusters, d.preview, d.decisions, deleteAttemptResults);
  const workflowSteps = useMemo(
    () => getWorkflowStepState({
      appView,
      status: d.status,
      summary: d.summary,
      preview: d.preview,
      progress: d.progress,
    }),
    [appView, d.preview, d.progress, d.status, d.summary],
  );

  useEffect(() => {
    let active = true;
    getRuntimeInfo().then((info) => {
      if (active) setRuntimeInfo(info);
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (d.status === "running") setAppView("scanning");
    if (d.status === "completed" && d.summary && appView === "scanning") setAppView("summary");
  }, [appView, d.status, d.summary]);

  useEffect(() => {
    setFocusedAlbumId(null);
  }, [d.selectedClusterId, d.selectedTab]);

  useEffect(() => {
    if (!d.error) return;
    antContext.notification.error({ message: "שגיאה", description: d.error, placement: "topLeft" });
    d.setError("");
  }, [antContext.notification, d]);

  useEffect(() => {
    if (!d.successSummary) return;
    antContext.notification.success({ message: "העברה הושלמה", description: `הועברו ${d.successSummary.moved_count} תיקיות.`, placement: "topLeft" });
    d.setSuccessSummary(null);
  }, [antContext.notification, d]);

  const refreshFeedbackSummary = async () => {
    try {
      const summary = await api.getFeedbackSummary();
      setFeedbackSummary(summary);
    } catch {
      setFeedbackSummary(null);
    }
  };

  useEffect(() => {
    refreshFeedbackSummary();
  }, []);

  const submitScan = async () => {
    d.setError("");
    d.setSuccessSummary(null);
    try {
      const formPayload = form;
      const preferenceOrder = normalizeFolderPaths(form.folders);
      const payload = {
        ...formPayload,
        folders: preferenceOrder,
        preferred_root: form.use_preferred_roots ? preferenceOrder[0] || null : null,
        preferred_roots: form.use_preferred_roots ? preferenceOrder : [],
      };
      const created = await api.createAnalysisSession(payload);
      d.setSessionId(created.session_id);
      d.setStatus(created.status);
      d.setSummary(null);
      d.setProgress({
        step: "queued",
        stage: "queued",
        message: "ממתין",
        human_message: "ממתין לתחילת הניתוח.",
        current: 0,
        total: 1,
        percent: 0,
        warnings: [],
      });
      d.setClusters([]);
      d.setDecisions({});
      d.setDeleteSelections({});
      d.setPreview({ items: [], total_count: 0, total_size_mb: 0, auto_selected_count: 0, manual_selected_count: 0 });
      d.setAllClusters([]);
      d.setSelectedClusterId(null);
      setDeleteAttemptResults({});
      await refreshFeedbackSummary();
      setAppView("scanning");
    } catch (err) {
      d.setError(err.message);
    }
  };

  const handleScanSubmit = async (event) => {
    if (event) event.preventDefault();

    const existingClusterCount = (d.summary?.counts?.safe_clusters ?? 0) + (d.summary?.counts?.review_clusters ?? 0);
    const hasExistingResults = d.status === "completed" && (
      Boolean(d.summary)
      || d.allClusters.length > 0
      || d.preview.total_count > 0
    );

    if (!hasExistingResults) {
      await submitScan();
      return;
    }

    antContext.modal.confirm({
      centered: true,
      title: "להתחיל סריקה חדשה במקום התוצאות הקיימות?",
      icon: <ExclamationCircleOutlined style={{ color: "#d48806" }} />,
      okText: "כן, התחל מחדש",
      cancelText: "ביטול",
      content: (
        <div style={{ display: "grid", gap: 8 }}>
          <span>יש כבר תוצאות סריקה שמוכנות לעבודה בחלון הזה.</span>
          <span>
            {existingClusterCount > 0
              ? `סריקה חדשה תאפס ${existingClusterCount} קבוצות שנמצאו ואת כל סימוני השמירה או ההעברה שביצעת עד כה.`
              : "סריקה חדשה תאפס את הממצאים והסימונים הקיימים בסשן הנוכחי."}
          </span>
          <span>התהליך עשוי לארוך זמן בהתאם לגודל הספרייה ולבדיקות שסימנת.</span>
        </div>
      ),
      onOk: () => submitScan(),
    });
  };

  const executeDelete = async (folderIdsToExecute = null) => {
    if (!d.sessionId) return;
    const targetIds = folderIdsToExecute || d.preview.items.map(item => item.folder_id);
    if(targetIds.length === 0) return;
    
    setExecutingDelete(true);
    try {
      const execution = await api.executeDelete(d.sessionId, targetIds);
      setDeleteAttemptResults((prev) => mergeDeleteAttemptResults(prev, execution.results));
      await d.refreshData(d.sessionId, d.selectedTab);
      await refreshFeedbackSummary();
      if(appView === "finalize") setAppView("review"); // Return to IDE mode after mass delete
    } catch (err) {
      d.setError(err.message);
    } finally {
      setExecutingDelete(false);
    }
  };

  const updateClusterDecision = async (clusterId, keeperId) => {
    await d.handleDecision(clusterId, keeperId, null);
  };

  const clearClusterDecision = async (clusterId) => {
    await d.handleDecision(clusterId, null, []);
    await refreshFeedbackSummary();
  };

  const exportFeedbackData = async () => {
    if (!feedbackSummary?.export_url) return;
    try {
      const result = await exportFeedbackFile(api.buildApiUrl(feedbackSummary.export_url));
      if (result?.canceled) return;
      antContext.notification.success({
        title: "נתוני האימון יוצאו",
        description: result?.filePath ? `הקובץ נשמר: ${result.filePath}` : "קובץ ה-JSONL מוכן לשיתוף.",
        placement: "topLeft",
      });
    } catch (err) {
      d.setError(err.message);
    }
  };

  const clearFeedbackHistory = async () => {
    try {
      const summary = await api.clearFeedbackHistory();
      setFeedbackSummary(summary);
      antContext.notification.success({
        title: "היסטוריית הזיהויים נוקתה",
        description: "קובץ נתוני האימון המקומי נמחק.",
        placement: "topLeft",
      });
    } catch (err) {
      d.setError(err.message);
    }
  };

  const navigateToSetup = () => {
    d.setError("");
    d.setSuccessSummary(null);
    setAppView("setup");
  };

  const resetForNewScan = () => {
    d.resetSession();
    setDeleteAttemptResults({});
    setAppView("setup");
  };

  const handleWorkflowNavigate = (nextView) => {
    if (nextView === "setup") {
      navigateToSetup();
      return;
    }
    setAppView(nextView);
  };

  const openExplorer = async (path) => {
    try {
      const opened = await openDesktopPath(path);
      if (!opened) await api.openInExplorer(path);
    } catch (err) { d.setError(err.message); }
  };

  const handlePickFolders = async () => {
    const paths = await pickScanFolders();
    if (paths.length) setForm((prev) => ({ ...prev, folders: mergeFolderInputs(prev.folders, paths) }));
  };

  const handlePickFolder = async (folderId, currentPath = "") => {
    const paths = await pickScanFolders({ allowMultiple: false, defaultPath: currentPath || undefined });
    const nextPath = paths[0];
    if (!nextPath) return;
    setForm((prev) => ({
      ...prev,
      folders: prev.folders.map((folder) => (folder.id === folderId ? { ...folder, path: nextPath } : folder)),
    }));
  };

  useKeyboardShortcuts({
    appView, status: d.status, clusters: d.clusters, selectedCluster, selectedClusterId: d.selectedClusterId,
    setSelectedClusterId: d.setSelectedClusterId, currentKeeperId, focusedAlbumId, setFocusedAlbumId,
    handleDecision: updateClusterDecision, preview: d.preview, openFinalize: () => setAppView("finalize"),
    openExplorer,
  });

  return (
    <Layout className="app-shell">
      <Layout.Content className="window-content">
        <div className="workflow-shell">
          <WorkflowRail
            steps={workflowSteps}
            activeStep={appView}
            onNavigate={handleWorkflowNavigate}
          />
          <div className="workflow-view-shell">
            {appView === "setup" && (
              <SetupScreen
                form={form}
                setForm={setForm}
                onSubmit={handleScanSubmit}
                onPickFolders={handlePickFolders}
                onPickFolder={handlePickFolder}
                runtimeInfo={runtimeInfo}
              />
            )}
            {appView === "scanning" && <ScanningScreen progress={d.progress} />}
            {appView === "summary" && d.summary && (
              <SummaryScreen
                summary={d.summary}
                onStartReview={() => setAppView("review")}
              />
            )}
            {appView === "review" && d.status === "completed" && (
              <div className="ide-workspace" data-testid="review-workspace">
                <ClusterList
                  clusters={d.clusters}
                  selectedClusterId={d.selectedClusterId}
                  setSelectedClusterId={d.setSelectedClusterId}
                  decisions={d.decisions}
                  selectedTab={d.selectedTab}
                  setSelectedTab={d.setSelectedTab}
                />
                <div className="ide-main" data-testid="review-main">
                  <DiffWorkspace
                    key={`${d.selectedTab}-${d.selectedClusterId ?? "empty"}`}
                    cluster={selectedCluster}
                    currentKeeperId={currentKeeperId}
                    hasExplicitDecision={hasExplicitDecision}
                    handleDecision={updateClusterDecision}
                    clearDecision={clearClusterDecision}
                    openExplorer={openExplorer}
                    previewCount={d.preview.total_count}
                    onOpenFinalize={() => setAppView("finalize")}
                    onExecuteMassDelete={() => executeDelete()}
                    isExecuting={executingDelete}
                  />
                </div>
              </div>
            )}
            {appView === "finalize" && d.status === "completed" && (
              <FinalizeDeletionScreen
                workflow={deletionWorkflow}
                onExecute={executeDelete}
                isExecuting={executingDelete}
                openExplorer={openExplorer}
                onKeepAllCopies={clearClusterDecision}
                feedbackSummary={feedbackSummary}
                onExportFeedback={exportFeedbackData}
                onClearFeedbackHistory={clearFeedbackHistory}
              />
            )}
          </div>
        </div>
      </Layout.Content>
    </Layout>
  );
}

export default function App() {
  return (
    <ConfigProvider direction="rtl" locale={heIL} theme={antTheme}>
      <AntApp>
        <AppContent />
      </AntApp>
    </ConfigProvider>
  );
}
