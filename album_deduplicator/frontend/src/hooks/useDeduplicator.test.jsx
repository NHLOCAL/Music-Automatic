import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDeduplicator } from "./useDeduplicator";
import * as api from "../api";

vi.mock("../api", () => ({
  getAnalysisSession: vi.fn(),
  getClusters: vi.fn(),
  getDeletePreview: vi.fn(),
  updateDecisions: vi.fn(),
  getEventSource: vi.fn(() => ({
    addEventListener: vi.fn(),
    close: vi.fn(),
  })),
}));

const baseReviewCluster = {
  cluster_id: "cluster-review-1",
  confidence_bucket: "review",
  resolution_state: "skipped",
  recommended_keeper_id: "folder-1",
  selected_delete_folder_ids: [],
  albums: [
    { folder_id: "folder-1", is_deleted: false },
    { folder_id: "folder-2", is_deleted: false },
  ],
};

const sessionResponse = {
  progress: {
    step: "completed",
    stage: "complete",
    message: "done",
    human_message: "done",
    current: 1,
    total: 1,
    percent: 100,
    warnings: [],
  },
};

const previewResponse = {
  items: [
    {
      cluster_id: "cluster-review-1",
      folder_id: "folder-2",
      selection_source: "user_selected",
    },
  ],
  total_count: 1,
  total_size_mb: 42,
  auto_selected_count: 0,
  manual_selected_count: 1,
};

describe("useDeduplicator", () => {
  beforeEach(() => {
    let currentCluster = { ...baseReviewCluster, selected_delete_folder_ids: [] };

    api.getAnalysisSession.mockResolvedValue(sessionResponse);
    api.getClusters.mockImplementation(async (_sid, bucket) => ({
      clusters: bucket === "safe" ? [currentCluster] : [currentCluster],
    }));
    api.getDeletePreview.mockResolvedValue(previewResponse);
    api.updateDecisions.mockImplementation(async () => {
      currentCluster = {
        ...currentCluster,
        resolution_state: "user_selected",
        selected_delete_folder_ids: ["folder-2"],
      };
      return previewResponse;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("creates delete selections when the user confirms the recommended keeper in a review cluster", async () => {
    const { result } = renderHook(() => useDeduplicator());

    act(() => {
      result.current.setSessionId("session-1");
      result.current.setStatus("completed");
      result.current.setClusters([{ ...baseReviewCluster, selected_delete_folder_ids: [] }]);
      result.current.setAllClusters([{ ...baseReviewCluster, selected_delete_folder_ids: [] }]);
      result.current.setDeleteSelections({ "cluster-review-1": [] });
    });

    await act(async () => {
      await result.current.handleDecision("cluster-review-1", "folder-1");
    });

    expect(api.updateDecisions).toHaveBeenCalledWith("session-1", {
      decisions: [
        {
          cluster_id: "cluster-review-1",
          keeper_id: "folder-1",
          delete_folder_ids: ["folder-2"],
        },
      ],
    });

    await waitFor(() => {
      expect(result.current.preview.total_count).toBe(1);
      expect(result.current.deleteSelections["cluster-review-1"]).toEqual(["folder-2"]);
      expect(result.current.decisions["cluster-review-1"]).toBe("folder-1");
    });
  });
});
