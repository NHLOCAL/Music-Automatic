import { Slider, Stack, Typography } from '@mui/material';
import React from 'react';
import { Copy } from '../locale';

interface Props {
  copy: Copy;
  value: number;
  onChange: (next: number) => void;
}

const SimilarityFilter: React.FC<Props> = ({ copy, value, onChange }) => (
  <Stack spacing={1} sx={{ minWidth: 240 }}>
    <Typography variant="subtitle2" color="text.secondary">
      {copy.similarityFilter.label(value)}
    </Typography>
    <Slider
      value={value}
      onChange={(_, v) => onChange(v as number)}
      valueLabelDisplay="auto"
      step={5}
      marks
      min={50}
      max={100}
    />
  </Stack>
);

export default SimilarityFilter;
