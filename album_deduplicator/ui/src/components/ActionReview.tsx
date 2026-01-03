import { CheckCircle } from '@mui/icons-material';
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import React from 'react';
import { ComparisonDTO } from '../types';
import ActionConfirmationDialog from './ActionConfirmationDialog';
import QualityBadge from './QualityBadge';

interface Props {
  selected: ComparisonDTO[];
  onExecute: () => void;
}

const ActionReview: React.FC<Props> = ({ selected, onExecute }) => {
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems="center">
          <Box>
            <Typography variant="h6">Action review</Typography>
            <Typography color="text.secondary">
              {selected.length ? `${selected.length} pairs selected for merge` : 'Select pairs to enable merge actions.'}
            </Typography>
          </Box>
          <Button
            startIcon={<CheckCircle />}
            variant="contained"
            color="primary"
            disabled={!selected.length}
            onClick={() => setConfirmOpen(true)}
          >
            Merge selected
          </Button>
        </Stack>
        <Stack spacing={1} mt={2}>
          {selected.map((c) => (
            <Stack key={`${c.folder1}-${c.folder2}`} direction="row" spacing={1} alignItems="center">
              <QualityBadge score={c.final_combined_score ?? c.weighted_score} />
              <Typography variant="body2">{c.folder1}</Typography>
              <Chip label="↔" />
              <Typography variant="body2">{c.folder2}</Typography>
            </Stack>
          ))}
          {!selected.length && <Typography color="text.secondary">No pairs selected yet.</Typography>}
        </Stack>
      </CardContent>
      <ActionConfirmationDialog
        open={confirmOpen}
        count={selected.length}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          onExecute();
        }}
      />
    </Card>
  );
};

export default ActionReview;
