#define AppVersion "2.5.0"
[Setup]
AppId={{2F24CE85-F936-407A-98C3-E05B2F34B651}
AppName=StreamChrome PRO
AppVersion={#AppVersion}
AppPublisher=OhCato
AppPublisherURL=https://github.com/caiquecato/StreamChromePro
DefaultDirName={localappdata}\Programs\StreamChromePro
DefaultGroupName=StreamChrome PRO
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=StreamChromePro-Setup-2.5.0
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\StreamChromePro.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
[Files]
Source: "..\scratch\dist\StreamChromePro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scratch\dist\StreamChromeBridge.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "chromium-host.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "firefox-host.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\THIRD_PARTY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "yt-dlp\*"; DestDir: "{app}\yt-dlp"; Flags: ignoreversion
[Icons]
Name: "{group}\StreamChrome PRO"; Filename: "{app}\StreamChromePro.exe"
Name: "{autodesktop}\StreamChrome PRO"; Filename: "{app}\StreamChromePro.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Registry]
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\com.caiquecato.streamchromepro"; ValueType: string; ValueData: "{app}\chromium-host.json"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\com.caiquecato.streamchromepro"; ValueType: string; ValueData: "{app}\chromium-host.json"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Mozilla\NativeMessagingHosts\com.caiquecato.streamchromepro"; ValueType: string; ValueData: "{app}\firefox-host.json"; Flags: uninsdeletekey
[Run]
Filename: "{app}\StreamChromePro.exe"; Description: "Open StreamChrome PRO"; Flags: nowait postinstall skipifsilent
[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var Loaded: AnsiString; Text, ManifestPath, BridgePath: String; I: Integer;
begin
  if CurStep = ssPostInstall then begin
    BridgePath := ExpandConstant('{app}\StreamChromeBridge.exe');
    StringChangeEx(BridgePath, '\', '\\', True);
    for I := 0 to 1 do begin
      if I = 0 then ManifestPath := ExpandConstant('{app}\chromium-host.json')
      else ManifestPath := ExpandConstant('{app}\firefox-host.json');
      if LoadStringFromFile(ManifestPath, Loaded) then begin
        Text := String(Loaded);
        StringChangeEx(Text, 'StreamChromeBridge.exe', BridgePath, True);
        SaveStringToFile(ManifestPath, AnsiString(Text), False);
      end;
    end;
  end;
end;
