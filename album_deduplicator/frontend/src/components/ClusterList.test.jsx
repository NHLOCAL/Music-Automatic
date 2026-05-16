import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ClusterList } from "./ClusterList";

const clusters = [
  {
    cluster_id: "cluster-pending",
    confidence_bucket: "review",
    recommended_keeper_id: "folder-a",
    resolution_state: "skipped",
    pairs: [
      {
        pair_id: "pair-pending",
        folder1_id: "folder-a",
        folder2_id: "folder-b",
        final_score: 88.1,
      },
    ],
    albums: [
      { folder_id: "folder-a", name: "Pending Copy", is_deleted: false },
      { folder_id: "folder-b", name: "Pending Copy", is_deleted: false },
    ],
  },
  {
    cluster_id: "cluster-ready",
    confidence_bucket: "review",
    recommended_keeper_id: "folder-c",
    resolution_state: "manual",
    pairs: [
      {
        pair_id: "pair-ready",
        folder1_id: "folder-c",
        folder2_id: "folder-d",
        final_score: 95.6,
      },
    ],
    albums: [
      { folder_id: "folder-c", name: "Ready Copy", is_deleted: false },
      { folder_id: "folder-d", name: "Ready Copy", is_deleted: false },
    ],
  },
  {
    cluster_id: "cluster-completed",
    confidence_bucket: "review",
    recommended_keeper_id: "folder-e",
    resolution_state: "deleted",
    pairs: [
      {
        pair_id: "pair-completed",
        folder1_id: "folder-e",
        folder2_id: "folder-f",
        final_score: 91.2,
      },
    ],
    albums: [
      { folder_id: "folder-e", name: "Completed Copy", is_deleted: false },
      { folder_id: "folder-f", name: "Completed Copy", is_deleted: true },
    ],
  },
];

describe("ClusterList", () => {
  it("keeps the original cluster order after a cluster is marked ready", () => {
    const { container } = render(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-pending"
        setSelectedClusterId={vi.fn()}
        decisions={{ "cluster-ready": "folder-c" }}
        selectedTab="review"
        setSelectedTab={vi.fn()}
      />,
    );

    const items = Array.from(container.querySelectorAll(".ide-cluster-item"));

    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("Pending Copy");
    expect(items[0].textContent).toContain("ממתין לסקירה");
    expect(items[1].textContent).toContain("Ready Copy");
    expect(items[1].textContent).toContain("נבדק ומוכן");
    expect(items[1].textContent).toContain("התאמה: 95.6/100");
    expect(screen.getByTestId("cluster-scroll")).toBeInTheDocument();
  });

  it("moves clusters with fewer than two visible albums into the completed segment", () => {
    const { container, rerender } = render(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-pending"
        setSelectedClusterId={vi.fn()}
        decisions={{}}
        selectedTab="review"
        setSelectedTab={vi.fn()}
      />,
    );

    expect(container.textContent).toContain("Pending Copy");
    expect(container.textContent).toContain("Ready Copy");
    expect(container.textContent).not.toContain("Completed Copy");
    expect(container.textContent).not.toContain("הכל");
    expect(container.querySelector(".ide-sidebar-count").textContent).toBe("2 פריטים");

    rerender(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-completed"
        setSelectedClusterId={vi.fn()}
        decisions={{}}
        selectedTab="completed"
        setSelectedTab={vi.fn()}
      />,
    );

    expect(container.textContent).toContain("Completed Copy");
    expect(container.textContent).toContain("1 עותקים");
    expect(container.textContent).not.toContain("Pending Copy");
    expect(container.querySelector(".ide-sidebar-count").textContent).toBe("פריט אחד");
  });

  it("uses distinct icons for safe and completed segments", () => {
    const { container } = render(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-pending"
        setSelectedClusterId={vi.fn()}
        decisions={{}}
        selectedTab="safe"
        setSelectedTab={vi.fn()}
      />,
    );

    expect(container.querySelector(".anticon-safety-certificate")).toBeInTheDocument();
    expect(container.querySelector(".anticon-check-circle")).toBeInTheDocument();
  });

  it("sorts by readiness only when the user presses the sort button", () => {
    const { container, rerender } = render(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-pending"
        setSelectedClusterId={vi.fn()}
        decisions={{ "cluster-ready": "folder-c" }}
        selectedTab="review"
        setSelectedTab={vi.fn()}
      />,
    );
    const getItems = () => Array.from(container.querySelectorAll(".ide-cluster-item"));

    expect(getItems()[0].textContent).toContain("Pending Copy");

    fireEvent.click(container.querySelector(".ide-sidebar-sort-button"));

    expect(getItems()[0].textContent).toContain("Ready Copy");
    expect(getItems()[1].textContent).toContain("Pending Copy");

    rerender(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-pending"
        setSelectedClusterId={vi.fn()}
        decisions={{ "cluster-ready": "folder-c", "cluster-pending": "folder-a" }}
        selectedTab="review"
        setSelectedTab={vi.fn()}
      />,
    );

    expect(getItems()[0].textContent).toContain("Ready Copy");
    expect(getItems()[1].textContent).toContain("Pending Copy");
  });
});
