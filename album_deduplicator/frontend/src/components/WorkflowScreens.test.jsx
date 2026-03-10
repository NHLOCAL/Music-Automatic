import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScanningScreen } from "./ScanningScreen";
import { SummaryScreen } from "./SummaryScreen";

describe("Workflow screens", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the scanning screen with animated stage cards and stable status panels", () => {
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
    expect(screen.getByText("שלב פעיל")).toBeInTheDocument();
    expect(screen.getByText("התקדמות")).toBeInTheDocument();
    expect(screen.getByText("מצב")).toBeInTheDocument();
    expect(screen.getAllByText("משווה ובונה קבוצות").length).toBeGreaterThan(0);
    expect(screen.getByText("21/50")).toBeInTheDocument();
    expect(screen.getByText("ניתוח בלבד")).toBeInTheDocument();
    expect(screen.getByText("מזהה אלבומים, קורא metadata ובודק עטיפות וקבצי שמע.")).toBeInTheDocument();
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
});
