// Generic window-state logic built on the Native P/Invoke surface.
// This class is application-agnostic: the caller supplies the process
// name whose top-level windows should be resized, and the state each
// window must reach. No target is hardcoded here, not even in a
// comment.
//
// Keep this file ASCII-only. PowerShell 5.1 reads BOM-less files as
// ANSI, and a mangled comment is not worth an encoding bug.
namespace WindowControl
{
    using System;
    using System.Collections.Generic;
    using System.Diagnostics;

    public enum WindowState
    {
        // Standard frame kept; IsZoomed true / false / frame cleared.
        Max,
        Restore,
        Full
    }

    public static class WindowStateController
    {
        // WS_CAPTION and WS_THICKFRAME. These are the only style bits
        // ever written; every other bit survives read-modify-write.
        public const long CaptionMask   = 0x00C00000L;
        public const long ThickFrameMask = 0x00040000L;
        public const long FrameMask     = CaptionMask | ThickFrameMask;

        // Top-level, visible, non-empty-title windows owned by a
        // process whose image name matches processName exactly.
        public static long[] FindTopLevelWindows(string processName)
        {
            if (string.IsNullOrEmpty(processName))
                throw new ArgumentException(
                    "processName is required.", "processName");

            var pids = new HashSet<int>();

            foreach (Process process in
                Process.GetProcessesByName(processName))
            {
                try
                {
                    pids.Add(process.Id);
                }
                finally
                {
                    process.Dispose();
                }
            }

            var found = new List<long>();

            foreach (long hWnd in Native.TopLevelWindows())
            {
                if (!Native.Visible(hWnd))
                    continue;

                if (Native.TitleLength(hWnd) == 0)
                    continue;

                if (pids.Contains((int)Native.ProcessId(hWnd)))
                    found.Add(hWnd);
            }

            return found.ToArray();
        }

        public static void ApplyState(long hWnd, WindowState state)
        {
            bool wantFrame = state != WindowState.Full;
            bool wantZoom  = state != WindowState.Restore;

            long style = Native.Style(hWnd);

            bool hasCaption    = (style & CaptionMask) == CaptionMask;
            bool hasThickFrame = (style & ThickFrameMask) != 0;

            bool frameMatches = wantFrame
                ? hasCaption && hasThickFrame
                : (style & CaptionMask) == 0 && !hasThickFrame;

            bool frameChanged = false;

            if (!frameMatches)
            {
                long newStyle = wantFrame
                    ? style | FrameMask
                    : style & ~FrameMask;

                int apiError;

                if (!Native.TrySetStyle(hWnd, newStyle, out apiError))
                    throw new InvalidOperationException(
                        "SetWindowLong failed (Win32 error " +
                        apiError + ").");

                // Rebuild the non-client area without moving or
                // activating the window.
                Native.ApplyFrameChanged(hWnd);
                frameChanged = true;
            }

            // The frame always goes first: SW_MAXIMIZE measures the
            // window that has the frame style it is about to use.
            // For Full the show state below is not just cosmetic - it
            // is what keeps the window's normal rectangle alive; see
            // ApplyBorderlessFullscreen.
            if (state == WindowState.Full)
                ApplyBorderlessFullscreen(hWnd);
            else
                ApplyShowState(hWnd, wantZoom, frameChanged);

            Verify(hWnd, state);
        }

        private static void ApplyShowState(
            long hWnd, bool wantZoom, bool frameChanged)
        {
            // A frame change invalidates the cached maximize rect (it
            // is computed from the frame style), so ShowWindow runs
            // again even when IsZoomed already agrees.
            if (frameChanged || Native.Zoomed(hWnd) != wantZoom)
                Native.Show(hWnd, wantZoom);
        }

        // REGRESSION ("full, then restore does not go back", Oct 2026):
        // this order is the whole fix. See NormalRectangleContract in
        // internal/test_window_state.py for the pinned invariant.
        //
        // Maximize BEFORE resizing. Resizing a window that is in its
        // normal state overwrites the window's normal rectangle
        // (WINDOWPLACEMENT.rcNormalPosition), and that rectangle is
        // what a later "restore" hands back - overwriting it is
        // exactly the reported bug, both for full -> restore and for
        // max -> full -> restore (the pre-max size must come back).
        // While the window is zoomed the same SetWindowPos replaces
        // only the maximized rectangle, so the pre-full (and pre-max)
        // size survives inside the window itself and nothing has to be
        // remembered between runs.
        private static void ApplyBorderlessFullscreen(long hWnd)
        {
            Native.Show(hWnd, true);

            // Always refresh frame calculations before positioning.
            Native.ApplyFrameChanged(hWnd);

            Native.RECT monitor = Native.MonitorBounds(hWnd);

            // Position and size explicitly. Do not maximize afterward:
            // Windows could recalculate the rectangle using its
            // standard maximize rules.
            Native.SetFullBounds(hWnd, monitor);
        }

        private static void Verify(long hWnd, WindowState state)
        {
            // ShowWindow's return value is "was previously visible"
            // and SetWindowLong's is the previous style; neither is a
            // success signal. Re-reading the state is the only one.
            long style = Native.Style(hWnd);

            bool hasCaption    = (style & CaptionMask) == CaptionMask;
            bool hasThickFrame = (style & ThickFrameMask) != 0;

            if (state == WindowState.Full)
            {
                if ((style & CaptionMask) != 0 || hasThickFrame)
                    throw new InvalidOperationException(
                        "Fullscreen frame styles are not fully cleared.");

                // REGRESSION: a borderless window that is not
                // maximized has already lost its normal rectangle -
                // nothing would be left for "restore" to hand back.
                // Reporting [OK] here would hide that, so it fails.
                if (!Native.Zoomed(hWnd))
                    throw new InvalidOperationException(
                        "Fullscreen window is not maximized; a later " +
                        "restore would not return to the old size.");

                VerifyFullBounds(hWnd);
                return;
            }

            if (!hasCaption || !hasThickFrame)
                throw new InvalidOperationException(
                    "Standard frame styles were not applied.");

            bool wantZoom = state != WindowState.Restore;

            if (Native.Zoomed(hWnd) != wantZoom)
                throw new InvalidOperationException(
                    "Window did not reach the requested show state.");
        }

        private static void VerifyFullBounds(long hWnd)
        {
            // Validate the actual outer rectangle, not the request.
            Native.RECT actual  = Native.WindowBounds(hWnd);
            Native.RECT monitor = Native.MonitorBounds(hWnd);

            if (actual.Left   != monitor.Left ||
                actual.Top    != monitor.Top ||
                actual.Right  != monitor.Right ||
                actual.Bottom != monitor.Bottom)
            {
                throw new InvalidOperationException(
                    "Fullscreen bounds mismatch. Window=" +
                    actual.Left + "," + actual.Top + "," +
                    actual.Right + "," + actual.Bottom +
                    "; Monitor=" +
                    monitor.Left + "," + monitor.Top + "," +
                    monitor.Right + "," + monitor.Bottom);
            }
        }
    }
}
