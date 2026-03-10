import { render, screen } from "@testing-library/react";
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
];

describe("ClusterList", () => {
  it("places reviewed-ready clusters before pending review clusters and shows the status tag", () => {
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
    expect(items[0].textContent).toContain("Ready Copy");
    expect(items[0].textContent).toContain("נבדק ומוכן");
    expect(items[0].textContent).toContain("התאמה: 95.6/100");
    expect(items[1].textContent).toContain("Pending Copy");
    expect(items[1].textContent).toContain("ממתין לסקירה");
    expect(screen.getByTestId("cluster-scroll")).toBeInTheDocument();
  });
});
