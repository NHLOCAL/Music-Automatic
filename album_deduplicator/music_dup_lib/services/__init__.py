"""Public service exports, loaded only when requested by a caller."""

from importlib import import_module


_EXPORT_MODULES = {
    "AnalysisOrchestrator": ".analysis_orchestrator",
    "AnalysisOptions": ".analysis_orchestrator",
    "AnalysisProgressEvent": ".analysis_orchestrator",
    "DeletionService": ".deletion_service",
    "AlbumCluster": ".dto",
    "AlbumSummary": ".dto",
    "AnalysisCounts": ".dto",
    "AnalysisSnapshot": ".dto",
    "AnalysisStatus": ".dto",
    "AnalysisWarnings": ".dto",
    "ComparisonHighlight": ".dto",
    "DeleteExecution": ".dto",
    "DeleteExecutionItem": ".dto",
    "DeletePreview": ".dto",
    "DeletePreviewItem": ".dto",
    "PairAnalysis": ".dto",
    "ResolutionState": ".dto",
    "RecommendationReason": ".dto",
    "RecommendationService": ".recommendation_service",
    "ScoringService": ".scoring_service",
    "GeminiSettingsStore": ".gemini_settings_store",
    "UserDecisionStore": ".user_decision_store",
    "FeedbackSummary": ".user_feedback_logger",
    "UserFeedbackLogger": ".user_feedback_logger",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
