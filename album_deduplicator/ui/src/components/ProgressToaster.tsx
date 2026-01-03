import { Alert, Snackbar } from '@mui/material';
import React from 'react';

interface Props {
  open: boolean;
  severity: 'success' | 'info' | 'warning' | 'error';
  message: string;
  onClose: () => void;
}

const ProgressToaster: React.FC<Props> = ({ open, severity, message, onClose }) => (
  <Snackbar open={open} autoHideDuration={5000} onClose={onClose} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
    <Alert severity={severity} onClose={onClose} variant="filled" sx={{ width: '100%' }}>
      {message}
    </Alert>
  </Snackbar>
);

export default ProgressToaster;
