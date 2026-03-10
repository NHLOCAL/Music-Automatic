import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

class MockEventSource {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.listeners = new Map();
    MockEventSource.instances.push(this);
  }

  addEventListener(name, listener) {
    const current = this.listeners.get(name) ?? [];
    current.push(listener);
    this.listeners.set(name, current);
  }

  emit(name, data = {}) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.forEach((listener) => listener({ data: JSON.stringify(data) }));
  }

  close() {}
}

function jsonResponse(payload) {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

const sessionSummary = {
  session_id: "session-1",
  status: "completed",
  progress: {
    step: "completed",
    stage: "complete",
    message: "הניתוח הושלם",
    human_message: "הניתוח הסתיים. אפשר להתחיל לעבור על הקבוצות.",
    current: 1,
    total: 1,
    percent: 100,
    warnings: [],
  },
  counts: {
    folders: 2,
    compared_pairs: 1,
    safe_clusters: 1,
    review_clusters: 0,
  },
  error: null,
};

const clusterResponse = {
  clusters: [
    {
      cluster_id: "cluster-1",
      confidence_bucket: "safe",
      recommended_keeper_id: "folder-keep",
      selected_delete_folder_ids: ["folder-drop"],
      human_summary: 'נמצאו עותקים כמעט זהים. מומלץ לשמור את "Best".',
      resolution_state: "auto",
      albums: [
        {
          folder_id: "folder-keep",
          path: "C:/Music/Best",
          name: "Best",
          quality_score: 95,
          avg_bitrate: 320,
          file_count: 10,
          total_size_mb: 50,
          is_deleted: false,
          album_art_preview_url: "/api/analysis-sessions/session-1/albums/folder-keep/cover",
          tracks: [
            {
              track_index: 0,
              filename: "01.mp3",
              filepath: "C:/Music/Best/01.mp3",
              title: "Song A",
              duration: 180,
              bitrate: 320,
              stream_url: "/api/analysis-sessions/session-1/albums/folder-keep/tracks/0/stream",
            },
          ],
        },
        {
          folder_id: "folder-drop",
          path: "D:/Archive/Best",
          name: "Archive Copy",
          quality_score: 84,
          avg_bitrate: 192,
          file_count: 10,
          total_size_mb: 45,
          is_deleted: false,
          album_art_preview_url: null,
          tracks: [
            {
              track_index: 0,
              filename: "01.mp3",
              filepath: "D:/Archive/Best/01.mp3",
              title: "Song A",
              duration: 180,
              bitrate: 192,
              stream_url: "/api/analysis-sessions/session-1/albums/folder-drop/tracks/0/stream",
            },
          ],
        },
      ],
      pairs: [
        {
          pair_id: "pair-1",
          folder1_id: "folder-keep",
          folder2_id: "folder-drop",
          algorithmic_score: 98,
          ml_score: 99,
          base_score: 98.5,
          gemini_score: null,
          final_score: 98.5,
          is_identical_by_hash: false,
        },
      ],
    },
  ],
};

const previewResponse = {
  items: [
    {
      folder_id: "folder-drop",
      folder_path: "D:/Archive/Best",
      folder_name: "Archive Copy",
      keeper_folder_id: "folder-keep",
      keeper_folder_name: "Best",
      keeper_folder_path: "C:/Music/Best",
      cluster_id: "cluster-1",
      estimated_size_mb: 45,
      selection_source: "auto",
    },
  ],
  total_count: 1,
  total_size_mb: 45,
  auto_selected_count: 1,
  manual_selected_count: 0,
};

describe("App review layout", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    cleanup();
    delete window.albumDeduplicator;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps the review workspace layout stable and exposes the transfer step", async () => {
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse(clusterResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return jsonResponse(previewResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1")) {
        return jsonResponse(sessionSummary);
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    const folderInputs = screen.getAllByRole("textbox");

    fireEvent.change(folderInputs[0], { target: { value: "C:\\Music" } });
    fireEvent.change(folderInputs[1], { target: { value: "D:\\Archive" } });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "פתח סביבת עבודה" }));

    await waitFor(() => expect(screen.getByTestId("review-workspace")).toBeInTheDocument());

    expect(screen.getByTestId("cluster-scroll")).toBeInTheDocument();
    expect(screen.getByTestId("review-main")).toBeInTheDocument();
    expect(screen.getByTestId("diff-shell")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "עבור לשלב ההעברה" })).toBeInTheDocument();
  }, 10000);
});
