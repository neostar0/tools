// P/Invoke declarations, Win32 constants and structs used to inspect
// and move top-level windows. No policy lives here: WindowStateController
// decides what to call and in what order.
//
// Keep this file ASCII-only. PowerShell 5.1 reads BOM-less files as
// ANSI, and a mangled comment is not worth an encoding bug.
namespace WindowControl
{
    using System;
    using System.Collections.Generic;
    using System.Runtime.InteropServices;

    public static class Native
    {
        private const int GWL_STYLE = -16;

        private const int SW_RESTORE  = 9;
        private const int SW_MAXIMIZE = 3;

        private const uint SWP_NOSIZE       = 0x0001;
        private const uint SWP_NOMOVE       = 0x0002;
        private const uint SWP_NOZORDER     = 0x0004;
        private const uint SWP_NOACTIVATE   = 0x0010;
        private const uint SWP_FRAMECHANGED = 0x0020;

        private const uint MONITOR_DEFAULTTONEAREST = 2;

        private static readonly List<long> Collected =
            new List<long>();

        private static readonly EnumWindowsProc Collector = Collect;

        public delegate bool EnumWindowsProc(
            IntPtr hWnd, IntPtr lParam);

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MONITORINFO
        {
            public int cbSize;
            public RECT rcMonitor;
            public RECT rcWork;
            public uint dwFlags;
        }

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool EnumWindows(
            EnumWindowsProc callback, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(
            IntPtr hWnd, out uint processId);

        [DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern int GetWindowTextLength(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern bool IsZoomed(IntPtr hWnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool GetWindowRect(
            IntPtr hWnd, out RECT rect);

        [DllImport("user32.dll")]
        private static extern IntPtr MonitorFromWindow(
            IntPtr hWnd, uint flags);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool GetMonitorInfo(
            IntPtr hMonitor, ref MONITORINFO info);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(
            IntPtr hWnd, int command);

        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW",
            ExactSpelling = true)]
        private static extern IntPtr GetWindowLongPtr64(
            IntPtr hWnd, int index);

        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW",
            ExactSpelling = true, SetLastError = true)]
        private static extern IntPtr SetWindowLongPtr64(
            IntPtr hWnd, int index, IntPtr value);

        [DllImport("user32.dll", EntryPoint = "GetWindowLongW",
            ExactSpelling = true)]
        private static extern int GetWindowLong32(
            IntPtr hWnd, int index);

        [DllImport("user32.dll", EntryPoint = "SetWindowLongW",
            ExactSpelling = true, SetLastError = true)]
        private static extern int SetWindowLong32(
            IntPtr hWnd, int index, int value);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(
            IntPtr hWnd, IntPtr insertAfter,
            int x, int y, int cx, int cy, uint flags);

        [DllImport("user32.dll", EntryPoint = "SetThreadDpiAwarenessContext")]
        private static extern IntPtr SetThreadDpiAwarenessContext(
            IntPtr dpiContext);

        public static IntPtr EnterPerMonitorDpi()
        {
            // DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4.
            // Fall back to the current thread context on older Windows.
            try
            {
                return SetThreadDpiAwarenessContext(new IntPtr(-4));
            }
            catch (EntryPointNotFoundException)
            {
                Console.Error.WriteLine(
                    "[WARN] SetThreadDpiAwarenessContext is not " +
                    "available; continuing with the current DPI " +
                    "context.");
                return IntPtr.Zero;
            }
        }

        public static void RestoreDpiContext(IntPtr previous)
        {
            if (previous == IntPtr.Zero)
                return;

            try
            {
                SetThreadDpiAwarenessContext(previous);
            }
            catch (EntryPointNotFoundException)
            {
                Console.Error.WriteLine(
                    "[WARN] Could not restore the previous DPI " +
                    "context: SetThreadDpiAwarenessContext is not " +
                    "available.");
            }
        }

        private static bool Collect(IntPtr hWnd, IntPtr lParam)
        {
            Collected.Add(hWnd.ToInt64());
            return true;
        }

        public static long[] TopLevelWindows()
        {
            Collected.Clear();

            if (!EnumWindows(Collector, IntPtr.Zero))
                throw new InvalidOperationException(
                    "EnumWindows failed: " +
                    Marshal.GetLastWin32Error());

            return Collected.ToArray();
        }

        public static long ProcessId(long hWnd)
        {
            uint processId;
            GetWindowThreadProcessId(new IntPtr(hWnd), out processId);
            return processId;
        }

        public static bool Visible(long hWnd)
        {
            return IsWindowVisible(new IntPtr(hWnd));
        }

        public static int TitleLength(long hWnd)
        {
            return GetWindowTextLength(new IntPtr(hWnd));
        }

        public static bool Zoomed(long hWnd)
        {
            return IsZoomed(new IntPtr(hWnd));
        }

        public static long Style(long hWnd)
        {
            IntPtr h = new IntPtr(hWnd);

            if (IntPtr.Size == 8)
                return GetWindowLongPtr64(h, GWL_STYLE).ToInt64();

            return GetWindowLong32(h, GWL_STYLE);
        }

        public static bool TrySetStyle(
            long hWnd, long style, out int errorCode)
        {
            IntPtr h = new IntPtr(hWnd);
            IntPtr previous;

            if (IntPtr.Size == 8)
            {
                previous = SetWindowLongPtr64(
                    h, GWL_STYLE, new IntPtr(style));
            }
            else
            {
                int oldValue = SetWindowLong32(
                    h, GWL_STYLE, unchecked((int)style));

                previous = new IntPtr(oldValue);
            }

            errorCode = Marshal.GetLastWin32Error();

            // A zero previous value is valid if the last error is zero.
            return previous != IntPtr.Zero || errorCode == 0;
        }

        public static void ApplyFrameChanged(long hWnd)
        {
            if (!SetWindowPos(
                new IntPtr(hWnd), IntPtr.Zero,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE |
                SWP_NOZORDER | SWP_NOACTIVATE |
                SWP_FRAMECHANGED))
            {
                throw new InvalidOperationException(
                    "Frame change failed: " +
                    Marshal.GetLastWin32Error());
            }
        }

        public static void Show(long hWnd, bool maximize)
        {
            // The return value is the previous visibility state,
            // not a success indicator. Verify the final state instead.
            ShowWindow(
                new IntPtr(hWnd),
                maximize ? SW_MAXIMIZE : SW_RESTORE);
        }

        public static RECT MonitorBounds(long hWnd)
        {
            IntPtr monitor = MonitorFromWindow(
                new IntPtr(hWnd), MONITOR_DEFAULTTONEAREST);

            if (monitor == IntPtr.Zero)
                throw new InvalidOperationException(
                    "MonitorFromWindow failed.");

            MONITORINFO info = new MONITORINFO();
            info.cbSize = Marshal.SizeOf(typeof(MONITORINFO));

            if (!GetMonitorInfo(monitor, ref info))
                throw new InvalidOperationException(
                    "GetMonitorInfo failed: " +
                    Marshal.GetLastWin32Error());

            // rcMonitor is the complete monitor rectangle,
            // including the taskbar area.
            return info.rcMonitor;
        }

        public static void SetFullBounds(long hWnd, RECT bounds)
        {
            int width = bounds.Right - bounds.Left;
            int height = bounds.Bottom - bounds.Top;

            if (width <= 0 || height <= 0)
                throw new InvalidOperationException(
                    "Invalid monitor dimensions.");

            if (!SetWindowPos(
                new IntPtr(hWnd), IntPtr.Zero,
                bounds.Left, bounds.Top, width, height,
                SWP_NOZORDER | SWP_NOACTIVATE))
            {
                throw new InvalidOperationException(
                    "SetWindowPos fullscreen failed: " +
                    Marshal.GetLastWin32Error());
            }
        }

        public static RECT WindowBounds(long hWnd)
        {
            RECT rect;

            if (!GetWindowRect(new IntPtr(hWnd), out rect))
                throw new InvalidOperationException(
                    "GetWindowRect failed: " +
                    Marshal.GetLastWin32Error());

            return rect;
        }
    }
}
