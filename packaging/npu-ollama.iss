#define AppName "NPU Ollama"
#define AppVersion "0.1.0"
#define AppPublisher "NPU Ollama Contributors"

[Setup]
AppId={{0A09B880-6EB8-4557-A46A-225060873781}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\NPU Ollama
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=npu-ollama-setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\dist\npu-ollama\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NPU Ollama"; Filename: "{app}\npu-ollama.exe"; Parameters: "start"
Name: "{group}\NPU Ollama Chat"; Filename: "http://127.0.0.1:11435"

[Run]
Filename: "{app}\npu-ollama.exe"; Parameters: "install-startup"; Flags: runhidden
Filename: "{app}\npu-ollama.exe"; Parameters: "start"; Flags: nowait runhidden postinstall

[UninstallRun]
Filename: "{app}\npu-ollama.exe"; Parameters: "uninstall-startup"; Flags: runhidden

[Code]
const
  IntelNpuDriverUrl = 'https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html';

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
      'NPU Ollama requires the Intel NPU Driver for Windows before setup can continue.' + #13#10 + #13#10 +
      'Click Yes to open Intel''s driver download page. Install the driver, restart Windows if the driver installer asks you to, then run this setup again.' + #13#10 + #13#10 +
      IntelNpuDriverUrl,
      mbConfirmation,
      MB_YESNO
    );

  if Choice = IDYES then
    ShellExec('open', IntelNpuDriverUrl, '', '', SW_SHOWNORMAL, ewNoWait, Choice);

  Result := False;
end;
