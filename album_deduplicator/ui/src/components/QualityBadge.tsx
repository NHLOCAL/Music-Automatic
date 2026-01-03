import { Chip } from '@mui/material';
import React from 'react';

interface Props {
  score?: number | null;
}

const getColor = (score?: number | null) => {
  if (score === null || score === undefined) return 'default';
  if (score >= 85) return 'success';
  if (score >= 65) return 'warning';
  return 'error';
};

const QualityBadge: React.FC<Props> = ({ score }) => {
  const label = score === null || score === undefined ? 'Unknown quality' : `${score.toFixed(1)}% quality`;
  return <Chip size="small" color={getColor(score)} label={label} variant="outlined" />;
};

export default QualityBadge;
