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
      album_art_preview_url: "/api/analysis-sessions/session-1/albums/folder-1/cover",
      total_size_mb: 120,
      is_deleted: false,
      tracks: [
        {
          track_index: 0,
          filename: "01.mp3",
          filepath: "C:/Music/Acoustix/01.mp3",
          title: "פתיחה",
          duration: 180,
          bitrate: 320,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-1/tracks/0/stream",
        },
      ],
    },
    {
      folder_id: "folder-2",
      path: "D:/Archive/Acoustix",
      name: "Acoustix Archive",
      quality_score: 88,
      avg_bitrate: 256,
      file_count: 2,
      album_art_preview_url: null,
      total_size_mb: 110,
      is_deleted: false,
      tracks: [
        {
          track_index: 0,
          filename: "01.mp3",
          filepath: "D:/Archive/Acoustix/01.mp3",
          title: "פתיחה",
          duration: 180,
          bitrate: 256,
          stream_url: "/api/analysis-sessions/session-1/albums/folder-2/tracks/0/stream",
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
      is_identical_by_hash: false,
    },
  ],
};

describe("DiffWorkspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders album art and fallback cover states in the compact review panes", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
        previewCount={0}
      />,
    );

    expect(screen.getByAltText("עטיפת Acoustix")).toBeInTheDocument();
    expect(screen.getByLabelText("אין עטיפה זמינה")).toBeInTheDocument();
    expect(screen.getByText("נשמר: Acoustix")).toBeInTheDocument();
    expect(screen.getByText("למחיקה: 1")).toBeInTheDocument();
  });

  it("starts an in-app audio preview when the user plays a track", () => {
    const { container } = render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
        previewCount={0}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "נגן את 01.mp3" })[0]);

    expect(screen.getByTestId("audio-preview-card")).toBeInTheDocument();
    expect(screen.getByText("השמעת השוואה")).toBeInTheDocument();
    expect(screen.getByText("פתיחה")).toBeInTheDocument();
    expect(screen.getByText("C:/Music/Acoustix/01.mp3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "סגור את נגן ההשוואה" })).toBeInTheDocument();
    expect(screen.getByLabelText("ציר הזמן של פתיחה")).toBeInTheDocument();
    expect(container.querySelector("audio")).not.toBeNull();
  });

  it("opens a confirmation before mass delete from the review toolbar", async () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId="folder-1"
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
        previewCount={2}
        onOpenFinalize={vi.fn()}
        onExecuteMassDelete={vi.fn()}
        isExecuting={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "העבר למחזור (2)" }));

    expect(await screen.findByText("להעביר את כל הפריטים המסומנים לסל המחזור?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "כן, להעביר" })).toBeInTheDocument();
  });

  it("keeps copy actions selectable when no keeper has been chosen yet", () => {
    render(
      <DiffWorkspace
        cluster={cluster}
        currentKeeperId={null}
        handleDecision={vi.fn()}
        openExplorer={vi.fn()}
        previewCount={0}
      />,
    );

    expect(screen.getAllByRole("button", { name: "שמור עותק זה" })).toHaveLength(2);
    expect(screen.getByText("נשמר: לא נבחר")).toBeInTheDocument();
    expect(screen.getByText("למחיקה: 0")).toBeInTheDocument();
  });
});
