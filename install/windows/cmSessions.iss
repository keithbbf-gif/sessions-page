; cmSessions 1.0.0 per-user installer for 64-bit Windows.
; Fixed AppId so a reinstall upgrades in place:
; {A7C3E1B4-6D20-4F8A-9C55-1B0E8F2A6D11}
; Do not start sessions_page.exe when setup finishes.

[Setup]
AppId={{A7C3E1B4-6D20-4F8A-9C55-1B0E8F2A6D11}
AppName=cmSessions
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\cmSessions
DefaultGroupName=cmSessions
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
; 64-bit only (x64). x64compatible is the Inno 6.3+ name for systems
; that can run x64 binaries. The pre-6.3 identifier x64 no longer compiles.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputBaseFilename=cmSessions-Setup
OutputDir=V:\a\ai\COSMOS\builds\sessions-page\install\windows\out
UninstallDisplayName=cmSessions
; An upgrade may close a running copy to replace the exe. Do not relaunch it.
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "install_cmcode"; Description: "Install cmCode AI harness dependency (recommended for AI access)"; GroupDescription: "Dependencies:"; Flags: checkedonce

[Files]
Source: "V:\a\ai\COSMOS\builds\sessions-page\dist\sessions_page.exe"; DestDir: "{app}"; DestName: "sessions_page.exe"; Flags: ignoreversion
Source: "V:\a\ai\COSMOS\builds\sessions-page\install\windows\install_cmcode_dep.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\cmSessions"; Filename: "{app}\sessions_page.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\cmSessions"; Filename: "{app}\sessions_page.exe"; WorkingDir: "{app}"

; sessions_page.exe is not launched. The cmCode step is a separate binary install.
[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install_cmcode_dep.ps1"""; Tasks: install_cmcode; Check: not IsCmCodeInstalled; Flags: runhidden waituntilterminated

[Code]
function IsCmCodeInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result :=
    FileExists(ExpandConstant('{localappdata}\Programs\cmCode\cmcode.cmd')) or
    FileExists(ExpandConstant('{localappdata}\Programs\cmCode\pyproject.toml')) or
    FileExists(ExpandConstant('{localappdata}\Programs\COSMOS\cmCode\cmcode.cmd')) or
    FileExists(ExpandConstant('{localappdata}\Programs\COSMOS\cmCode\pyproject.toml'));
  if Result then
    Exit;
  if Exec(ExpandConstant('{sys}\where.exe'), 'cmcode', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;
  if Exec(ExpandConstant('{sys}\where.exe'), 'cosmos-code', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
    Result := True;
end;
