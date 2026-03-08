import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiffWorkspace } from "./DiffWorkspace";

const cluster = {
  cluster_id: "cluster-1",
  confidence_bucket: "review",
  recommended_keeper_id: "folder-1",
  human_summary: "יש דמיון גבוה בין העותקים, אבל נדרשת בדיקה ידנית לפני מחיקה.",
  technical_summary: "2 pairs הושוו. הציון הנמוך ביותר הוא 89.5/100.",
  reason_codes: ["review_threshold"],
  reasons: [
    { code: "preferred_root_keeper", message: "העותק הראשון נמצא בתיקייה המועדפת." },
  ],
  comparison_highlights: [
    { id: "h1", label: "איכות גבוהה יותר", album_id: "folder-1", tone: "positive", value: "320 kbps" },
  ],
  albums: [
    {
      folder_id: "folder-1",
      path: "C:/Music/Acoustix",
      name: "Acoustix",
      quality_score: 95,
      avg_bitrate: 320,
      file_count: 2,
      has_album_art: true,
      total_size_mb: 120,
      is_deleted: false,
      tracks: [
        { filename: "01.mp3", title: "פתיחה", artist: "ארי", duration: 180, size_mb: 6.2, bitrate: 320 },
        { filename: "02.mp3", title: "סיום", artist: "ארי", duration: 200, size_mb: 7.1, bitrate: 320 },
      ],
    },
    {
      folder_id: "folder-2",
      path: "D:/Archive/Acoustix",
      name: "Acoustix",
      quality_score: 88,
      avg_bitrate: 256,
      file_count: 2,
      has_album_art: false,
      total_size_mb: 110,
      is_deleted: false,
      tracks: [
        { filename: "01.mp3", title: "פתיחה", artist: "ארי", duration: 180, size_mb: 5.8, bitrate: 256 },
        { filename: "02.mp3", title: "סיום", artist: "ארי", duration: 200, size_mb: 6.4, bitrate: 256 },
      ],
    },
    {
      folder_id: "folder-3",
      path: "E:/Backup/Acoustix",
      name: "Acoustix",
      quality_score: 82,
      avg_bitrate: 192,
      file_count: 2,
      has_album_art: false,
      total_size_mb: 95,
      is_deleted: false,
      tracks: [
        { filename: "01.mp3", title: "פתיחה", artist: "ארי", duration: 180, size_mb: 4.9, bitrate: 192 },
        { filename: "02.mp3", title: "סיום", artist: "ארי", duration: 200, size_mb: 5.5, bitrate: 192 },
      ],
    },
  ],
  pairs: [
    {
      pair_id: "pair-1",
      folder1_id: "folder-1",
      folder2_id: "folder-2",
      algorithmic_score: 92,
      ml_score: 94,
      base_score: 93.1,
      gemini_score: 90,
      final_score: 92.6,
      gemini_verdict: "similar",
      gemini_reason: "הרשימות כמעט זהות עם הבדל קטן באיכות.",
      gemini_error: null,
      is_identical_by_hash: false,
      similarity_scores: {},
      reason_codes: ["review_threshold"],
    },
    {
      pair_id: "pair-2",
      folder1_id: "folder-1",
      folder2_id: "folder-3",
      algorithmic_score: 88,
      ml_score: 91,
      base_score: 89.7,
      gemini_score: null,
      final_score: 89.7,
      gemini_verdict: null,
      gemini_reason: null,
      gemini_error: null,
      is_identical_by_hash: false,
      similarity_scores: {},
      reason_codes: ["review_threshold"],
    },
  ],
};

describe("DiffWorkspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders numbered copies, numbered summary text, and a scrollable track comparison table", () => {
    const { container } = render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        hasUserDecision
        selectedDeleteFolderIds={["folder-2", "folder-3"]}
        handleDecision={vi.fn()}
        toggleDeleteSelection={vi.fn()}
        openExplorer={vi.fn()}
        setSingleDeleteTarget={vi.fn()}
        onBackToSetup={vi.fn()}
      />,
    );

    expect(screen.getAllByText("עותק 1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("עותק 2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("עותק 3").length).toBeGreaterThan(0);
    expect(screen.getByText(/ההמלצה הראשונית היא לשמור את עותק 1/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "איך המערכת הגיעה להחלטה" })).toBeInTheDocument();
    expect(screen.getAllByText("המודל המתמטי").length).toBeGreaterThan(0);
    expect(screen.getByText("ציון ה-AI המקומי")).toBeInTheDocument();
    expect(screen.getByText("הציון הסופי")).toBeInTheDocument();
    expect(screen.getAllByText("89.7/100").length).toBeGreaterThan(0);
    expect(screen.getAllByText("92.0/100").length).toBeGreaterThan(0);
    expect(screen.getAllByText("91.0/100").length).toBeGreaterThan(0);
    expect(screen.getByText("השוואת קבצים מפורטת")).toBeInTheDocument();
    expect(screen.getAllByText("01.mp3").length).toBeGreaterThan(0);
    expect(screen.getAllByText("02.mp3").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "עותק שמור" })).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "מחק תיקייה זו כעת" })).toHaveLength(2);
    expect(container.querySelector(".track-table-scroll")).not.toBeNull();
    expect(container.querySelector("table.tracks-table")).not.toBeNull();
    expect(container.querySelectorAll(".box-secondary-action")).toHaveLength(3);
  });

  it("reveals the advanced score breakdown for power users", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        hasUserDecision
        selectedDeleteFolderIds={["folder-2", "folder-3"]}
        handleDecision={vi.fn()}
        toggleDeleteSelection={vi.fn()}
        openExplorer={vi.fn()}
        setSingleDeleteTarget={vi.fn()}
        onBackToSetup={vi.fn()}
      />,
    );

    expect(screen.queryByText("פירוט מלא לכל pair")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצג פרטים מתקדמים" }));

    expect(screen.getByText("פירוט מלא לכל pair")).toBeInTheDocument();
    expect(screen.getByText("תקציר טכני")).toBeInTheDocument();
    expect(screen.getByText("2 pairs הושוו. הציון הנמוך ביותר הוא 89.5/100.")).toBeInTheDocument();
    expect(screen.getAllByText("90.0/100").length).toBeGreaterThan(0);
    expect(screen.getByText(/Reason codes של הקבוצה:/)).toBeInTheDocument();
  });

  it("blocks single-delete actions when no keeper is active", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId={null}
        hasUserDecision
        selectedDeleteFolderIds={[]}
        handleDecision={vi.fn()}
        toggleDeleteSelection={vi.fn()}
        openExplorer={vi.fn()}
        setSingleDeleteTarget={vi.fn()}
        onBackToSetup={vi.fn()}
      />,
    );

    const blockedButtons = screen.getAllByRole("button", { name: "בחר קודם עותק לשמירה" });
    expect(blockedButtons).toHaveLength(3);
    blockedButtons.forEach((button) => expect(button).toBeDisabled());
    expect(screen.queryAllByRole("button", { name: "מחק תיקייה זו כעת" })).toHaveLength(0);
  });
});
