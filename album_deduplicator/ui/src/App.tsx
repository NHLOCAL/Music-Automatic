import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';
import { prefixer } from 'stylis';
import rtlPlugin from 'stylis-plugin-rtl';
import {
  Box,
  CircularProgress,
  Container,
  Paper,
  Stack,
  Step,
  StepLabel,
  Stepper,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  createTheme,
  ThemeProvider,
  Chip,
} from '@mui/material';
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
import { executeAction, fetchFeatures, fetchResults, pollScan, startScan } from './api/client';
import ConfigurationStep from './components/ConfigurationStep';
import ResultsExplorer from './components/ResultsExplorer';
import ActionReview from './components/ActionReview';
import ProgressToaster from './components/ProgressToaster';
import { Copy, Language, translations } from './locale';

function App() {
  const [activeStep, setActiveStep] = useState(0);
  const [language, setLanguage] = useState<Language>('en');
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

  const copy: Copy = translations[language];
  const dir = language === 'he' ? 'rtl' : 'ltr';

  const theme = useMemo(
    () =>
      createTheme({
        direction: dir,
        typography: {
          fontFamily: '"Assistant", "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
        palette: {
          mode: 'light',
          primary: {
            main: '#6d5dfc',
          },
          secondary: {
            main: '#22d3ee',
          },
          background: {
            default: '#f6f7fb',
            paper: '#ffffff',
          },
        },
        shape: { borderRadius: 14 },
        components: {
          MuiCard: {
            defaultProps: { elevation: 0 },
            styleOverrides: {
              root: {
                borderColor: 'rgba(109,93,252,0.12)',
                boxShadow: '0 12px 30px rgba(25, 23, 49, 0.06)',
              },
            },
          },
          MuiPaper: {
            styleOverrides: {
              root: { boxShadow: '0 10px 40px rgba(25, 23, 49, 0.04)' },
            },
          },
          MuiButton: {
            styleOverrides: {
              root: { textTransform: 'none', fontWeight: 600 },
            },
          },
          MuiStepIcon: {
            styleOverrides: {
              root: { color: 'rgba(109,93,252,0.3)' },
              text: { fill: '#ffffff' },
            },
          },
        },
      }),
    [dir]
  );

  const ltrCache = useMemo(() => createCache({ key: 'mui', stylisPlugins: [prefixer] }), []);
  const rtlCache = useMemo(() => createCache({ key: 'mui-rtl', stylisPlugins: [prefixer, rtlPlugin] }), []);
  const cache = dir === 'rtl' ? rtlCache : ltrCache;

  useEffect(() => {
    document.body.dir = dir;
  }, [dir]);

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
      setToast({ open: true, severity: 'info', message: copy.toasts.scanStarted });
    },
    onError: (err) => {
      setToast({ open: true, severity: 'error', message: copy.toasts.scanStartError(err.message) });
    },
  });

  const actionMutation = useMutation<ActionResponseDTO, Error, ActionRequestDTO>({
    mutationFn: executeAction,
    onSuccess: (resp) => {
      setToast({ open: true, severity: 'success', message: copy.toasts.mergeSuccess(resp.processed) });
      setActiveStep(2);
    },
    onError: (err) => setToast({ open: true, severity: 'error', message: copy.toasts.mergeError(err.message) }),
  });

  useEffect(() => {
    if (statusQuery.data?.status === 'completed') {
      setActiveStep(1);
      setToast({ open: true, severity: 'success', message: copy.toasts.scanCompleted });
    }
    if (statusQuery.data?.status === 'failed') {
      setToast({ open: true, severity: 'error', message: copy.toasts.scanFailed });
    }
  }, [statusQuery.data, copy]);

  const comparisons = useMemo(() => resultsQuery.data?.comparisons ?? [], [resultsQuery.data]);

  const toggleSelect = (comparison: ComparisonDTO) => {
    const exists = selected.some((s) => s.folder1 === comparison.folder1 && s.folder2 === comparison.folder2);
    if (exists) {
      setSelected(selected.filter((s) => !(s.folder1 === comparison.folder1 && s.folder2 === comparison.folder2)));
    } else {
      setSelected([...selected, comparison]);
    }
  };

  const hero = (
    <Box
      sx={{
        background: 'radial-gradient(circle at 20% 20%, rgba(34,211,238,0.2), transparent 30%), linear-gradient(120deg, #0f172a, #111827)',
        color: 'common.white',
        pb: { xs: 4, md: 6 },
        pt: { xs: 3, md: 5 },
        mb: 2,
      }}
    >
      <Container maxWidth="lg">
        <Stack spacing={3}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems="flex-start">
            <Box>
              <Chip
                label={copy.heroTag}
                color="secondary"
                variant="filled"
                sx={{ mb: 1, fontWeight: 700, px: 1.5, bgcolor: 'rgba(34,211,238,0.2)' }}
              />
              <Typography variant="h3" fontWeight={800} gutterBottom>
                {copy.title}
              </Typography>
              <Typography variant="h6" color="rgba(255,255,255,0.85)">
                {copy.subtitle}
              </Typography>
            </Box>
            <Paper sx={{ p: 2, minWidth: 260 }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                {copy.languageLabel}
              </Typography>
              <ToggleButtonGroup
                fullWidth
                exclusive
                value={language}
                onChange={(_, value) => value && setLanguage(value)}
                color="primary"
              >
                <ToggleButton value="en">{copy.languageNames.en}</ToggleButton>
                <ToggleButton value="he">{copy.languageNames.he}</ToggleButton>
              </ToggleButtonGroup>
            </Paper>
          </Stack>
          <Paper sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)' }}>
            <Stepper activeStep={activeStep} alternativeLabel>
              {copy.steps.map((label) => (
                <Step key={label}>
                  <StepLabel>
                    <Typography color="inherit" fontWeight={600}>
                      {label}
                    </Typography>
                  </StepLabel>
                </Step>
              ))}
            </Stepper>
          </Paper>
        </Stack>
      </Container>
    </Box>
  );

  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={theme}>
        <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
          {hero}
          <Container maxWidth="lg" sx={{ pb: 6 }}>
            <Stack spacing={3}>
              <ConfigurationStep
                copy={copy}
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

              {activeStep >= 1 ? (
                <Stack spacing={2}>
                  {statusQuery.isFetching && (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <CircularProgress size={20} />
                      <Typography color="text.secondary">{statusQuery.data?.message ?? copy.statuses.working}</Typography>
                    </Stack>
                  )}
                  <ResultsExplorer
                    copy={copy}
                    comparisons={comparisons}
                    minimumScore={minimumScore}
                    onMinimumScoreChange={setMinimumScore}
                    selected={selected}
                    onToggleSelect={toggleSelect}
                  />
                </Stack>
              ) : (
                <Paper variant="outlined" sx={{ p: 3 }}>
                  <Typography color="text.secondary">{copy.resultsExplorer.noRows}</Typography>
                </Paper>
              )}

              {activeStep >= 1 && (
                <ActionReview
                  copy={copy}
                  selected={selected}
                  onExecute={() => {
                    if (!jobId) return;
                    const payload: ActionRequestDTO = { job_id: jobId, pairs: selected.map((s) => [s.folder1, s.folder2]), action: 'merge' };
                    actionMutation.mutate(payload);
                  }}
                />
              )}
            </Stack>
          </Container>

          <ProgressToaster
            open={toast.open}
            severity={toast.severity}
            message={toast.message}
            onClose={() => setToast({ ...toast, open: false })}
          />
        </Box>
      </ThemeProvider>
    </CacheProvider>
  );
}

export default App;
