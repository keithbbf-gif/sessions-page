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

[Files]
Source: "V:\a\ai\COSMOS\builds\sessions-page\dist\sessions_page.exe"; DestDir: "{app}"; DestName: "sessions_page.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\cmSessions"; Filename: "{app}\sessions_page.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\cmSessions"; Filename: "{app}\sessions_page.exe"; WorkingDir: "{app}"
