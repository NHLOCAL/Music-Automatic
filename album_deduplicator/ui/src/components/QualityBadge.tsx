import { Chip } from '@mui/material';
import React from 'react';
import { Copy } from '../locale';

interface Props {
  score?: number | null;
  copy: Copy;
}

const getColor = (score?: number | null) => {
  if (score === null || score === undefined) return 'default';
  if (score >= 85) return 'success';
  if (score >= 65) return 'warning';
  return 'error';
};

const QualityBadge: React.FC<Props> = ({ score, copy }) => {
  const label = score === null || score === undefined ? copy.qualityBadge.unknown : copy.qualityBadge.quality(score);
  return <Chip size="small" color={getColor(score)} label={label} variant="outlined" />;
};

export default QualityBadge;
