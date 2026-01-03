import { CircularProgress, Container, Stack, Step, StepLabel, Stepper, Typography } from '@mui/material';
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  ComparisonDTO,
  FeatureFlagsDTO,
  JobStatusDTO,
  ScanResultDTO,
  ActionRequestDTO,
  ActionResponseDTO,
} from './types';
import {
  executeAction,
  fetchFeatures,
  fetchResults,
  pollScan,
  startScan,
} from './api/client';
import ConfigurationStep from './components/ConfigurationStep';
import ResultsExplorer from './components/ResultsExplorer';
import ActionReview from './components/ActionReview';
import ProgressToaster from './components/ProgressToaster';

const steps = ['Configuration', 'Results exploration', 'Action review'];

function App() {
  const [activeStep, setActiveStep] = useState(0);
  const [folders, setFolders] = useState<string[]>([]);
  const [enableHashing, setEnableHashing] = useState(true);
  const [useML, setUseML] = useState(false);
  const [useGemini, setUseGemini] = useState(false);
  const [preferredBitrate, setPreferredBitrate] = useState('high');
  const [minimumScore, setMinimumScore] = useState(70);
  const [selected, setSelected] = useState<ComparisonDTO[]>([]);
  const [jobId, setJobId] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{ open: boolean; severity: 'success' | 'info' | 'warning' | 'error'; message: string }>(
    { open: false, severity: 'info', message: '' }
  );

  const featuresQuery = useQuery<FeatureFlagsDTO>({ queryKey: ['features'], queryFn: fetchFeatures });

  const statusQuery = useQuery<JobStatusDTO | undefined>({
    queryKey: ['job-status', jobId],
    enabled: Boolean(jobId),
    queryFn: () => pollScan(jobId as string),
    refetchInterval: (data) => (data && data.status === 'completed' ? false : 1500),
  });

  const resultsQuery = useQuery<ScanResultDTO>({
    queryKey: ['results', jobId],
    enabled: statusQuery.data?.status === 'completed',
    queryFn: () => fetchResults(jobId as string),
  });

  const startMutation = useMutation<JobStatusDTO, Error, void>({
    mutationFn: async () => {
      const status = await startScan(folders, {
        force_rescan: true,
        enable_hashing: enableHashing,
        ml_scoring: useML,
        gemini_enabled: useGemini,
        preferred_bitrate: preferredBitrate,
      });
      return status;
    },
    onSuccess: (data) => {
      setJobId(data.id);
      setActiveStep(1);
      setToast({ open: true, severity: 'info', message: 'Scan started. This may take a while...' });
    },
    onError: (err) => {
      setToast({ open: true, severity: 'error', message: `Failed to start scan: ${err.message}` });
    },
  });

  const actionMutation = useMutation<ActionResponseDTO, Error, ActionRequestDTO>({
    mutationFn: executeAction,
    onSuccess: (resp) => {
      setToast({ open: true, severity: 'success', message: `Merge executed for ${resp.processed} pair(s).` });
      setActiveStep(2);
    },
    onError: (err) => setToast({ open: true, severity: 'error', message: `Action failed: ${err.message}` }),
  });

  useEffect(() => {
    if (statusQuery.data?.status === 'completed') {
      setActiveStep(1);
      setToast({ open: true, severity: 'success', message: 'Scan completed. Explore the results below.' });
    }
    if (statusQuery.data?.status === 'failed') {
      setToast({ open: true, severity: 'error', message: 'Scan failed. Check backend logs for details.' });
    }
  }, [statusQuery.data]);

  const comparisons = useMemo(() => resultsQuery.data?.comparisons ?? [], [resultsQuery.data]);

  const toggleSelect = (comparison: ComparisonDTO) => {
    const exists = selected.some((s) => s.folder1 === comparison.folder1 && s.folder2 === comparison.folder2);
    if (exists) {
      setSelected(selected.filter((s) => !(s.folder1 === comparison.folder1 && s.folder2 === comparison.folder2)));
    } else {
      setSelected([...selected, comparison]);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={3}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Album deduplicator
        </Typography>
        <Stepper activeStep={activeStep} alternativeLabel>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {activeStep === 0 && (
          <ConfigurationStep
            features={featuresQuery.data}
            folders={folders}
            onFoldersChange={setFolders}
            enableHashing={enableHashing}
            onEnableHashingChange={setEnableHashing}
            useML={useML}
            onUseMLChange={setUseML}
            useGemini={useGemini}
            onUseGeminiChange={setUseGemini}
            preferredBitrate={preferredBitrate}
            onPreferredBitrateChange={setPreferredBitrate}
            onStart={() => startMutation.mutate()}
            isStarting={startMutation.isPending}
          />
        )}

        {activeStep >= 1 && (
          <Stack spacing={2}>
            {statusQuery.isFetching && (
              <Stack direction="row" spacing={1} alignItems="center">
                <CircularProgress size={20} />
                <Typography color="text.secondary">{statusQuery.data?.message ?? 'Working...'}</Typography>
              </Stack>
            )}
            <ResultsExplorer
              comparisons={comparisons}
              minimumScore={minimumScore}
              onMinimumScoreChange={setMinimumScore}
              selected={selected}
              onToggleSelect={toggleSelect}
            />
          </Stack>
        )}

        {activeStep >= 1 && (
          <ActionReview
            selected={selected}
            onExecute={() => {
              if (!jobId) return;
              const payload: ActionRequestDTO = { job_id: jobId, pairs: selected.map((s) => [s.folder1, s.folder2]), action: 'merge' };
              actionMutation.mutate(payload);
            }}
          />
        )}
      </Stack>

      <ProgressToaster
        open={toast.open}
        severity={toast.severity}
        message={toast.message}
        onClose={() => setToast({ ...toast, open: false })}
      />
    </Container>
  );
}

export default App;
