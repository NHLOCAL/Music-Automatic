import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FinalizeDeletionScreen } from "./FinalizeDeletionScreen";
import { ScanningScreen } from "./ScanningScreen";
import { SummaryScreen } from "./SummaryScreen";

describe("Workflow screens", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the scanning screen with a compact progress summary and stable status panels", () => {
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

    expect(screen.getByText("סריקה חכמה בתהליך")).toBeInTheDocument();
    expect(screen.getByText("מנועי ההשוואה עובדים")).toBeInTheDocument();
    expect(screen.getByText("משווה בין אלבומים")).toBeInTheDocument();
    expect(screen.getByTestId("scanning-stage-strip")).toBeInTheDocument();
    expect(screen.getByTestId("scanning-status-grid")).toBeInTheDocument();
    expect(screen.getByText("התקדמות כוללת")).toBeInTheDocument();
    expect(screen.getByText("21/50 פריטים עובדו")).toBeInTheDocument();
    expect(screen.getByText("שלב פעיל")).toBeInTheDocument();
    expect(screen.getByText("התקדמות")).toBeInTheDocument();
    expect(screen.getByText("מצב")).toBeInTheDocument();
    expect(screen.getAllByText("משווה ובונה קבוצות").length).toBeGreaterThan(0);
    expect(screen.getByText("21/50")).toBeInTheDocument();
    expect(screen.getByText("ניתוח בלבד")).toBeInTheDocument();
    expect(screen.getByText("4 מתוך 4 שלבי ניתוח פעילים עכשיו.")).toBeInTheDocument();
  });

  it("renders the summary screen with the refreshed desktop stat grid", () => {
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

    expect(screen.getByText("הסריקה הושלמה!")).toBeInTheDocument();
    expect(screen.getByText("מוכן למעבר על התוצאות")).toBeInTheDocument();
    expect(screen.getByText("כל ההחלטות עדיין הפיכות לפני שלב ההעברה.")).toBeInTheDocument();
    expect(screen.getByTestId("summary-stats")).toBeInTheDocument();
    expect(screen.getByText("בטוח למחיקה")).toBeInTheDocument();
    expect(screen.getByText("דורש בדיקה")).toBeInTheDocument();
    expect(screen.getByText("זוגות שנבדקו")).toBeInTheDocument();
    expect(screen.getByText("11 תיקיות השתתפו בניתוח הנוכחי.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "סריקה חדשה" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "התחל לעבור על התוצאות" })).toBeInTheDocument();
  });

  it("renders the finalize screen with a compact overview grid before the transfer sections", () => {
    render(
      <FinalizeDeletionScreen
        workflow={{
          pendingGroups: [
            {
              cluster: {
                cluster_id: "cluster-1",
                human_summary: "עותק ארכיון מול עותק ראשי.",
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
      />,
    );

    expect(screen.getByRole("heading", { name: "מרכז ההעברה וההשוואה" })).toBeInTheDocument();
    expect(screen.getAllByText("מוכן להעברה").length).toBeGreaterThan(0);
    expect(screen.getByTestId("finalize-summary-grid")).toBeInTheDocument();
    expect(screen.getByText("ממתינות להעברה")).toBeInTheDocument();
    expect(screen.getByText("בחירה אוטומטית")).toBeInTheDocument();
    expect(screen.getByText("עותקים שנשמרו")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "העבר 1 תיקיות לסל המחזור" })).toBeInTheDocument();
    expect(screen.getByText("תיקיות שממתינות למחיקה")).toBeInTheDocument();
    expect(screen.getByText("העותק שנשמר")).toBeInTheDocument();
    expect(screen.getByText("Archive Copy")).toBeInTheDocument();
  });
});
