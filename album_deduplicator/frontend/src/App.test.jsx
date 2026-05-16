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
    exportFeedback: vi.fn(async () => ({ ok: true, filePath: "C:\\Exports\\album-deduplicator-user-feedback.jsonl" })),
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

const emptyPreviewResponse = {
  items: [],
  total_count: 0,
  total_size_mb: 0,
  auto_selected_count: 0,
  manual_selected_count: 0,
};

const feedbackSummaryResponse = {
  feedback_file_path: "C:/Users/me/AppData/Local/Music Automatic/Album Deduplicator/user_feedback/user_feedback_events.jsonl",
  event_count: 3,
  size_bytes: 1024,
  export_url: "/api/ml-feedback/export",
};

function getScanFolderInputs() {
  return screen.getAllByRole("textbox", { name: /תיקייה לסריקה/i });
}

function getWorkflowStep(key) {
  return screen.getByTestId(`workflow-step-${key}`).closest(".ant-steps-item");
}

describe("App", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    window.localStorage.clear();
    window.sessionStorage.clear();
    delete window.albumDeduplicator;
  });

  afterEach(() => {
    cleanup();
    delete window.albumDeduplicator;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the compact setup flow with the restored settings options", () => {
    window.albumDeduplicator = createDesktopBridge();
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    expect(screen.getByTestId("workflow-rail")).toBeInTheDocument();
    expect(getWorkflowStep("setup")).not.toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("scanning")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("summary")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("review")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("finalize")).toHaveClass("ant-steps-item-disabled");
    expect(screen.getByText("מיוזיק אוטומטיק")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "בחר תיקייה עבור שורה 1" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "תיקייה לסריקה 2" })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "הפעל סדר עדיפות לשמירה" })).toBeChecked();
    expect(screen.getByText("סדר השורות הוא סדר ההעדפה: תיקייה עליונה עדיפה על זו שמתחתיה, גם עבור תתי-תיקיות שנמצאות בתוכה.")).toBeInTheDocument();
    expect(screen.queryByText("כאשר נמצאים עותקים זהים או באותה איכות, המערכת תשמור את העותק שנמצא תחת התיקייה שמופיעה מוקדם יותר בסדר.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("הגדרות מתקדמות"));
    expect(screen.getByRole("checkbox", { name: "רענון מלא מהדיסק" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "בדיקת Hash מלאה" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "אימות AI למקרים גבוליים" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "התחל סריקה" })).toBeDisabled();
  });

  it("submits full hash scan when the toggle is enabled", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse({ clusters: [] });
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
    fireEvent.change(folderInputs[0], { target: { value: "C:\\Music" } });
    fireEvent.click(screen.getByRole("button", { name: /הוסף תיקייה נוספת/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" }), { target: { value: "D:\\Archive" } });
    fireEvent.click(screen.getByText("הגדרות מתקדמות"));
    fireEvent.click(screen.getByRole("checkbox", { name: "בדיקת Hash מלאה" }));
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => {
      const createRequest = fetchMock.mock.calls.find(([url, options]) =>
        String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
      );
      expect(createRequest).toBeTruthy();
      expect(JSON.parse(createRequest[1].body)).toMatchObject({
        folders: ["C:\\Music", "D:\\Archive"],
        preferred_root: "C:\\Music",
        preferred_roots: ["C:\\Music", "D:\\Archive"],
        full_hash_scan: true,
      });
    });
  });

  it("loads saved Gemini key status and submits a new key with the scan", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/settings/gemini")) {
        return jsonResponse({ has_api_key: true });
      }
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse({ clusters: [] });
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByText("הגדרות מתקדמות"));

    expect(await screen.findByText("מפתח Gemini שמור במחשב הזה. אפשר להשאיר ריק כדי להשתמש בו.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "אימות AI למקרים גבוליים" }));
    fireEvent.change(screen.getByLabelText("מפתח API של Gemini"), {
      target: { value: "new-gemini-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => {
      const createRequest = fetchMock.mock.calls.find(([url, options]) =>
        String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
      );
      expect(createRequest).toBeTruthy();
      expect(JSON.parse(createRequest[1].body)).toMatchObject({
        gemini_enabled: true,
        gemini_api_key: "new-gemini-key",
      });
    });
  });

  it("uses the electron bridge to pick scan folders without duplicating an existing path", async () => {
    window.albumDeduplicator = createDesktopBridge({
      selectScanFolders: vi.fn(async () => ["C:\\Music", "D:\\Archive", "E:\\Collection"]),
    });
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });

    fireEvent.click(screen.getByRole("button", { name: /הוספת כמה תיקיות/ }));
    
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" })).toBeInTheDocument();
      expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 3" })).toBeInTheDocument();
    });

    await waitFor(() => {
      const pathInputs = getScanFolderInputs();
      expect(pathInputs[0]).toHaveValue("C:\\Music");
      expect(pathInputs[1]).toHaveValue("D:\\Archive");
      expect(pathInputs[2]).toHaveValue("E:\\Collection");
    });
  });

  it("fills a single scan row from the folder picker button", async () => {
    const selectScanFolders = vi.fn(async () => ["D:\\Archive"]);
    window.albumDeduplicator = createDesktopBridge({ selectScanFolders });
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "בחר תיקייה עבור שורה 1" }));

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toHaveValue("D:\\Archive");
    });

    expect(selectScanFolders).toHaveBeenCalledWith({ allowMultiple: false, defaultPath: undefined });
  });

  it("submits the configured preference order from the existing scan rows", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse({ clusters: [] });
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: /הוסף תיקייה נוספת/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" }), {
      target: { value: "D:\\Archive" },
    });
    fireEvent.click(screen.getByRole("button", { name: /הוסף תיקייה נוספת/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 3" }), {
      target: { value: "E:\\Backup" },
    });

    fireEvent.click(screen.getByRole("button", { name: "העלה את תיקייה 2 בסדר ההעדפה" }));
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => {
      const createRequest = fetchMock.mock.calls.find(([url, options]) =>
        String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
      );
      expect(createRequest).toBeTruthy();
      expect(JSON.parse(createRequest[1].body)).toMatchObject({
        preferred_root: "D:\\Archive",
        preferred_roots: ["D:\\Archive", "C:\\Music", "E:\\Backup"],
        use_preferred_roots: true,
      });
    });
  });

  it("can submit a scan with preference order disabled", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse({ clusters: [] });
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: /הוסף תיקייה נוספת/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" }), {
      target: { value: "D:\\Archive" },
    });

    fireEvent.click(screen.getByRole("checkbox", { name: "הפעל סדר עדיפות לשמירה" }));
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => {
      const createRequest = fetchMock.mock.calls.find(([url, options]) =>
        String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
      );
      expect(createRequest).toBeTruthy();
      expect(JSON.parse(createRequest[1].body)).toMatchObject({
        preferred_root: null,
        preferred_roots: [],
        use_preferred_roots: false,
      });
    });
  });

  it("opens the finalize screen and requires confirmation before delete", async () => {
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
      if (String(url).includes("/api/analysis-sessions/session-1/delete-executions")) {
        return jsonResponse({
          moved_count: 1,
          failed_count: 0,
          total_size_mb: 45,
          results: [],
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const folderInputs = getScanFolderInputs();
    fireEvent.change(folderInputs[0], { target: { value: "C:\\Music" } });
    fireEvent.click(screen.getByRole("button", { name: /הוסף תיקייה נוספת/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 2" }), { target: { value: "D:\\Archive" } });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "פתח סביבת עבודה" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "עבור לשלב ההעברה" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "עבור לשלב ההעברה" }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "אישור העברה לסל המחזור (1 תיקיות)" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "בצע מחיקה למסומנים" }));

    expect(await screen.findByText("להעביר את הפריטים המסומנים לסל המחזור?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "כן, להעביר" })).toBeInTheDocument();
  }, 15000);

  it("selects the matching folder immediately from numeric review shortcuts", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/decisions") && options.method === "POST") {
        return jsonResponse({
          ...previewResponse,
          items: [{ ...previewResponse.items[0], folder_id: "folder-keep", keeper_folder_id: "folder-drop" }],
          manual_selected_count: 1,
        });
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "פתח סביבת עבודה" }));

    await waitFor(() => expect(screen.getByTestId("review-workspace")).toBeInTheDocument());
    fireEvent.keyDown(window, { key: "2" });

    await waitFor(() => {
      const decisionRequest = fetchMock.mock.calls.find(([url, options = {}]) =>
        String(url).includes("/api/analysis-sessions/session-1/decisions") && options.method === "POST"
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
  }, 15000);

  it("clears the review decision from the space key shortcut", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/decisions") && options.method === "POST") {
        return jsonResponse(emptyPreviewResponse);
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "פתח סביבת עבודה" }));

    await waitFor(() => expect(screen.getByTestId("review-workspace")).toBeInTheDocument());
    fireEvent.keyDown(window, { key: " " });

    await waitFor(() => {
      const decisionRequest = fetchMock.mock.calls.find(([url, options = {}]) =>
        String(url).includes("/api/analysis-sessions/session-1/decisions") && options.method === "POST"
      );
      expect(decisionRequest).toBeTruthy();
      expect(JSON.parse(decisionRequest[1].body)).toEqual({
        decisions: [
          {
            cluster_id: "cluster-1",
            keeper_id: null,
            delete_folder_ids: [],
          },
        ],
      });
    });
  }, 15000);

  it("exports feedback through the Electron bridge without opening a blank child window", async () => {
    const exportFeedback = vi.fn(async () => ({ ok: true, filePath: "C:\\Exports\\feedback.jsonl" }));
    window.albumDeduplicator = createDesktopBridge({ exportFeedback });
    const openMock = vi.fn();
    vi.stubGlobal("open", openMock);
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).includes("/api/ml-feedback/summary")) {
        return jsonResponse(feedbackSummaryResponse);
      }
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("workflow-step-finalize"));

    await waitFor(() => expect(screen.getByRole("button", { name: "יצא נתונים לשיתוף" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "יצא נתונים לשיתוף" }));

    await waitFor(() => {
      expect(exportFeedback).toHaveBeenCalledWith("http://127.0.0.1:9900/api/ml-feedback/export");
    });
    expect(openMock).not.toHaveBeenCalled();
  }, 15000);

  it("clears feedback history from the finalize screen after confirmation", async () => {
    window.albumDeduplicator = createDesktopBridge();
    let feedbackSummary = feedbackSummaryResponse;
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).includes("/api/ml-feedback/summary")) {
        return jsonResponse(feedbackSummary);
      }
      if (String(url).includes("/api/ml-feedback") && options.method === "DELETE") {
        feedbackSummary = { ...feedbackSummaryResponse, event_count: 0, size_bytes: 0 };
        return jsonResponse(feedbackSummary);
      }
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("workflow-step-finalize"));

    await waitFor(() => expect(screen.getByText("3 אירועי אימון נשמרו")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "נקה היסטוריה" }));

    expect(await screen.findByText("לנקות את היסטוריית הזיהויים?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "כן, נקה" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:9900/api/ml-feedback", expect.objectContaining({ method: "DELETE" }));
      expect(screen.getByText("0 אירועי אימון נשמרו")).toBeInTheDocument();
    });
  }, 15000);

  it("keeps the finalize screen stable when canceling a pending transfer for a cluster", async () => {
    window.albumDeduplicator = createDesktopBridge();
    let previewAfterDecision = previewResponse;
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      if (String(url).includes("/api/analysis-sessions/session-1/clusters")) {
        return jsonResponse(clusterResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/decisions") && options.method === "POST") {
        previewAfterDecision = emptyPreviewResponse;
        return jsonResponse(emptyPreviewResponse);
      }
      if (String(url).includes("/api/analysis-sessions/session-1/delete-preview")) {
        return jsonResponse(previewAfterDecision);
      }
      if (String(url).includes("/api/analysis-sessions/session-1") && (!options.method || options.method === "GET")) {
        return jsonResponse(sessionSummary);
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("workflow-step-finalize"));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "בטל העברה ושמור הכל" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "בטל העברה ושמור הכל" }));

    await waitFor(() =>
      expect(screen.getByText("אין פריטים להעברה.")).toBeInTheDocument(),
    );
    expect(screen.getByRole("heading", { name: "אישור העברה לסל המחזור (0 תיקיות)" })).toBeInTheDocument();
  }, 15000);

  it("shows the scan step as active while a session is running and keeps future steps disabled", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        return jsonResponse({ session_id: "session-1", status: "queued" });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("progress", {
      stage: "compare",
      message: "משווה בין אלבומים",
      human_message: "המערכת משווה בין העותקים שנמצאו.",
      current: 4,
      total: 10,
      percent: 40,
      warnings: [],
    });

    await waitFor(() => expect(screen.getByRole("heading", { name: "סריקה בתהליך" })).toBeInTheDocument());

    expect(getWorkflowStep("setup")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("scanning")).toHaveClass("ant-steps-item-active");
    expect(getWorkflowStep("summary")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("review")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("finalize")).toHaveClass("ant-steps-item-disabled");
    expect(screen.getByTestId("workflow-step-badge-scanning")).toHaveTextContent("90%");
  });

  it("allows jumping between completed views without clearing the current session", async () => {
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());
    expect(screen.getByText("1 בטוחות")).toBeInTheDocument();
    expect(screen.getByText("0 לסקירה")).toBeInTheDocument();
    expect(screen.getByText("1 למחיקה")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("workflow-step-review"));
    await waitFor(() => expect(screen.getByTestId("review-workspace")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("workflow-step-finalize"));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "אישור העברה לסל המחזור (1 תיקיות)" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("workflow-step-setup"));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toBeInTheDocument());

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "E:\\Updated Music" },
    });

    fireEvent.click(screen.getByTestId("workflow-step-finalize"));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "אישור העברה לסל המחזור (1 תיקיות)" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("workflow-step-review"));
    await waitFor(() => expect(screen.getByRole("button", { name: "עבור לשלב ההעברה" })).toBeInTheDocument());
  });

  it("keeps the old session available while editing setup and resets it only after submitting a new scan", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        const body = JSON.parse(options.body);
        if (body.folders[0] === "E:\\Fresh Scan") {
          return jsonResponse({ session_id: "session-2", status: "queued" });
        }
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });

    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("workflow-step-finalize"));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "אישור העברה לסל המחזור (1 תיקיות)" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("workflow-step-setup"));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toBeInTheDocument());
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "E:\\Fresh Scan" },
    });

    fireEvent.click(screen.getByTestId("workflow-step-review"));
    await waitFor(() => expect(screen.getByTestId("review-workspace")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("workflow-step-setup"));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toHaveValue("E:\\Fresh Scan"));
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));
    expect((await screen.findAllByText("להתחיל סריקה חדשה במקום התוצאות הקיימות?")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "כן, התחל מחדש" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "סריקה בתהליך" })).toBeInTheDocument());

    expect(getWorkflowStep("scanning")).toHaveClass("ant-steps-item-active");
    expect(getWorkflowStep("summary")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("review")).toHaveClass("ant-steps-item-disabled");
    expect(getWorkflowStep("finalize")).toHaveClass("ant-steps-item-disabled");
  });

  it("warns before replacing an existing completed scan and only restarts after confirmation", async () => {
    window.albumDeduplicator = createDesktopBridge();
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/api/analysis-sessions") && options.method === "POST") {
        const body = JSON.parse(options.body);
        if (body.folders[0] === "E:\\Fresh Scan") {
          return jsonResponse({ session_id: "session-2", status: "queued" });
        }
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

    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "C:\\Music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("completed", { status: "completed" });
    await waitFor(() => expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("workflow-step-setup"));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toBeInTheDocument());
    fireEvent.change(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" }), {
      target: { value: "E:\\Fresh Scan" },
    });

    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));

    expect((await screen.findAllByText("להתחיל סריקה חדשה במקום התוצאות הקיימות?")).length).toBeGreaterThan(0);
    expect(screen.getByText("סריקה חדשה תאפס 1 קבוצות שנמצאו ואת כל סימוני השמירה או ההעברה שביצעת עד כה.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));

    expect(screen.getByRole("textbox", { name: "תיקייה לסריקה 1" })).toHaveValue("E:\\Fresh Scan");
    expect(fetchMock.mock.calls.filter(([url, options]) =>
      String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
    )).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "התחל סריקה" }));
    expect((await screen.findAllByText("להתחיל סריקה חדשה במקום התוצאות הקיימות?")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "כן, התחל מחדש" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "סריקה בתהליך" })).toBeInTheDocument());
    expect(fetchMock.mock.calls.filter(([url, options]) =>
      String(url).endsWith("/api/analysis-sessions") && options?.method === "POST",
    )).toHaveLength(2);
  });
});
