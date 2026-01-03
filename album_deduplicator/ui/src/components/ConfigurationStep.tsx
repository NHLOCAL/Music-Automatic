import { AutoAwesome, Bolt, PlayArrow } from '@mui/icons-material';
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControlLabel,
  Stack,
  Switch,
  Typography,
  MenuItem,
  TextField,
} from '@mui/material';
import React from 'react';
import { FeatureFlagsDTO } from '../types';
import FolderSelector from './FolderSelector';

interface Props {
  features?: FeatureFlagsDTO;
  folders: string[];
  onFoldersChange: (next: string[]) => void;
  enableHashing: boolean;
  onEnableHashingChange: (value: boolean) => void;
  useML: boolean;
  onUseMLChange: (value: boolean) => void;
  useGemini: boolean;
  onUseGeminiChange: (value: boolean) => void;
  preferredBitrate: string;
  onPreferredBitrateChange: (value: string) => void;
  onStart: () => void;
  isStarting: boolean;
}

const ConfigurationStep: React.FC<Props> = ({
  features,
  folders,
  onFoldersChange,
  enableHashing,
  onEnableHashingChange,
  useML,
  onUseMLChange,
  useGemini,
  onUseGeminiChange,
  preferredBitrate,
  onPreferredBitrateChange,
  onStart,
  isStarting,
}) => (
  <Card variant="outlined">
    <CardContent>
      <Stack spacing={3}>
        <FolderSelector folders={folders} onChange={onFoldersChange} />
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="center">
          <FormControlLabel
            control={<Switch checked={enableHashing} onChange={(e) => onEnableHashingChange(e.target.checked)} />}
            label="Enable hashing"
          />
          <FormControlLabel
            control={<Switch checked={useML} onChange={(e) => onUseMLChange(e.target.checked)} />}
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <Bolt fontSize="small" />
                <span>Use ML similarity</span>
                {features && (
                  <Typography variant="caption" color={features.ml_available ? 'success.main' : 'warning.main'}>
                    {features.ml_available ? 'Available' : 'Unavailable'}
                  </Typography>
                )}
              </Stack>
            }
          />
          <FormControlLabel
            control={<Switch checked={useGemini} onChange={(e) => onUseGeminiChange(e.target.checked)} />}
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <AutoAwesome fontSize="small" />
                <span>Use Gemini reasoning</span>
                {features && (
                  <Typography variant="caption" color={features.gemini_available ? 'success.main' : 'warning.main'}>
                    {features.gemini_available ? 'Available' : 'Unavailable'}
                  </Typography>
                )}
              </Stack>
            }
          />
          <TextField
            select
            label="Preferred bitrate"
            value={preferredBitrate}
            onChange={(e) => onPreferredBitrateChange(e.target.value)}
            sx={{ minWidth: 180 }}
          >
            <MenuItem value="high">High</MenuItem>
            <MenuItem value="128">128 kbps</MenuItem>
          </TextField>
        </Stack>
        <Box display="flex" justifyContent="flex-end">
          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            onClick={onStart}
            disabled={!folders.length || isStarting}
            size="large"
          >
            {isStarting ? 'Starting...' : 'Run scan'}
          </Button>
        </Box>
      </Stack>
    </CardContent>
  </Card>
);

export default ConfigurationStep;
