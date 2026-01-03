export interface FolderDTO {
  path: string;
  track_count: number;
  quality_score?: number | null;
  quality_breakdown: Record<string, number>;
  avg_bitrate?: number | null;
}

export interface ComparisonDTO {
  folder1: string;
  folder2: string;
  weighted_score: number;
  ml_similarity_score?: number | null;
  final_combined_score?: number | null;
  is_identical_by_hash: boolean;
  gemini_verdict?: string | null;
  gemini_similarity_score?: number | null;
  gemini_reason?: string | null;
  gemini_error?: string | null;
}

export interface ScanResultDTO {
  folders: FolderDTO[];
  comparisons: ComparisonDTO[];
}

export interface JobStatusDTO {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  errors: string[];
}

export interface FeatureFlagsDTO {
  gemini_available: boolean;
  ml_available: boolean;
}

export interface ActionRequestDTO {
  job_id: string;
  pairs: [string, string][];
  action: 'merge';
}

export interface ActionResponseDTO {
  job_id: string;
  action: string;
  processed: number;
}
