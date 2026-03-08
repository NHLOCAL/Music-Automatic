import { render } from "@testing-library/react";
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
        algorithmic_score: 87,
        ml_score: 89,
        base_score: 88.1,
        gemini_score: null,
        final_score: 88.1,
        is_identical_by_hash: false,
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
        algorithmic_score: 95,
        ml_score: 96,
        base_score: 95.6,
        gemini_score: null,
        final_score: 95.6,
        is_identical_by_hash: false,
      },
    ],
    albums: [
      { folder_id: "folder-c", name: "Ready Copy", is_deleted: false },
      { folder_id: "folder-d", name: "Ready Copy", is_deleted: false },
    ],
  },
];

describe("ClusterList", () => {
  it("places reviewed-ready clusters before pending review clusters", () => {
    const { container } = render(
      <ClusterList
        clusters={clusters}
        selectedClusterId="cluster-ready"
        setSelectedClusterId={vi.fn()}
        decisions={{ "cluster-ready": "folder-c" }}
        selectedTab="review"
        setSelectedTab={vi.fn()}
      />,
    );

    const cards = Array.from(container.querySelectorAll(".cluster-card"));

    expect(cards).toHaveLength(2);
    expect(cards[0].textContent).toContain("Ready Copy");
    expect(cards[0].textContent).toContain("נבדק ומוכן");
    expect(cards[0].textContent).toContain("סופי 95.6");
    expect(cards[1].textContent).toContain("Pending Copy");
  });
});
