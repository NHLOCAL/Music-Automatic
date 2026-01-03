import { Add, Folder } from '@mui/icons-material';
import { Box, Button, Chip, Stack, TextField, Typography } from '@mui/material';
import React, { useState } from 'react';
import { Copy } from '../locale';

interface Props {
  copy: Copy;
  folders: string[];
  onChange: (next: string[]) => void;
}

const FolderSelector: React.FC<Props> = ({ copy, folders, onChange }) => {
  const [current, setCurrent] = useState('');

  const addFolder = () => {
    if (!current.trim()) return;
    onChange([...folders, current.trim()]);
    setCurrent('');
  };

  const removeFolder = (path: string) => {
    onChange(folders.filter((f) => f !== path));
  };

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom color="text.secondary">
        {copy.folderSelector.title}
      </Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
        <TextField
          fullWidth
          label={copy.folderSelector.placeholder}
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          InputProps={{ startAdornment: <Folder color="primary" sx={{ mr: 1 }} /> }}
        />
        <Button startIcon={<Add />} variant="contained" onClick={addFolder} disabled={!current.trim()}>
          {copy.folderSelector.add}
        </Button>
      </Stack>
      <Stack direction="row" spacing={1} mt={2} flexWrap="wrap">
        {folders.map((folder) => (
          <Chip key={folder} label={folder} onDelete={() => removeFolder(folder)} color="primary" variant="outlined" />
        ))}
        {!folders.length && <Typography color="text.secondary">{copy.folderSelector.empty}</Typography>}
      </Stack>
    </Box>
  );
};

export default FolderSelector;
