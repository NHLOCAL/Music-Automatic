import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
};

describe("DiffWorkspace", () => {
  it("renders numbered copies and a scrollable track comparison grid", () => {
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
    expect(screen.getByText("השוואת קבצים מפורטת")).toBeInTheDocument();
    expect(screen.getAllByText("01.mp3").length).toBeGreaterThan(0);
    expect(screen.getAllByText("02.mp3").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "עותק שמור" })).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "מחק תיקייה זו כעת" })).toHaveLength(2);
    expect(container.querySelector(".track-grid-scroll")).not.toBeNull();
    expect(container.querySelectorAll(".box-secondary-action")).toHaveLength(3);
  });
});
