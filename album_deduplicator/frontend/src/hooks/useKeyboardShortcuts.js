import { useEffect } from "react";
export function useKeyboardShortcuts({
  status, clusters, selectedCluster, selectedClusterId, setSelectedClusterId,
  currentKeeperId, focusedAlbumId, setFocusedAlbumId, handleDecision,
  preview, setBulkConfirmOpen, singleDeleteTarget, setSingleDeleteTarget, executeSingleDelete, openExplorer,
  toggleDeleteSelection,
}) {
  useEffect(() => {
    const onKeyDown = (event) => {
      const targetTag = event.target?.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(targetTag)) return;
      if (event.key === "Escape") {
        setBulkConfirmOpen(false);
        setSingleDeleteTarget(null);
        return;
      }
      if (status !== "completed" || !selectedCluster) return;
      const clusterIndex = clusters.findIndex(c => c.cluster_id === selectedCluster.cluster_id);
      if (event.key === "ArrowDown" && clusterIndex < clusters.length - 1) {
        event.preventDefault();
        setSelectedClusterId(clusters[clusterIndex + 1].cluster_id);
        return;
      }
      if (event.key === "ArrowUp" && clusterIndex > 0) {
        event.preventDefault();
        setSelectedClusterId(clusters[clusterIndex - 1].cluster_id);
        return;
      }
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const visibleAlbums = selectedCluster.albums.filter(a => !a.is_deleted);
        if (!visibleAlbums.length) return;
        const currentRefId = currentKeeperId ?? focusedAlbumId;
        const index = visibleAlbums.findIndex(a => a.folder_id === currentRefId);
        const offset = event.key === "ArrowLeft" ? -1 : 1;
        const nextIdx = index === -1 ? 0 : (index + offset + visibleAlbums.length) % visibleAlbums.length;
        const nextAlbumId = visibleAlbums[nextIdx].folder_id;
        setFocusedAlbumId(nextAlbumId);
        handleDecision(selectedCluster.cluster_id, nextAlbumId);
        return;
      }
      if (event.key === " ") {
        event.preventDefault();
        handleDecision(selectedCluster.cluster_id, null, []);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        if (singleDeleteTarget) executeSingleDelete(singleDeleteTarget);
        else if (preview.total_count > 0) setBulkConfirmOpen(true);
        return;
      }
      if (event.key.toLowerCase() === "o") {
        event.preventDefault();
        const album = selectedCluster.albums.find(a => a.folder_id === (focusedAlbumId ?? currentKeeperId)) ?? selectedCluster.albums.find(a => !a.is_deleted);
        if (album) openExplorer(album.path);
        return;
      }
      if (event.key.toLowerCase() === "d") {
        event.preventDefault();
        const candidate = selectedCluster.albums.find(a => !a.is_deleted && a.folder_id !== currentKeeperId);
        if (candidate) {
          setSingleDeleteTarget({ clusterId: selectedCluster.cluster_id, folderId: candidate.folder_id, name: candidate.name });
        }
        return;
      }
      if (event.key.toLowerCase() === "x") {
        event.preventDefault();
        const candidate = selectedCluster.albums.find((album) => album.folder_id === focusedAlbumId)
          ?? selectedCluster.albums.find((album) => !album.is_deleted && album.folder_id !== currentKeeperId);
        if (candidate && candidate.folder_id !== currentKeeperId) {
          toggleDeleteSelection(selectedCluster.cluster_id, candidate.folder_id);
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [clusters, currentKeeperId, focusedAlbumId, preview.total_count, selectedCluster, singleDeleteTarget, status, executeSingleDelete, handleDecision, openExplorer, setBulkConfirmOpen, setFocusedAlbumId, setSelectedClusterId, setSingleDeleteTarget, toggleDeleteSelection]);
}   
