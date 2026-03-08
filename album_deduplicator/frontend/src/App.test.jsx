import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.stubGlobal("fetch", vi.fn());

describe("App", () => {
  it("renders the minimal analysis flow", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: "התחל ניתוח" })).toBeInTheDocument();
    expect(screen.getByText("ML פעיל כברירת מחדל.")).toBeInTheDocument();
    expect(screen.getByText("בטוח למחיקה")).toBeInTheDocument();
  });
});
