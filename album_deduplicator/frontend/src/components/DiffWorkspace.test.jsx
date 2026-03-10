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
      album_art_preview_url: "/api/analysis-sessions/session-1/albums/folder-1/cover",
      in_preferred_root: true,
      total_size_mb: 120,
      is_deleted: false,
      tracks: [
        {
          track_index: 0,
          filename: "01.mp3",
          filepath: "C:/Music/Acoustix/01.mp3",
          title: "פתיחה",
          artist: "ארי",
          duration: 180,
          size_mb: 6.2,
          bitrate: 320,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-1/tracks/0/stream",
        },
        {
          track_index: 1,
          filename: "02.mp3",
          filepath: "C:/Music/Acoustix/02.mp3",
          title: "סיום",
          artist: "ארי",
          duration: 200,
          size_mb: 7.1,
          bitrate: 320,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-1/tracks/1/stream",
        },
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
      album_art_preview_url: null,
      in_preferred_root: false,
      total_size_mb: 110,
      is_deleted: false,
      tracks: [
        {
          track_index: 0,
          filename: "01.mp3",
          filepath: "D:/Archive/Acoustix/01.mp3",
          title: "פתיחה",
          artist: "ארי",
          duration: 180,
          size_mb: 5.8,
          bitrate: 256,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-2/tracks/0/stream",
        },
        {
          track_index: 1,
          filename: "02.mp3",
          filepath: "D:/Archive/Acoustix/02.mp3",
          title: "סיום",
          artist: "ארי",
          duration: 200,
          size_mb: 6.4,
          bitrate: 256,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-2/tracks/1/stream",
        },
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
      album_art_preview_url: null,
      in_preferred_root: false,
      total_size_mb: 95,
      is_deleted: false,
      tracks: [
        {
          track_index: 0,
          filename: "01.mp3",
          filepath: "E:/Backup/Acoustix/01.mp3",
          title: "פתיחה",
          artist: "ארי",
          duration: 180,
          size_mb: 4.9,
          bitrate: 192,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-3/tracks/0/stream",
        },
        {
          track_index: 1,
          filename: "02.mp3",
          filepath: "E:/Backup/Acoustix/02.mp3",
          title: "סיום",
          artist: "ארי",
          duration: 200,
          size_mb: 5.5,
          bitrate: 192,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-3/tracks/1/stream",
        },
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

  it("renders album covers and the track table without showing the audio banner before playback", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    expect(screen.getAllByText("עותק 1").length).toBeGreaterThan(0);
    expect(screen.getByText("עטיפת אלבום")).toBeInTheDocument();
    expect(screen.getAllByText("אין עטיפה זמינה").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("audio-preview-card")).not.toBeInTheDocument();
    expect(screen.getByText("בסיס השוואה בטבלה:")).toBeInTheDocument();
    expect(screen.getByTestId("track-table-card")).toBeInTheDocument();
    expect(screen.getByText("איך המערכת הגיעה להחלטה")).toBeInTheDocument();
    fireEvent.click(screen.getByText("איך המערכת הגיעה להחלטה"));
    expect(screen.getByText("מודל AI")).toBeInTheDocument();
    expect(screen.queryByText((_, node) => node?.textContent?.includes("Score בסיס") ?? false)).not.toBeInTheDocument();
  });

  it("shows the base score only when it differs from the final score", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-2"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("איך המערכת הגיעה להחלטה"));

    expect(screen.getByText("מודל AI")).toBeInTheDocument();
    expect(screen.getAllByText((_, node) => node?.textContent?.includes("Score בסיס") ?? false).length).toBeGreaterThan(0);
  });

  it("starts an in-app preview player when the user plays a track", () => {
    const { container } = render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "נגן את 01.mp3" })[0]);

    expect(screen.getByTestId("audio-preview-card")).toBeInTheDocument();
    expect(screen.getByText("השמעת השוואה מהירה")).toBeInTheDocument();
    expect(screen.getByTestId("audio-preview-card")).toHaveTextContent("מנגן");
    expect(screen.getAllByText("פתיחה").length).toBeGreaterThan(0);
    expect(screen.getByText("C:/Music/Acoustix/01.mp3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "סגור את נגן ההשוואה" })).toBeInTheDocument();
    expect(screen.getByLabelText("ציר הזמן של פתיחה")).toBeInTheDocument();
    expect(container.querySelector("audio")).not.toBeNull();
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

    expect(screen.getByText("הטבלה מקובעת כעת לעותק 2 כדי לאפשר השוואה ידנית.")).toBeInTheDocument();
  });

  it("keeps copy actions selectable when no keeper has been chosen yet", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId={null}
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button", { name: "שמור עותק זה" })).toHaveLength(3);
    expect(screen.getByText("לא נבחר")).toBeInTheDocument();
    expect(screen.getByText("לסל המחזור")).toBeInTheDocument();
  });
});
