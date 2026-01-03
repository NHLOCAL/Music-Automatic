import { Info } from '@mui/icons-material';
import {
  Box,
  Card,
  CardContent,
  Chip,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import React from 'react';
import { ComparisonDTO } from '../types';
import ComparisonDetailDrawer from './ComparisonDetailDrawer';
import QualityBadge from './QualityBadge';
import SimilarityFilter from './SimilarityFilter';

interface Props {
  comparisons: ComparisonDTO[];
  minimumScore: number;
  onMinimumScoreChange: (value: number) => void;
  selected: ComparisonDTO[];
  onToggleSelect: (comparison: ComparisonDTO) => void;
}

const ResultsExplorer: React.FC<Props> = ({ comparisons, minimumScore, onMinimumScoreChange, selected, onToggleSelect }) => {
  const [detail, setDetail] = React.useState<ComparisonDTO | undefined>(undefined);

  const visible = comparisons.filter((c) => (c.final_combined_score ?? c.weighted_score) >= minimumScore);
  const isSelected = (c: ComparisonDTO) => selected.some((s) => s.folder1 === c.folder1 && s.folder2 === c.folder2);

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ xs: 'flex-start', md: 'center' }}>
          <SimilarityFilter value={minimumScore} onChange={onMinimumScoreChange} />
          <Typography color="text.secondary">{visible.length} pairs visible</Typography>
        </Stack>
        <Box mt={2}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pair</TableCell>
                <TableCell>Scores</TableCell>
                <TableCell>Gemini</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {visible.map((c) => (
                <TableRow
                  key={`${c.folder1}-${c.folder2}`}
                  hover
                  onClick={() => onToggleSelect(c)}
                  selected={isSelected(c)}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell>
                    <Stack spacing={0.5}>
                      <Typography variant="body2" color="text.primary">
                        {c.folder1}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {c.folder2}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <QualityBadge score={c.final_combined_score ?? c.weighted_score} />
                      {c.ml_similarity_score && <Chip size="small" color="info" label={`ML ${c.ml_similarity_score.toFixed(1)}%`} />}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {c.gemini_verdict ? (
                      <Chip size="small" color="secondary" label={c.gemini_verdict} />
                    ) : (
                      <Chip size="small" label="Not evaluated" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View details">
                      <IconButton onClick={(e) => { e.stopPropagation(); setDetail(c); }}>
                        <Info />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {!visible.length && (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography color="text.secondary">No comparisons meet the filter yet.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Box>
      </CardContent>
      <ComparisonDetailDrawer open={Boolean(detail)} onClose={() => setDetail(undefined)} comparison={detail} />
    </Card>
  );
};

export default ResultsExplorer;
