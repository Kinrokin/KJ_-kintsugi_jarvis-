"""Generate, never apply, opt-in autostart artifacts. No root/admin escalation."""
from __future__ import annotations
import hashlib,os,sys
from pathlib import Path
from .common import Refused,canonical

def checked_path(value):
    p=Path(value).expanduser().absolute();s=str(p)
    if any(x in s for x in '\r\n\x00"%'):raise Refused('Deployment path contains unsupported quoting/specifier characters')
    return s

def ps_literal(value):return "'"+value.replace("'","''")+"'"

def plans(config_path,home,python_path=None,package=None):
    config=checked_path(config_path);home=checked_path(home);python=checked_path(python_path or sys.executable)
    package=checked_path(package or Path(__file__).resolve().parents[1]);script=checked_path(Path(package)/'scripts/runtime_operator.py')
    name='Kintsugi-'+hashlib.sha256(home.encode()).hexdigest()[:12]
    args='-I "'+script+'" --config "'+config+'" run'
    ps="""# Generated plan; nothing happens without -Apply, -Start or -Remove.
param([switch]$Apply,[switch]$Start,[switch]$Remove)
$ErrorActionPreference='Stop'
$Name=NAME
$Exe=EXE
$Args=ARGS
$Directory=DIRECTORY
$Marker='Kintsugi 3.2 operator-approved current-user runtime; no provider writer'
$Existing=Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
$Owned=$Existing -and $Existing.Description -eq $Marker -and $Existing.Actions.Count -eq 1 -and $Existing.Actions[0].Execute -eq $Exe -and $Existing.Actions[0].Arguments -eq $Args
if($Existing -and -not $Owned){throw 'Existing task has different ownership/content; refusing to touch it.'}
if($Remove){
  if(-not $Owned){throw 'No exact owned task to remove.'}
  Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $Name -Confirm:$true
  return
}
if($Apply){
  if(-not (Test-Path -LiteralPath $Exe)){throw 'Python executable does not exist.'}
  if(-not $Existing){
    $Identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
    $Action=New-ScheduledTaskAction -Execute $Exe -Argument $Args -WorkingDirectory $Directory
    $Trigger=New-ScheduledTaskTrigger -AtLogOn -User $Identity
    $Principal=New-ScheduledTaskPrincipal -UserId $Identity -LogonType Interactive -RunLevel Limited
    $Settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description $Marker | Out-Null
  }
}
if($Start){
  if(-not (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue)){throw 'Apply the reviewed task first.'}
  Start-ScheduledTask -TaskName $Name
}
[PSCustomObject]@{Name=$Name;ApplyRequested=[bool]$Apply;StartRequested=[bool]$Start;ExpectedExecutable=$Exe;ExpectedArguments=$Args;Limitation='Runs as this user when logged on and computer awake. No physical phone or delivery certification.'} | ConvertTo-Json
"""
    for key,val in [('NAME',name),('EXE',python),('ARGS',args),('DIRECTORY',package)]:ps=ps.replace('='+key+'\n','='+ps_literal(val)+'\n')
    def unitarg(s):return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
    unit='\n'.join(['[Unit]','Description=Kintsugi private household runtime (user service)','After=network-online.target','',
        '[Service]','Type=simple','ExecStart='+unitarg(python)+' -I '+unitarg(script)+' --config '+unitarg(config)+' run',
        'WorkingDirectory='+unitarg(package),'Restart=on-failure','RestartSec=30','UMask=0077','NoNewPrivileges=yes','PrivateTmp=yes','',
        '[Install]','WantedBy=default.target',''])
    return {'name':name,'windows_powershell':ps,'systemd_user_unit':unit,'applied':False}
