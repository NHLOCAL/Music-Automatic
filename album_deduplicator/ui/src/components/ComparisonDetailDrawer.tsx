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
import { Copy } from '../locale';
import QualityBadge from './QualityBadge';

interface Props {
  open: boolean;
  onClose: () => void;
  comparison?: ComparisonDTO;
  copy: Copy;
}

const ComparisonDetailDrawer: React.FC<Props> = ({ open, onClose, comparison, copy }) => {
  if (!comparison) return null;
  const rows = [
    { label: copy.comparisonDetail.rows.weighted, value: `${comparison.weighted_score.toFixed(2)}%` },
    comparison.ml_similarity_score !== undefined && comparison.ml_similarity_score !== null
      ? { label: copy.comparisonDetail.rows.mlSimilarity, value: `${comparison.ml_similarity_score.toFixed(2)}%` }
      : null,
    comparison.final_combined_score !== undefined && comparison.final_combined_score !== null
      ? { label: copy.comparisonDetail.rows.combined, value: `${comparison.final_combined_score.toFixed(2)}%` }
      : null,
    comparison.is_identical_by_hash
      ? { label: copy.comparisonDetail.rows.identical, value: copy.comparisonDetail.yes }
      : { label: copy.comparisonDetail.rows.identical, value: copy.comparisonDetail.no },
    comparison.gemini_verdict ? { label: copy.comparisonDetail.rows.geminiVerdict, value: `${comparison.gemini_verdict}` } : null,
    comparison.gemini_similarity_score !== undefined && comparison.gemini_similarity_score !== null
      ? { label: copy.comparisonDetail.rows.geminiSimilarity, value: `${comparison.gemini_similarity_score.toFixed(1)}%` }
      : null,
    comparison.gemini_reason ? { label: copy.comparisonDetail.rows.geminiReason, value: comparison.gemini_reason } : null,
    comparison.gemini_error ? { label: copy.comparisonDetail.rows.geminiError, value: comparison.gemini_error } : null,
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{copy.comparisonDetail.title}</DialogTitle>
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
          <QualityBadge copy={copy} score={comparison.final_combined_score ?? comparison.weighted_score} />
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default ComparisonDetailDrawer;
