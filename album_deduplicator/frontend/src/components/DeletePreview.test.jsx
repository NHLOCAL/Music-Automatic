import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DeletePreview } from "./DeletePreview";

describe("DeletePreview", () => {
  it("renders the compact workflow summary with pending, completed and failed counts", () => {
    render(
      <DeletePreview
        workflowSummary={{
          pendingCount: 3,
          pendingSizeMb: 128.4,
          deletedCount: 1,
          failedCount: 2,
        }}
        onOpenFinalize={vi.fn()}
        isExecuting={false}
      />,
    );

    expect(screen.getByText("מוכנות להעברה")).toBeInTheDocument();
    expect(screen.getByText("שלב ההעברה הסופי מוכן")).toBeInTheDocument();
    expect(screen.getByText("3 ממתינות")).toBeInTheDocument();
    expect(screen.getByText("1 הועברו")).toBeInTheDocument();
    expect(screen.getByText("2 דורשות טיפול")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "פתח את שלב ההעברה" })).toBeInTheDocument();
  });
});
