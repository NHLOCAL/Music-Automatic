import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkflowRail } from "./WorkflowRail";

function getStep(key) {
  return screen.getByTestId(`workflow-step-${key}`).closest(".ant-steps-item");
}

describe("WorkflowRail", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders labels, badges, active step, and disabled states", () => {
    render(
      <WorkflowRail
        activeStep="summary"
        onNavigate={vi.fn()}
        steps={[
          { key: "setup", title: "בחירה", description: "בחרו תיקיות", enabled: true, badges: [] },
          { key: "scanning", title: "סריקה", description: "סריקה פעילה", enabled: false, badges: [<span key="scan">42%</span>] },
          { key: "summary", title: "סיכום", description: "מבט מהיר", enabled: true, badges: [<span key="safe">4 בטוחות</span>, <span key="review">2 לסקירה</span>] },
          { key: "review", title: "סקירה", description: "בחירת keeper", enabled: true, badges: [] },
          { key: "finalize", title: "העברה", description: "אימות אחרון", enabled: true, badges: [<span key="finalize">1 למחיקה</span>] },
        ]}
      />,
    );

    expect(screen.getByText("בחירה")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByText("4 בטוחות")).toBeInTheDocument();
    expect(screen.getByText("2 לסקירה")).toBeInTheDocument();
    expect(screen.getByText("1 למחיקה")).toBeInTheDocument();
    expect(getStep("summary")).toHaveClass("ant-steps-item-active");
    expect(getStep("scanning")).toHaveClass("ant-steps-item-disabled");
  });

  it("navigates only to enabled steps", () => {
    const onNavigate = vi.fn();

    render(
      <WorkflowRail
        activeStep="setup"
        onNavigate={onNavigate}
        steps={[
          { key: "setup", title: "בחירה", description: "בחרו תיקיות", enabled: true, badges: [] },
          { key: "scanning", title: "סריקה", description: "יופעל בהמשך", enabled: false, badges: [] },
          { key: "summary", title: "סיכום", description: "מוכן", enabled: true, badges: [] },
          { key: "review", title: "סקירה", description: "בדיקה ידנית", enabled: true, badges: [] },
          { key: "finalize", title: "העברה", description: "אישור", enabled: true, badges: [] },
        ]}
      />,
    );

    fireEvent.click(screen.getByTestId("workflow-step-summary"));
    fireEvent.click(screen.getByTestId("workflow-step-scanning"));

    expect(onNavigate).toHaveBeenCalledWith("summary");
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });
});
