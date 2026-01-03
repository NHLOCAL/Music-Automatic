import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import React from 'react';
import { ComparisonDTO } from '../types';
import QualityBadge from './QualityBadge';

interface Props {
  open: boolean;
  onClose: () => void;
  comparison?: ComparisonDTO;
}

const ComparisonDetailDrawer: React.FC<Props> = ({ open, onClose, comparison }) => {
  if (!comparison) return null;
  const rows = [
    { label: 'Weighted score', value: `${comparison.weighted_score.toFixed(2)}%` },
    comparison.ml_similarity_score !== undefined && comparison.ml_similarity_score !== null
      ? { label: 'ML similarity', value: `${comparison.ml_similarity_score.toFixed(2)}%` }
      : null,
    comparison.final_combined_score !== undefined && comparison.final_combined_score !== null
      ? { label: 'Combined score', value: `${comparison.final_combined_score.toFixed(2)}%` }
      : null,
    comparison.is_identical_by_hash ? { label: 'Identical by hash', value: 'Yes' } : null,
    comparison.gemini_verdict ? { label: 'Gemini verdict', value: `${comparison.gemini_verdict}` } : null,
    comparison.gemini_similarity_score !== undefined && comparison.gemini_similarity_score !== null
      ? { label: 'Gemini similarity', value: `${comparison.gemini_similarity_score.toFixed(1)}%` }
      : null,
    comparison.gemini_reason ? { label: 'Gemini reason', value: comparison.gemini_reason } : null,
    comparison.gemini_error ? { label: 'Gemini error', value: comparison.gemini_error } : null,
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Comparison details</DialogTitle>
      <DialogContent>
        <Stack spacing={1} mb={2}>
          <Typography variant="body2" color="text.secondary">
            {comparison.folder1}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {comparison.folder2}
          </Typography>
        </Stack>
        <Divider sx={{ my: 1 }} />
        <List>
          {rows.map((row) => (
            <ListItem key={row.label} disableGutters>
              <ListItemText primary={row.label} secondary={row.value} />
            </ListItem>
          ))}
        </List>
        <Box mt={2}>
          <QualityBadge score={comparison.final_combined_score ?? comparison.weighted_score} />
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default ComparisonDetailDrawer;
