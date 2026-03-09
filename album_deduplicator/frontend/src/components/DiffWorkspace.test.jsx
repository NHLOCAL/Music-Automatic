import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiffWorkspace } from "./DiffWorkspace";

const cluster = {
  cluster_id: "cluster-1",
  confidence_bucket: "review",
  recommended_keeper_id: "folder-1",
  human_summary: "יש דמיון גבוה בין העותקים, אבל נדרשת בדיקה ידנית לפני מחיקה.",
  albums: [
    {
      folder_id: "folder-1",
      path: "C:/Music/Acoustix",
      name: "Acoustix",
      quality_score: 95,
      avg_bitrate: 320,
      file_count: 2,
      has_album_art: true,
      in_preferred_root: true,
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
      in_preferred_root: false,
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
      in_preferred_root: false,
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
      is_identical_by_hash: false,
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
      is_identical_by_hash: false,
      reason_codes: ["review_threshold"],
    },
  ],
};

describe("DiffWorkspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the redesigned comparison workspace with a decision strip and a track summary", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    expect(screen.getAllByText("עותק 1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("עותק 2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("עותק 3").length).toBeGreaterThan(0);
    expect(screen.getByText("העותק שיישמר כעת")).toBeInTheDocument();
    expect(screen.getByText("המלצת המערכת")).toBeInTheDocument();
    expect(screen.getByText("בסיס ההשוואה בטבלת השירים")).toBeInTheDocument();
    expect(screen.getByText("מה יועבר לסל המחזור")).toBeInTheDocument();
    expect(screen.getByTestId("diff-shell")).toBeInTheDocument();
    expect(screen.getByTestId("comparison-scroller")).toBeInTheDocument();
    expect(screen.getByTestId("track-table-card")).toBeInTheDocument();
    expect(screen.getByText("איך המערכת הגיעה להחלטה")).toBeInTheDocument();
    expect(screen.getByText("עותקי האלבום זה לצד זה")).toBeInTheDocument();
    expect(screen.getByText("רשימת השוואה מפורטת")).toBeInTheDocument();
    expect(screen.getByText("בחר מול איזה עותק מוצגים ההבדלים")).toBeInTheDocument();
    expect(screen.getByText("הטבלה עוקבת אוטומטית אחרי בסיס ההחלטה")).toBeInTheDocument();
    expect(screen.getByText("תואם לעותק הבסיס")).toBeInTheDocument();
    fireEvent.click(screen.getByText("איך המערכת הגיעה להחלטה"));
    expect(screen.getByText("ציון סופי")).toBeInTheDocument();
    expect(screen.getByText("השוואה מתמטית")).toBeInTheDocument();
    expect(screen.getByText("למידת מכונה")).toBeInTheDocument();
    expect(screen.getByText("Score בסיס")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "נבחר לשמירה" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "מיועד למחיקה" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "פתח בתיקייה" })).toHaveLength(3);
    expect(screen.getAllByText("01.mp3").length).toBeGreaterThan(0);
    expect(screen.getAllByText("02.mp3").length).toBeGreaterThan(0);
    expect(screen.getByText("סיכום זמינות")).toBeInTheDocument();
    expect(screen.getAllByText("2 שירים זמינים").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("table").length).toBeGreaterThan(0);
  }, 10000);

  it("shows system insight text and toggles the details panel open", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    expect(screen.getByText("פירוט score, הסבר אנושי, ושכבת השקיפות האלגוריתמית.")).toBeInTheDocument();
    expect(screen.queryByText("ציון סופי")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("איך המערכת הגיעה להחלטה"));
    expect(screen.getAllByText("89.7/100").length).toBeGreaterThan(0);
  });

  it("lets the user pin the track comparison to a specific album copy", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "עותק 2" }));

    expect(screen.getByText("הטבלה מקובעת כרגע לבסיס השוואה ידני")).toBeInTheDocument();
    expect(screen.getAllByText("הטבלה מציגה כעת את כל ההבדלים מול עותק 2.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("בסיס ידני").length).toBeGreaterThan(0);
  });

  it("keeps all copy actions selectable when no keeper has been chosen yet", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId={null}
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button", { name: "שמור עותק זה" })).toHaveLength(3);
    expect(screen.getByText("עדיין לא נבחר keeper ידני")).toBeInTheDocument();
    expect(screen.getByText("0 עותקים")).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: "מיועד למחיקה" })).toHaveLength(0);
  });
});
