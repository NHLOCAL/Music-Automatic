import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FinalizeDeletionScreen } from "./FinalizeDeletionScreen";
import { ScanningScreen } from "./ScanningScreen";
import { SummaryScreen } from "./SummaryScreen";

describe("Workflow screens", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the compact scanning screen with the current minimal progress layout", () => {
    render(
      <ScanningScreen
        progress={{
          percent: 42,
          stage: "compare",
          message: "משווה בין אלבומים",
          human_message: "המערכת בודקת התאמות בין עותקים ומכינה קבוצות להחלטה.",
          current: 21,
          total: 50,
        }}
      />,
    );

    expect(screen.getByText("סריקה בתהליך")).toBeInTheDocument();
    expect(screen.getByText("מנועי ההשוואה מנתחים את הקבצים")).toBeInTheDocument();
    expect(screen.getByText("משווה בין אלבומים")).toBeInTheDocument();
    expect(screen.getByText("21/50")).toBeInTheDocument();
    expect(screen.getByText("פריטים שעובדו")).toBeInTheDocument();
    expect(screen.getByText("סטטוס")).toBeInTheDocument();
  });

  it("renders the summary screen with the current actions", () => {
    render(
      <SummaryScreen
        summary={{
          counts: {
            safe_clusters: 4,
            review_clusters: 2,
            compared_pairs: 17,
            folders: 11,
          },
        }}
        onStartReview={vi.fn()}
        onBackToSetup={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "הסריקה הושלמה בהצלחה" })).toBeInTheDocument();
    expect(screen.getByText("המידע מוכן למעבר")).toBeInTheDocument();
    expect(screen.getByText("בטוחים למחיקה")).toBeInTheDocument();
    expect(screen.getByText("דורשים סקירה")).toBeInTheDocument();
    expect(screen.getByText("זוגות שהושוו")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "סריקה חדשה" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "פתח סביבת עבודה" })).toBeInTheDocument();
  });

  it("renders the finalize screen and opens a confirmation before delete", async () => {
    const onKeepAllCopies = vi.fn();

    render(
      <FinalizeDeletionScreen
        workflow={{
          pendingGroups: [
            {
              cluster: {
                cluster_id: "cluster-1",
                human_summary: "עותק ארכיון מול עותק ראשי.",
                confidence_bucket: "review",
                albums: [
                  { folder_id: "keeper-1", name: "Best", is_deleted: false },
                  { folder_id: "pending-1", name: "Archive Copy", is_deleted: false },
                ],
              },
              keeper: {
                folder_id: "keeper-1",
                name: "Best",
                path: "D:/Music/Best",
                file_count: 10,
                total_size_mb: 120,
              },
              pending: [
                {
                  folder_id: "pending-1",
                  name: "Archive Copy",
                  path: "E:/Archive/Best",
                  file_count: 10,
                  estimated_size_mb: 118,
                  status_label: "נבחר אוטומטית",
                  status_tone: "warning",
                },
              ],
              deleted: [],
              status: { label: "מוכן להעברה", tone: "warning" },
            },
          ],
          historyGroups: [],
          summary: {
            pendingCount: 1,
            pendingSizeMb: 118,
            autoSelectedCount: 1,
            manualSelectedCount: 0,
            deletedCount: 0,
            deletedSizeMb: 0,
            keeperCount: 1,
            failedCount: 0,
            pendingGroupCount: 1,
            historyGroupCount: 0,
          },
        }}
        onBackToReview={vi.fn()}
        onBackToSetup={vi.fn()}
        onExecute={vi.fn()}
        isExecuting={false}
        openExplorer={vi.fn()}
        onKeepAllCopies={onKeepAllCopies}
      />,
    );

    expect(screen.getByRole("heading", { name: "אישור העברה לסל המחזור (1 תיקיות)" })).toBeInTheDocument();
    expect(screen.getByText("הפריטים יסומנו לסל המחזור בלבד, ללא מחיקה לצמיתות.")).toBeInTheDocument();
    expect(screen.getByText("Archive Copy")).toBeInTheDocument();
    expect(screen.getByText("Best")).toBeInTheDocument();
    expect(screen.getByText("אפשר לבטל את ההעברה לקבוצה הזו ולהשאיר את כל העותקים.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "בטל העברה ושמור הכל" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "בטל העברה ושמור הכל" }));

    expect(onKeepAllCopies).toHaveBeenCalledWith("cluster-1");

    fireEvent.click(screen.getByRole("button", { name: "בצע מחיקה למסומנים" }));

    expect(await screen.findByText("להעביר את הפריטים המסומנים לסל המחזור?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "כן, להעביר" })).toBeInTheDocument();
  });
});
