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

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
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
      selected_delete_folder_ids: ["folder-drop"],
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

const deletedClusterResponse = {
  clusters: [
    {
      ...clusterResponse.clusters[0],
      resolution_state: "deleted",
      selected_delete_folder_ids: [],
      albums: [
        {
          ...clusterResponse.clusters[0].albums[0],
          is_deleted: false,
        },
        {
          ...clusterResponse.clusters[0].albums[1],
          is_deleted: true,
        },
      ],
    },
  ],
};

const reviewClusterResponse = {
  clusters: [
    {
      ...clusterResponse.clusters[0],
      confidence_bucket: "review",
      selected_delete_folder_ids: [],
      human_summary: 'האלבומים נראים דומים מאוד, אבל עדיין חסר ביטחון מספיק למחיקה אוטומטית. ההמלצה הראשונית היא לשמור את "Best".',
      resolution_state: "skipped",
    },
  ],
};

const emptyPreviewResponse = {
  items: [],
  total_count: 0,
  total_size_mb: 0,
  auto_selected_count: 0,
  manual_selected_count: 0,
};

const emptyClusterResponse = {
  clusters: [],
};

function getScanFolderInputs() {
  return screen.getAllByRole("textbox", { name: /תיקייה לסריקה/i });
}

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

    expect(screen.getByText("Music Automatic")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "התחל סריקה חכמה" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" })).toBeInTheDocument();

    fireEvent.click(screen.getByText("הגדרות מתקדמות"));
    expect(screen.getByText("אימות AI (Gemini)")).toBeInTheDocument();
    expect(screen.getByLabelText("סריקת Hash מלאה")).not.toBeChecked();
  }, 10000);

  it("submits full hash scan only when the advanced toggle is enabled", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse(emptyClusterResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return jsonResponse(emptyPreviewResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1")) {
        return jsonResponse({
          ...sessionSummary,
          counts: {
            ...sessionSummary.counts,
            safe_clusters: 0,
            review_clusters: 0,
          },
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], {
      target: { value: "C:\\Music" },
    });
    fireEvent.change(folderInputs[1], {
      target: { value: "D:\\Archive" },
    });

    fireEvent.click(screen.getByText("הגדרות מתקדמות"));
    fireEvent.click(screen.getByLabelText("סריקת Hash מלאה"));
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => {
      const createRequest = fetchMock.mock.calls.find(([url, options]) =>
        String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
      );
      expect(createRequest).toBeTruthy();
      expect(JSON.parse(createRequest[1].body)).toMatchObject({
        folders: ["C:\\Music", "D:\\Archive"],
        full_hash_scan: true,
      });
    });
  });

  it("uses the electron bridge to pick scan folders", async () => {
    window.albumDeduplicator = createDesktopBridge({
      selectScanFolders: vi.fn(async () => ["C:\\Music", "D:\\Archive"]),
    });
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "+ בחר כמה תיקיות" }));

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toHaveValue("C:\\Music"),
    );
    expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" })).toHaveValue("D:\\Archive");
  });

  it("merges multiple picked scan folders without duplicating existing paths", async () => {
    window.albumDeduplicator = createDesktopBridge({
      selectScanFolders: vi.fn(async () => ["C:\\Music", "D:\\Archive", "E:\\Collection"]),
    });
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });

    fireEvent.click(screen.getByRole("button", { name: "+ בחר כמה תיקיות" }));

    await waitFor(() => {
      const pathInputs = getScanFolderInputs();
      expect(pathInputs[0]).toHaveValue("C:\\Music");
      expect(pathInputs[1]).toHaveValue("D:\\Archive");
      expect(pathInputs[2]).toHaveValue("E:\\Collection");
    });
  });

  it("loads a completed session and renders the compact review workspace", async () => {
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

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], {
      target: { value: "C:\\Music" },
    });
    fireEvent.change(folderInputs[1], {
      target: { value: "D:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "הסריקה הושלמה!" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "התחל לעבור על התוצאות" }));

    await waitFor(() =>
      expect(screen.getByTestId("diff-shell")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("Best vs Archive Copy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("בטוח למחיקה").length).toBeGreaterThan(0);
    expect(screen.getByText("השמעת השוואה מהירה")).toBeInTheDocument();
    expect(screen.getAllByText("01.mp3").length).toBeGreaterThan(0);
    expect(screen.getByText("איך המערכת הגיעה להחלטה")).toBeInTheDocument();
    fireEvent.click(screen.getByText("איך המערכת הגיעה להחלטה"));
    expect(screen.getByText("מודל AI")).toBeInTheDocument();
    expect(screen.queryByText("Score בסיס")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "נבחר לשמירה" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "למחיקה" })).toBeInTheDocument();
  });

  it("opens the standalone finalize screen and shows partial execution status after delete", async () => {
    window.albumDeduplicator = createDesktopBridge();
    let deleteExecuted = false;
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-executions")) {
        deleteExecuted = true;
        return jsonResponse({
          moved_count: 1,
          failed_count: 0,
          total_size_mb: 45,
          results: [
            {
              folder_id: "folder-drop",
              folder_path: "D:/Archive/Best",
              success: true,
              message: "הועבר לסל המחזור.",
              size_mb: 45,
            },
          ],
        });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse(deleteExecuted ? deletedClusterResponse : clusterResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return jsonResponse(deleteExecuted ? emptyPreviewResponse : previewResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1")) {
        return jsonResponse(sessionSummary);
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], {
      target: { value: "C:\\Music" },
    });
    fireEvent.change(folderInputs[1], {
      target: { value: "D:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "הסריקה הושלמה!" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "התחל לעבור על התוצאות" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "עבור לשלב ההעברה" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "עבור לשלב ההעברה" }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "מרכז ההעברה וההשוואה" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("heading", { name: "ממתינות להעברה עכשיו" })).toBeInTheDocument();
    expect(screen.getByText("Archive Copy")).toBeInTheDocument();
    expect(screen.getByText("Best")).toBeInTheDocument();
    expect(screen.getByText("נבחר אוטומטית")).toBeInTheDocument();
    expect(screen.getByText("העותק שנשמר")).toBeInTheDocument();
    expect(screen.getByText("עדיין אין היסטוריית מחיקות להצגה")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "העבר 1 תיקיות לסל המחזור" }));

    await waitFor(() => expect(screen.getByText("אין כרגע קבוצות שממתינות למחיקה")).toBeInTheDocument());
    expect(screen.getByText("אין כרגע קבוצות שממתינות למחיקה")).toBeInTheDocument();
    expect(screen.getAllByText("Archive Copy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Best").length).toBeGreaterThan(0);
    expect(screen.getAllByText("תיקיות שכבר הועברו").length).toBeGreaterThan(0);
    expect(screen.getByText("היסטוריית הפעולות שבוצעו עד כה, יחד עם ה־keeper שנשאר בכל קבוצה כדי לאפשר השוואה חוזרת.")).toBeInTheDocument();
  }, 15000);

  it("waits for summary data before switching from scanning to summary", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const sessionRequest = deferred();
    const clustersRequest = deferred();
    const previewRequest = deferred();

    const fetchMock = vi.fn((url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return Promise.resolve(jsonResponse({ session_id: "session-1", status: "queued" }));
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return clustersRequest.promise;
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return previewRequest.promise;
      }
      if (String(url).includes("/api/analysis-sessions/session-1")) {
        return sessionRequest.promise;
      }
      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], {
      target: { value: "C:\\Music" },
    });
    fireEvent.change(folderInputs[1], {
      target: { value: "D:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    expect(screen.queryByText("הסריקה הושלמה!")).not.toBeInTheDocument();
    expect(screen.getByText("ממתין")).toBeInTheDocument();

    sessionRequest.resolve(jsonResponse(sessionSummary));
    clustersRequest.resolve(jsonResponse(clusterResponse));
    previewRequest.resolve(jsonResponse(previewResponse));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "הסריקה הושלמה!" })).toBeInTheDocument(),
    );
  });

  it("allows changing the keeper in a review cluster and persists the decision", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return String(url).includes("bucket=review")
          ? jsonResponse(reviewClusterResponse)
          : jsonResponse(emptyClusterResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return jsonResponse(emptyPreviewResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/decisions")) {
        return jsonResponse({
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
              selection_source: "user_selected",
            },
          ],
          total_count: 1,
          total_size_mb: 45,
          auto_selected_count: 0,
          manual_selected_count: 1,
        });
      }
      if (String(url).includes("/api/analysis-sessions/session-1")) {
        return jsonResponse({
          ...sessionSummary,
          counts: {
            ...sessionSummary.counts,
            safe_clusters: 0,
            review_clusters: 1,
          },
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], {
      target: { value: "C:\\Music" },
    });
    fireEvent.change(folderInputs[1], {
      target: { value: "D:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "הסריקה הושלמה!" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "התחל לעבור על התוצאות" }));
    fireEvent.click(screen.getByText("לסקירה"));

    await waitFor(() => expect(screen.getAllByText("Best vs Archive Copy").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "למחיקה" }));

    await waitFor(() => {
      const decisionRequest = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/api/analysis-sessions/session-1/decisions"),
      );
      expect(decisionRequest).toBeTruthy();
      expect(JSON.parse(decisionRequest[1].body)).toEqual({
        decisions: [
          {
            cluster_id: "cluster-1",
            keeper_id: "folder-drop",
            delete_folder_ids: ["folder-keep"],
          },
        ],
      });
    });
  });

  it("does not open single-delete confirmation when no keeper is active", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const reviewClusterWithoutKeeperResponse = {
      clusters: [
        {
          ...reviewClusterResponse.clusters[0],
          recommended_keeper_id: null,
        },
      ],
    };
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return String(url).includes("bucket=review")
          ? jsonResponse(reviewClusterWithoutKeeperResponse)
          : jsonResponse(emptyClusterResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return jsonResponse(emptyPreviewResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1")) {
        return jsonResponse({
          ...sessionSummary,
          counts: {
            ...sessionSummary.counts,
            safe_clusters: 0,
            review_clusters: 1,
          },
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], {
      target: { value: "C:\\Music" },
    });
    fireEvent.change(folderInputs[1], {
      target: { value: "D:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה חכמה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "הסריקה הושלמה!" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "התחל לעבור על התוצאות" }));
    fireEvent.click(screen.getByText("לסקירה"));

    await waitFor(() => expect(screen.getAllByText("Best vs Archive Copy").length).toBeGreaterThan(0));

    expect(screen.getAllByRole("button", { name: "שמור עותק זה" }).length).toBeGreaterThan(0);

    fireEvent.keyDown(window, { key: "d" });

    expect(screen.queryByText("העברה בודדת לסל המחזור")).not.toBeInTheDocument();
  });
});
