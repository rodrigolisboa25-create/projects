param([string]$Uri = '', [string]$ActivationFile = '')
# Clique numa notificação do Estoque Contábil (protocolo estoquecontabil:).
# 1) Avisa o servidor local, que leva a aba já aberta para a página da notificação.
# 2) Traz essa aba do navegador para frente (Chrome/Edge), sem abrir outra.
# 3) Sem aba aberta: abre o sistema; servidor parado: usa o inicializador do atalho.
$ErrorActionPreference = 'Continue'

function Get-QueryValue([string]$Text, [string]$Name) {
  if ($Text -match "[?&]$Name=([^&]*)") { return [Uri]::UnescapeDataString($Matches[1]) }
  return ''
}

$view = Get-QueryValue $Uri 'view'
$id = Get-QueryValue $Uri 'id'
if ($view -notmatch '^[a-z-]{0,30}$') { $view = '' }
if ($id -notmatch '^\d{0,12}$') { $id = '' }

$port = 8765
$token = ''
try {
  $config = Get-Content -LiteralPath $ActivationFile -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($config.port) { $port = [int]$config.port }
  $token = [string]$config.token
} catch {}
$base = "http://127.0.0.1:$port/"

$openTabs = -1
try {
  $body = @{ view = $view; id = $id } | ConvertTo-Json -Compress
  $answer = Invoke-RestMethod -Uri ($base + 'api/notifications/activate') -Method Post -Body $body `
    -ContentType 'application/json' -Headers @{ 'X-Ops-Activation' = $token } -TimeoutSec 5
  $openTabs = [int]$answer.tabs
} catch { $openTabs = -1 }

function Show-SystemTab {
  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
  Add-Type -Namespace OpsContabil -Name Janela -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr handle);
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr handle, int command);
[DllImport("user32.dll")] public static extern bool IsIconic(System.IntPtr handle);
[DllImport("user32.dll")] public static extern bool BringWindowToTop(System.IntPtr handle);
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr handle, System.IntPtr processId);
[DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
[DllImport("user32.dll")] public static extern bool AttachThreadInput(uint attach, uint attachTo, bool doAttach);
public static void Bring(System.IntPtr handle) {
  // O Windows só deixa trazer uma janela para frente quem está ligado à janela em uso:
  // liga-se temporariamente a ela, traz o navegador e se desliga.
  uint current = GetCurrentThreadId();
  uint foreground = GetWindowThreadProcessId(GetForegroundWindow(), System.IntPtr.Zero);
  bool attached = foreground != 0 && foreground != current && AttachThreadInput(current, foreground, true);
  if (IsIconic(handle)) { ShowWindow(handle, 9); }
  BringWindowToTop(handle);
  SetForegroundWindow(handle);
  if (attached) { AttachThreadInput(current, foreground, false); }
}
'@
  $element = [System.Windows.Automation.AutomationElement]
  $browserWindows = $element::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,
    (New-Object System.Windows.Automation.PropertyCondition($element::ClassNameProperty, 'Chrome_WidgetWin_1')))
  foreach ($window in $browserWindows) {
    $tabs = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants,
      (New-Object System.Windows.Automation.PropertyCondition($element::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)))
    foreach ($tab in $tabs) {
      # Título da página: "Estoque Contábil" (curinga evita depender da codificação do acento).
      if ($tab.Current.Name -like '*Estoque Cont*bil*') {
        $handle = [IntPtr]$window.Current.NativeWindowHandle
        [OpsContabil.Janela]::Bring($handle)
        try { $tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select() }
        catch { try { $tab.SetFocus() } catch {} }
        Start-Sleep -Milliseconds 150
        if ([OpsContabil.Janela]::GetForegroundWindow() -ne $handle) { [OpsContabil.Janela]::Bring($handle) }
        return $true
      }
    }
  }
  return $false
}

if ($openTabs -gt 0 -and (Show-SystemTab)) { exit 0 }

if ($openTabs -lt 0) {
  $launcher = Join-Path $env:LOCALAPPDATA 'OpsContabil\ABRIR_ESTOQUE_CONTABIL.ps1'
  if (Test-Path -LiteralPath $launcher) {
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', $launcher)
    exit 0
  }
}

$target = $base + '?origem=notificacao'
if ($view) { $target += '#' + $view }
Start-Process $target
