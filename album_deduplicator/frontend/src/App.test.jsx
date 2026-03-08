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
  mode_summary: {
    ml_default_enabled: true,
    gemini_enabled: false,
    review_threshold: 85,
    safe_delete_threshold: 97,
  },
  degraded_flags: {
    ml_unavailable: false,
    gemini_unavailable: false,
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
      human_summary: 'נמצאו עותקים כמעט זהים. מומלץ לשמור את "Best".',
      resolution_state: "auto",
      recommended_keeper_reason: "האלבום המומלץ נמצא בתיקייה המועדפת.",
      reason_codes: ["preferred_root_keeper"],
      reasons: [{ code: "preferred_root_keeper", message: "root preferred" }],
      comparison_highlights: [
        { id: "h1", label: "איכות גבוהה יותר", album_id: "folder-keep", tone: "positive", value: "95.0%" },
        { id: "h2", label: "כולל עטיפת אלבום", album_id: "folder-keep", tone: "positive", value: null },
      ],
      technical_summary: "1 זוג הושווה. הציון הנמוך ביותר הוא 98.5%.",
      deletable_folder_ids: ["folder-drop"],
      albums: [
        {
          folder_id: "folder-keep",
          path: "C:/Music/Best",
          name: "Best",
          quality_score: 95,
          avg_bitrate: 320,
          file_count: 10,
          in_preferred_root: true,
          has_album_art: true,
          lossless_ratio: 0,
          lyrics_ratio: 0.4,
          total_size_mb: 50,
          is_deleted: false,
          tracks: [
            { filename: "01.mp3", title: "Song A", artist: "Artist", duration: 180, size_mb: 5, bitrate: 320 },
          ],
        },
        {
          folder_id: "folder-drop",
          path: "D:/Archive/Best",
          name: "Archive Copy",
          quality_score: 84,
          avg_bitrate: 192,
          file_count: 10,
          in_preferred_root: false,
          has_album_art: false,
          lossless_ratio: 0,
          lyrics_ratio: 0,
          total_size_mb: 45,
          is_deleted: false,
          tracks: [
            { filename: "01.mp3", title: "Song A", artist: "Artist", duration: 180, size_mb: 5, bitrate: 192 },
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
          gemini_verdict: null,
          gemini_reason: null,
          gemini_error: null,
          is_identical_by_hash: false,
          similarity_scores: {},
          reason_codes: ["safe_threshold"],
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

describe("App", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the minimal analysis flow and advanced settings toggle", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<App />);

    expect(screen.getByRole("button", { name: "התחל ניתוח" })).toBeInTheDocument();
    expect(screen.getByText("ML פעיל כברירת מחדל.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "פתח אפשרויות מתקדמות" }));
    expect(screen.getByText("Gemini לזוגות גבוליים בלבד")).toBeInTheDocument();
  });

  it("loads a completed session and shows the human summary plus shortcut overlay", async () => {
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

    fireEvent.change(screen.getByLabelText("תיקיות קלט"), {
      target: { value: "C:\\Music\nD:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל ניתוח" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getAllByText('נמצאו עותקים כמעט זהים. מומלץ לשמור את "Best".').length).toBeGreaterThan(0),
    );
    expect(screen.getByText("למה דווקא העותק הזה?")).toBeInTheDocument();
    expect(screen.getByText("רשימת שירים מאוחדת")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "קיצורי מקלדת" }));
    expect(screen.getByText("Keyboard Power Mode")).toBeInTheDocument();
    expect(screen.getByText("פתח אישור למחיקה בודדת")).toBeInTheDocument();
  });

  it("opens a mini confirmation before single delete", async () => {
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
    fireEvent.change(screen.getByLabelText("תיקיות קלט"), {
      target: { value: "C:\\Music\nD:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל ניתוח" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "מחק עכשיו" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "מחק עכשיו" }));

    expect(screen.getByText('להעביר את "Archive Copy" לסל המחזור?')).toBeInTheDocument();
    expect(screen.getByText("כן, העבר לסל המחזור")).toBeInTheDocument();
  });
});
