# Set the window state of every top-level window of a running process.
# The process name is an argument; nothing about any application is
# assumed here.

param(
    [Parameter(Position = 0)]
    [string] $ProcessName,

    [Parameter(Position = 1)]
    [string] $State,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Extra
)

function Show-Usage {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'usage.md')
}

function Write-Failure {
    param(
        [string] $Headline,
        [System.Management.Automation.ErrorRecord] $Record
    )

    # One grep-able [FAIL] line first, then the whole exception:
    # type, message, .NET stack, inner exceptions and the script
    # position that raised it - never the bare message.
    [Console]::Error.WriteLine($Headline)

    $detail = $Record.Exception.ToString()

    if ($Record.InvocationInfo) {
        $detail += [Environment]::NewLine +
            $Record.InvocationInfo.PositionMessage
    }

    foreach ($line in ($detail -split '\r?\n')) {
        if ($line.Trim().Length -gt 0) {
            [Console]::Error.WriteLine('    ' + $line.TrimEnd())
        }
    }
}

if ($Extra.Count -gt 0 -or
    [string]::IsNullOrEmpty($ProcessName) -or
    $State -cnotin @('max', 'restore', 'full')) {
    Show-Usage
    exit 2
}

if ($env:OS -ne 'Windows_NT') {
    [Console]::Error.WriteLine('[FAIL] set-window-state is Windows only.')
    exit 1
}

$reported = @{
    'max'     = 'maximized'
    'restore' = 'restored'
    'full'    = 'borderless fullscreen'
}

# Use unique type names to reduce Add-Type collisions when testing
# repeatedly in the same PowerShell session.
$typeLoaded = $false
$addTypeErrors = @()
$previousDpiContext = [IntPtr]::Zero
$failed = 0

try {
    # One compilation unit, two sources: WindowStateController calls Native
    # directly, so both files must be compiled together. Each file
    # keeps its own "namespace" block on purpose - using directives
    # inside a namespace stay valid when the two are concatenated.
    $source = (
        Get-Content -LiteralPath (
            Join-Path $PSScriptRoot 'Native.cs') -Raw -ErrorAction Stop
    ) + "`n" + (
        Get-Content -LiteralPath (
            Join-Path $PSScriptRoot 'WindowStateController.cs') -Raw -ErrorAction Stop
    )

    Add-Type -ErrorVariable addTypeErrors -TypeDefinition $source

    # A compile failure must stop here with the real compiler errors,
    # instead of letting the first [WindowControl.*] call die with a
    # misleading "Unable to find type" and the finally block throw again.
    if (-not ('WindowControl.WindowStateController' -as [type])) {
        foreach ($addTypeError in $addTypeErrors) {
            Write-Failure (
                '[FAIL] Add-Type: {0}' -f
                    $addTypeError.Exception.Message) $addTypeError
        }

        if ($addTypeErrors.Count -eq 0) {
            [Console]::Error.WriteLine(
                '[FAIL] Add-Type produced no error but the helper type is missing.')
        }

        exit 1
    }

    # The type already present in this session is the tolerated
    # collision case; still report what Add-Type complained about.
    foreach ($addTypeError in $addTypeErrors) {
        [Console]::Error.WriteLine(
            ('[WARN] Add-Type: {0}' -f $addTypeError.Exception.Message))
    }

    $typeLoaded = $true

    $windowState = switch ($State) {
        'max'     { [WindowControl.WindowState]::Max }
        'restore' { [WindowControl.WindowState]::Restore }
        'full'    { [WindowControl.WindowState]::Full }
    }

    # Coordinates returned by monitor APIs should be interpreted
    # consistently with physical-pixel positioning where supported.
    $previousDpiContext = [WindowControl.Native]::EnterPerMonitorDpi()

    $targets = @(
        [WindowControl.WindowStateController]::FindTopLevelWindows($ProcessName)
    )

    if ($targets.Count -eq 0) {
        [Console]::Error.WriteLine(
            ('[FAIL] no window found for process {0}.' -f $ProcessName))
        exit 1
    }

    foreach ($h in $targets) {
        try {
            [WindowControl.WindowStateController]::ApplyState($h, $windowState)
        }
        catch {
            $failed++

            Write-Failure (
                '[FAIL] HWND {0}: {1}' -f
                    $h, $_.Exception.Message) $_
        }
    }

    if ($failed -gt 0) {
        [Console]::Error.WriteLine(
            ('[FAIL] {0}: {1} of {2} window(s) did not reach the requested state.' -f
                $State, $failed, $targets.Count))
        exit 1
    }

    Write-Output (
        '[OK] {0}: {1} window(s) {2}.' -f
            $State, $targets.Count, $reported[$State]
    )
}
catch {
    Write-Failure (
        '[FAIL] {0}' -f $_.Exception.Message) $_
    exit 1
}
finally {
    if ($typeLoaded) {
        [WindowControl.Native]::RestoreDpiContext($previousDpiContext)
    }
}

exit 0
