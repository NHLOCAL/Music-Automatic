import axios from 'axios';
import {
  ActionRequestDTO,
  ActionResponseDTO,
  FeatureFlagsDTO,
  JobStatusDTO,
  ScanResultDTO,
} from '../types';

const api = axios.create({
  baseURL: '/api',
});

export const fetchFeatures = async (): Promise<FeatureFlagsDTO> => {
  const { data } = await api.get<FeatureFlagsDTO>('/features');
  return data;
};

export const startScan = async (
  folders: string[],
  options: { force_rescan: boolean; enable_hashing: boolean; ml_scoring: boolean; gemini_enabled: boolean; preferred_bitrate: string }
): Promise<JobStatusDTO> => {
  const { data } = await api.post<JobStatusDTO>('/scan', {
    folders,
    force_rescan: options.force_rescan,
    enable_hashing: options.enable_hashing,
    ml_scoring: options.ml_scoring,
    gemini_enabled: options.gemini_enabled,
    preferred_bitrate: options.preferred_bitrate,
  });
  return data;
};

export const pollScan = async (jobId: string): Promise<JobStatusDTO> => {
  const { data } = await api.get<JobStatusDTO>(`/scan/${jobId}`);
  return data;
};

export const fetchResults = async (jobId: string): Promise<ScanResultDTO> => {
  const { data } = await api.get<ScanResultDTO>(`/scan/${jobId}/results`);
  return data;
};

export const executeAction = async (payload: ActionRequestDTO): Promise<ActionResponseDTO> => {
  const { data } = await api.post<ActionResponseDTO>('/actions', payload);
  return data;
};

export default api;
