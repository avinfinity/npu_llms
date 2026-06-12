#define AppName "NPU"
#define AppVersion "0.1.1"
#define AppPublisher "NPU Contributors"

[Setup]
AppId={{0A09B880-6EB8-4557-A46A-225060873781}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\NPU
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=npu-setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
ChangesEnvironment=yes

[Files]
Source: "..\dist\npu\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NPU"; Filename: "{app}\npu.exe"; Parameters: "start"
Name: "{group}\NPU Chat"; Filename: "http://127.0.0.1:11435/chat"

[Run]
Filename: "{app}\npu.exe"; Parameters: "install-startup"; Flags: runhidden
Filename: "{app}\npu.exe"; Parameters: "start"; Flags: nowait runhidden postinstall

[UninstallRun]
Filename: "{app}\npu.exe"; Parameters: "stop"; Flags: runhidden
Filename: "{app}\npu.exe"; Parameters: "uninstall-startup"; Flags: runhidden

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsPathEntry(ExpandConstant('{app}')); Flags: preservestringtype

[Code]
const
  IntelNpuDriverUrl = 'https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html';

function PathEntryExists(PathValue: String; Entry: String): Boolean;
begin
  Result := Pos(';' + Uppercase(Entry) + ';', ';' + Uppercase(PathValue) + ';') > 0;
end;

function NeedsPathEntry(Entry: String): Boolean;
var
  PathValue: String;
begin
  if not RegQueryStringValue(
    HKLM,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path',
    PathValue
  ) then
    PathValue := '';

  Result := not PathEntryExists(PathValue, Entry);
end;

procedure RemovePathEntry(Entry: String);
var
  PathValue: String;
  NewPathValue: String;
  Segment: String;
  SeparatorPos: Integer;
begin
  if not RegQueryStringValue(
    HKLM,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path',
    PathValue
  ) then
    exit;

  NewPathValue := '';
  PathValue := PathValue + ';';

  while Length(PathValue) > 0 do
  begin
    SeparatorPos := Pos(';', PathValue);
    Segment := Copy(PathValue, 1, SeparatorPos - 1);
    Delete(PathValue, 1, SeparatorPos);

    if (Segment <> '') and (Uppercase(Segment) <> Uppercase(Entry)) then
    begin
      if NewPathValue <> '' then
        NewPathValue := NewPathValue + ';';
      NewPathValue := NewPathValue + Segment;
    end;
  end;

  RegWriteExpandStringValue(
    HKLM,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path',
    NewPathValue
  );
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemovePathEntry(ExpandConstant('{app}'));
end;

function IsIntelNpuDriverPresent(): Boolean;
var
  ResultCode: Integer;
  PowerShellArgs: String;
begin
  PowerShellArgs :=
    '-NoProfile -ExecutionPolicy Bypass -Command "' +
    '$devices = Get-CimInstance Win32_PnPEntity | Where-Object { ' +
    '(($_.Name -match ''Intel.*(NPU|AI Boost|Neural)'') -or ($_.Name -match ''NPU'')) ' +
    '-and ($_.ConfigManagerErrorCode -eq 0) }; ' +
    'if ($devices) { exit 0 } else { exit 1 }"';

  Result :=
    Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      PowerShellArgs,
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) and (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
var
  Choice: Integer;
begin
  Result := True;

  if IsIntelNpuDriverPresent() then
    exit;

  Choice :=
    MsgBox(
      'NPU requires the Intel NPU Driver for Windows before setup can continue.' + #13#10 + #13#10 +
      'Click Yes to open Intel''s driver download page. Install the driver, restart Windows if the driver installer asks you to, then run this setup again.' + #13#10 + #13#10 +
      IntelNpuDriverUrl,
      mbConfirmation,
      MB_YESNO
    );

  if Choice = IDYES then
    ShellExec('open', IntelNpuDriverUrl, '', '', SW_SHOWNORMAL, ewNoWait, Choice);

  Result := False;
end;
