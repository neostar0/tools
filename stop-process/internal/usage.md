Usage: stop-process <name>

Stop every process whose exact name matches <name>.
Graceful first (WM_CLOSE / SIGTERM), wait 3s, then force (/F / SIGKILL).

Exit codes: 0 = nothing matching is running, 1 = a match survived,
            2 = bad usage
