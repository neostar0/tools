Usage: serve-video-rtsp <video-file> [-n NAME] [-p PORT]
       serve-video-rtsp --stop
       check-mediamtx [--force]

Serve <video-file> over RTSP with mediamtx: ffmpeg loops the file forever and
publishes it to a local mediamtx server, then the rtsp:// URL is printed.

Options:
  -n, --name NAME   RTSP path name (default: stream)
  -p, --port PORT   RTSP listen port (default: 8554)
  --stop            stop the server this tool started
  -h, --help        print this help and exit

check-mediamtx installs the pinned mediamtx release into internal/bin when the
binary is missing; --force downloads and replaces it again.

Exit codes: 0 = success, already installed or already stopped; 1 = a missing
            dependency, a busy port, a missing file or a stream that died;
            2 = bad usage
