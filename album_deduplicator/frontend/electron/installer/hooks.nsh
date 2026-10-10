# Override before the per-user macros expand in both installer and uninstaller.
!macro customHeader
  !ifndef INSTALL_MODE_PER_ALL_USERS
    !include "${PROJECT_DIR}\electron\installer\safe-per-user.nsh"
  !endif
!macroend
