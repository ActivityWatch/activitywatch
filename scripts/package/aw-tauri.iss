; Inno Setup script for ActivityWatch (Tauri edition)
;
; This is separate from activitywatch-setup.iss (aw-qt) to avoid
; installation collisions. Uses a different AppId, install directory,
; and display name.

#define MyAppName "ActivityWatch (Tauri)"
#define MyAppVersion GetEnv('AW_VERSION')
#define MyAppPublisher "ActivityWatch Contributors"
#define MyAppURL "https://activitywatch.net/"
#define MyAppExeName "aw-tauri.exe"
#define MyAutostartName "aw-tauri"
#define RootDir "..\.."
#define DistDir "..\..\dist"

#pragma verboselevel 9

[Setup]
; IMPORTANT: Different AppId from aw-qt to allow side-by-side installation
AppId={{983D0855-08C8-46BD-AEFB-3924581C6703}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL="https://github.com/ActivityWatch/activitywatch/issues"
AppUpdatesURL="https://github.com/ActivityWatch/activitywatch/releases"
DefaultDirName={autopf}\ActivityWatch-Tauri
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#DistDir}
OutputBaseFilename=activitywatch-setup
SetupIconFile="{#RootDir}\aw-tauri\src-tauri\icons\icon.ico"
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "StartMenuEntry" ; Description: "Start ActivityWatch when Windows starts"; GroupDescription: "Windows Startup"; MinVersion: 4,4;

[Files]
Source: "{#DistDir}\activitywatch\aw-tauri.exe"; DestDir: "{app}\aw-tauri"; Flags: ignoreversion
Source: "{#DistDir}\activitywatch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: StartMenuEntry;

[Registry]
; aw-tauri registers its own login item at runtime (tauri-plugin-autostart), so the
; installer never created these values and would leave them behind. MyAutostartName
; matches the runtime name; the Research Edition build patches it to its own identity.
; ValueType: none creates nothing on install; uninsdeletevalue removes the value on
; uninstall. StartupApproved holds Task Manager's enabled/disabled flag.
; HKCU cleanup covers only the account running the uninstaller, not other users of an
; all-users install. Named-profile login items are also outside this cleanup.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "{#MyAutostartName}"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"; ValueType: none; ValueName: "{#MyAutostartName}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
