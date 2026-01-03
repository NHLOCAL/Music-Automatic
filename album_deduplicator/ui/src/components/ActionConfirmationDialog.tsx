import { Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Button } from '@mui/material';
import React from 'react';

interface Props {
  open: boolean;
  count: number;
  onCancel: () => void;
  onConfirm: () => void;
}

const ActionConfirmationDialog: React.FC<Props> = ({ open, count, onCancel, onConfirm }) => (
  <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
    <DialogTitle>Execute merge action</DialogTitle>
    <DialogContent>
      <DialogContentText>
        You are about to merge {count} folder pairs. The action will use the backend ActionHandler and may move or update files.
        Continue?
      </DialogContentText>
    </DialogContent>
    <DialogActions>
      <Button onClick={onCancel}>Cancel</Button>
      <Button onClick={onConfirm} variant="contained" color="primary">
        Confirm
      </Button>
    </DialogActions>
  </Dialog>
);

export default ActionConfirmationDialog;
