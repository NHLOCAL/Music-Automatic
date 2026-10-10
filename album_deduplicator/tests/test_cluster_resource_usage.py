from music_dup_lib.services import recommendation_service as module
from test_recommendation_service import make_folder, make_pair


def test_sparse_cluster_traverses_existing_edges_instead_of_all_possible_pairs(monkeypatch):
    folders = [make_folder(f"C:/library/{index}", float(index)) for index in range(200)]
    pairs = [make_pair(first.path, second.path, 99) for first, second in zip(folders, folders[1:])]
    allocations = []

    def counted_key(values):
        allocations.append(1)
        return frozenset(values)

    monkeypatch.setattr(module, "frozenset", counted_key, raising=False)
    service = module.RecommendationService()
    folder_map = {folder.path: folder for folder in folders}
    albums = service.build_album_summaries(folder_map)
    clusters = service.build_clusters(folder_map, {pair.pair_id: pair for pair in pairs}, albums)
    cluster = next(iter(clusters.values()))
    assert len(clusters) == 1
    assert len(cluster.folder_ids) == 200
    assert set(cluster.pair_ids) == {pair.pair_id for pair in pairs}
    assert cluster.confidence_bucket == "review"
    assert "pairwise_validation_incomplete" in cluster.reason_codes
    assert len(allocations) <= 2 * len(pairs)
