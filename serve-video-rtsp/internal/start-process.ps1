# Start mediamtx or the ffmpeg publisher detached from this console and print
# the new process id. Everything the child needs arrives through environment
# variables, so no path and no stream name is ever interpolated into a
# command line: a file called "a & b.mp4" must not be able to inject syntax.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('mtx', 'ff')]
    [string] $Kind
)

function Join-CommandLine {
    param([string[]] $Parts)

    # A Windows path cannot contain a double quote, so quoting the elements
    # that carry whitespace is enough to survive cmd's argument splitting.
    ($Parts | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }) -join ' '
}

switch ($Kind) {
    'mtx' {
        $exe     = $env:MTX_EXE
        $argLine = Join-CommandLine @($env:MTX_CFG)
        $stdout  = $env:MTX_OUT
        $stderr  = $env:MTX_ERR
    }
    'ff' {
        $exe     = $env:FF_EXE
        $parts   = @('-nostdin', '-hide_banner', '-loglevel', 'warning',
                     '-re', '-stream_loop', '-1', '-i', $env:VID_FILE)
        $parts  += @($env:FF_ARGS -split ' ')
        $parts  += @('-f', 'rtsp', '-rtsp_transport', 'tcp', $env:RTSP_URL)
        $argLine = Join-CommandLine $parts
        $stdout  = $env:FF_OUT
        $stderr  = $env:FF_ERR
    }
}

try {
    # The children may drop files next to their working directory (mediamtx
    # generates auto.key/auto.crt), so pin it to the runtime folder instead of
    # whoever launched us.
    $workDir = Split-Path -Parent $stdout
    $process = Start-Process -FilePath $exe -ArgumentList $argLine `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -WorkingDirectory $workDir `
        -PassThru -WindowStyle Hidden -ErrorAction Stop
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}

Write-Output $process.Id
exit 0
