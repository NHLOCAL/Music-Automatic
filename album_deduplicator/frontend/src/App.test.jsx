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

function createDesktopBridge(overrides = {}) {
  return {
    runtime: {
      isElectron: true,
      backendBaseUrl: "http://127.0.0.1:9900",
      version: "0.1.0",
      platform: "win32",
    },
    getRuntimeInfo: vi.fn(async () => ({
      isElectron: true,
      backendBaseUrl: "http://127.0.0.1:9900",
      version: "0.1.0",
      platform: "win32",
    })),
    selectScanFolders: vi.fn(async () => []),
    selectPreferredRoot: vi.fn(async () => null),
    openPath: vi.fn(async () => ({ ok: true })),
    revealPath: vi.fn(async () => ({ ok: true })),
    ...overrides,
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
    delete window.albumDeduplicator;
  });

  afterEach(() => {
    cleanup();
    delete window.albumDeduplicator;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the browser fallback flow and advanced settings", () => {
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    expect(screen.getByRole("button", { name: "התחל סריקה חכמה" })).toBeInTheDocument();
    expect(screen.getByText("React + API")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הגדרות מתקדמות" }));
    expect(screen.getByText("הפעל אימות AI (Gemini) למקרים גבוליים")).toBeInTheDocument();
  });

  it("uses the electron bridge to pick scan folders", async () => {
    window.albumDeduplicator = createDesktopBridge({
      selectScanFolders: vi.fn(async () => ["C:\\Music", "D:\\Archive"]),
    });
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "בחר תיקיות" }));

    await waitFor(() =>
      expect(screen.getByLabelText("תיקיות לסריקה")).toHaveValue("C:\\Music\nD:\\Archive"),
    );
    expect(screen.getByText("Electron + React")).toBeInTheDocument();
  });

  it("loads a completed session and opens the single-delete confirmation", async () => {
    window.albumDeduplicator = createDesktopBridge();
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

    fireEvent.change(screen.getByLabelText("תיקיות לסריקה"), {
      target: { value: "C:\\Music\nD:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getAllByText('נמצאו עותקים כמעט זהים. מומלץ לשמור את "Best".').length).toBeGreaterThan(0),
    );

    fireEvent.click(screen.getByRole("button", { name: "מחק עכשיו" }));

    expect(screen.getByText("העברה בודדת לסל המחזור")).toBeInTheDocument();
    expect(screen.getByText('התיקייה "Archive Copy" תועבר מיד לסל המחזור.')).toBeInTheDocument();
  });
});
