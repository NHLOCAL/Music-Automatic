import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ClusterList } from "./ClusterList";

const { renderScoreButton } = vi.hoisted(() => ({ renderScoreButton: vi.fn() }));
vi.mock("./ScoreTransparencyPanel", () => ({
  ScoreInfoButton: (props) => { renderScoreButton(props.cluster.cluster_id); return null; },
}));

describe("ClusterList rendering", () => {
  it("rerenders only the changed selection and decision rows in a large list", () => {
    const clusters = Array.from({ length: 200 }, (_, index) => ({
      cluster_id: `cluster-${index}`, confidence_bucket: "review", resolution_state: "skipped",
      albums: [{ folder_id: `${index}-a`, name: `Album ${index}` }, { folder_id: `${index}-b`, name: `Album ${index}` }],
      pairs: [],
    }));
    const onSelect = vi.fn();
    const onTab = vi.fn();
    const props = { clusters, decisions: {}, selectedTab: "review", setSelectedClusterId: onSelect, setSelectedTab: onTab };
    const { rerender } = render(<ClusterList {...props} selectedClusterId="cluster-0" />);
    renderScoreButton.mockClear();
    rerender(<ClusterList {...props} selectedClusterId="cluster-1" />);
    expect(renderScoreButton.mock.calls.flat()).toEqual(["cluster-0", "cluster-1"]);
    renderScoreButton.mockClear();
    rerender(<ClusterList {...props} decisions={{ "cluster-5": "5-a" }} selectedClusterId="cluster-1" />);
    expect(renderScoreButton.mock.calls.flat()).toEqual(["cluster-5"]);
  });
});
