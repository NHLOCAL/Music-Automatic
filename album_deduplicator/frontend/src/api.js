const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
export async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}
export function getEventSource(sessionId) {
  return new EventSource(`${API_BASE}/api/analysis-sessions/${sessionId}/events`);
}
export function createAnalysisSession(payload) {
  return requestJson("/api/analysis-sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
export function getAnalysisSession(sessionId) {
  return requestJson(`/api/analysis-sessions/${sessionId}`);
}
export function getClusters(sessionId, bucket) {
  return requestJson(`/api/analysis-sessions/${sessionId}/clusters?bucket=${bucket}`);
}
export function getDeletePreview(sessionId) {
  return requestJson(`/api/analysis-sessions/${sessionId}/delete-preview`);
}
export function updateDecisions(sessionId, payload) {
  return requestJson(`/api/analysis-sessions/${sessionId}/decisions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
export function executeDelete(sessionId, folderIds) {
  return requestJson(`/api/analysis-sessions/${sessionId}/delete-executions`, {
    method: "POST",
    body: JSON.stringify({ folder_ids: folderIds }),
  });
}
export function executeSingleDelete(sessionId, clusterId, folderId) {
  return requestJson(`/api/analysis-sessions/${sessionId}/delete-single`, {
    method: "POST",
    body: JSON.stringify({ cluster_id: clusterId, folder_id: folderId }),
  });
}
export function openInExplorer(path) {
  return requestJson("/api/system/open-explorer", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}