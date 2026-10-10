# Backport electron-builder a356198 (#9769). Remove when the bundled template
# uses lstrcpynW instead of reading NSIS_MAX_STRLEN characters from shell memory.
!macroundef setInstallModePerUser
!macro setInstallModePerUser
  StrCpy $installMode CurrentUser
  SetShellVarContext current
  ReadRegStr $perUserInstallationFolder HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
  ${if} $perUserInstallationFolder != ""
    StrCpy $INSTDIR $perUserInstallationFolder
  ${else}
    StrCpy $0 "$LocalAppData\Programs"
    Push $1
    Push $2
    StrCpy $2 0
    System::Call 'SHELL32::SHGetKnownFolderPath(g "${FOLDERID_UserProgramFiles}", i ${KF_FLAG_CREATE}, p 0, *p .r2)i.r1'
    ${If} $1 == 0
      System::Call 'KERNEL32::lstrcpynW(w .r0, p r2, i ${NSIS_MAX_STRLEN})p'
    ${endif}
    ${If} $2 != 0
      System::Call 'OLE32::CoTaskMemFree(p r2)'
    ${endif}
    Pop $2
    Pop $1
    StrCpy $INSTDIR "$0\${APP_FILENAME}"
  ${endif}
  !insertmacro GetDParameter $R0
  ${If} $R0 != ""
    StrCpy $INSTDIR $R0
  ${endif}
!macroend
