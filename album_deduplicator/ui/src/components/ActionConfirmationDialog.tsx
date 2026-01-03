import { Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Button } from '@mui/material';
import React from 'react';
import { Copy } from '../locale';

interface Props {
  open: boolean;
  count: number;
  onCancel: () => void;
  onConfirm: () => void;
  copy: Copy;
}

const ActionConfirmationDialog: React.FC<Props> = ({ open, count, onCancel, onConfirm, copy }) => (
  <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
    <DialogTitle>{copy.confirmation.title}</DialogTitle>
    <DialogContent>
      <DialogContentText>{copy.confirmation.body(count)}</DialogContentText>
    </DialogContent>
    <DialogActions>
      <Button onClick={onCancel}>{copy.confirmation.cancel}</Button>
      <Button onClick={onConfirm} variant="contained" color="primary">
        {copy.confirmation.confirm}
      </Button>
    </DialogActions>
  </Dialog>
);

export default ActionConfirmationDialog;
