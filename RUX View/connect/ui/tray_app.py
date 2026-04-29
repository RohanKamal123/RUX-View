"""Windows System Tray Application — pystray + tkinter settings UI.

Provides a system tray icon with status indicators (green=running,
red=stopped, yellow=error) and a right-click menu for controlling
the Vision OS Connect client agent.

The Settings window (tkinter) allows the user to configure API key,
camera name, RTSP URL, camera mode, audio toggle, and auto-start.
"""

import asyncio
import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

import pystray
from PIL import Image, ImageDraw

from connect.config import AppConfig, load_config, save_config

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
ICON_SIZE = 64
WINDOW_TITLE = "Vision OS Connect Settings"
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 420
PADDING = 10
LABEL_WIDTH = 14

# Camera mode options for the dropdown
CAMERA_MODES = ["indoor", "outdoor", "parking", "mixed", "shop"]


class TrayApp:
    """Windows system tray application for Vision OS Connect.

    Displays a status icon in the system tray with a right-click
    menu to open settings, start/stop the client, or exit.

    Usage:
        app = VisionOSConnect(config)
        tray = TrayApp(app)
        tray.run()  # blocking — runs the tray event loop
    """

    def __init__(self, app) -> None:
        """Initialise the tray application.

        Args:
            app: A ``VisionOSConnect`` instance to control.
        """
        self._app = app
        self._icon: Optional[pystray.Icon] = None
        self._running = False

    # ── Public API ───────────────────────────────────────────────────────────

    def run(self) -> None:
        """Run the tray application (blocking).

        Creates the system tray icon and enters the pystray event
        loop.  This call blocks until ``stop()`` is called or the
        user selects Exit from the menu.
        """
        self._running = True
        icon_image = self._create_icon(self._app.status)

        self._icon = pystray.Icon(
            "visionos_connect",
            icon_image,
            "Vision OS Connect",
            menu=self._build_menu(),
        )

        logger.info("Tray application started")
        self._icon.run()

    def stop(self) -> None:
        """Stop the tray application and remove the icon."""
        self._running = False
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
            logger.info("Tray application stopped")

    # ── Internal: Icon Creation ──────────────────────────────────────────────

    def _create_icon(self, status: str) -> Image:
        """Create a tray icon image based on the current status.

        Colours:
        - ``running``: Green circle
        - ``stopped``: Red circle
        - ``error``:   Yellow circle

        Args:
            status: One of ``"running"``, ``"stopped"``, or ``"error"``.

        Returns:
            A PIL ``Image`` suitable for use as a tray icon.
        """
        colour_map = {
            "running": (0, 180, 0),    # green
            "stopped": (180, 0, 0),    # red
            "error":   (200, 180, 0),  # yellow
        }
        fill = colour_map.get(status, (128, 128, 128))  # grey fallback

        image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw a filled circle with a thin border
        draw.ellipse(
            [4, 4, ICON_SIZE - 4, ICON_SIZE - 4],
            fill=fill + (255,),
            outline=(255, 255, 255, 200),
            width=2,
        )

        return image

    # ── Internal: Menu Building ──────────────────────────────────────────────

    def _build_menu(self):
        """Build the right-click context menu.

        Menu items:
        - Open Settings: Opens the tkinter settings window.
        - Start / Stop: Toggles the client agent on/off.
        - Exit: Stops the tray app and exits.

        Returns:
            A ``pystray.Menu`` instance.
        """
        return pystray.Menu(
            pystray.MenuItem(
                "Open Settings",
                self._on_open_settings,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start" if self._app.status == "stopped" else "Stop",
                self._on_toggle_start_stop,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_exit),
        )

    # ── Internal: Menu Actions ───────────────────────────────────────────────

    def _on_open_settings(self) -> None:
        """Open the settings window in a separate thread.

        Since tkinter must run on the main thread on Windows, we
        launch the settings window in a new thread with its own
        event loop.
        """
        settings_thread = threading.Thread(
            target=self._run_settings_window,
            daemon=True,
        )
        settings_thread.start()

    def _run_settings_window(self) -> None:
        """Run the tkinter settings window (blocking, in a thread)."""
        window = SettingsWindow(self._app.config)
        window.show()

        # After the window closes, reload config and update the icon
        updated_config = load_config()
        if updated_config is not None:
            # Update the app's config reference
            self._app._config = updated_config

        # Update the tray icon to reflect any status change
        if self._icon is not None:
            self._icon.icon = self._create_icon(self._app.status)
            self._icon.menu = self._build_menu()

    def _on_toggle_start_stop(self) -> None:
        """Toggle the client agent between started and stopped states.

        Runs the async start/stop in a background thread since
        pystray's menu callbacks are synchronous.
        """
        def _toggle() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if self._app.status == "stopped":
                    loop.run_until_complete(self._app.start())
                else:
                    loop.run_until_complete(self._app.stop())
            finally:
                loop.close()

            # Update the tray icon
            if self._icon is not None:
                self._icon.icon = self._create_icon(self._app.status)
                self._icon.menu = self._build_menu()

        thread = threading.Thread(target=_toggle, daemon=True)
        thread.start()

    def _on_exit(self) -> None:
        """Stop the client agent and exit the tray application."""
        # Stop the app in a background thread
        def _shutdown() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._app.stop())
            finally:
                loop.close()

        thread = threading.Thread(target=_shutdown, daemon=True)
        thread.start()
        thread.join(timeout=5)

        self.stop()


class SettingsWindow:
    """Tkinter settings window for Vision OS Connect configuration.

    Provides form fields for all ``AppConfig`` settings:
    - API Key (with placeholder for QR scan button)
    - Camera Name
    - RTSP URL
    - Camera Mode dropdown
    - Audio Enabled checkbox
    - Auto Start checkbox
    - Save button

    Usage:
        window = SettingsWindow(config)
        window.show()
    """

    def __init__(self, config: AppConfig) -> None:
        """Build the settings window UI.

        Args:
            config: An ``AppConfig`` instance to populate the fields with.
        """
        self._config = config
        self._window: Optional[tk.Tk] = None

        # ── StringVars for form fields ──────────────────────────────────
        self._api_key_var = tk.StringVar(value=config.api_key)
        self._camera_name_var = tk.StringVar(value=config.camera_name)
        self._rtsp_url_var = tk.StringVar(value=config.rtsp_url)
        self._mode_var = tk.StringVar(value=config.mode)
        self._audio_enabled_var = tk.BooleanVar(value=config.audio_enabled)
        self._auto_start_var = tk.BooleanVar(value=config.auto_start)

    # ── Public API ───────────────────────────────────────────────────────────

    def show(self) -> None:
        """Display the settings window (blocking).

        Creates and shows the tkinter window.  This call blocks
        until the user closes the window.
        """
        self._window = tk.Tk()
        self._window.title(WINDOW_TITLE)
        self._window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self._window.resizable(False, False)

        # Centre the window on screen
        self._window.update_idletasks()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        x = (screen_w - WINDOW_WIDTH) // 2
        y = (screen_h - WINDOW_HEIGHT) // 2
        self._window.geometry(f"+{x}+{y}")

        self._build_form()
        self._window.mainloop()

    # ── Internal: Form Building ──────────────────────────────────────────────

    def _build_form(self) -> None:
        """Build the settings form with all fields and the Save button."""
        if self._window is None:
            return

        main_frame = ttk.Frame(self._window, padding=PADDING)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── API Key ──────────────────────────────────────────────────────
        row = 0
        ttk.Label(main_frame, text="API Key:", width=LABEL_WIDTH).grid(
            row=row, column=0, sticky=tk.W, pady=4
        )
        api_entry = ttk.Entry(
            main_frame,
            textvariable=self._api_key_var,
            width=40,
            show="*",  # mask the API key
        )
        api_entry.grid(row=row, column=1, sticky=tk.EW, padx=(0, 4), pady=4)

        # QR scan button (placeholder — future enhancement)
        qr_btn = ttk.Button(
            main_frame,
            text="QR",
            width=4,
            command=self._on_qr_scan,
        )
        qr_btn.grid(row=row, column=2, padx=(0, 0), pady=4)

        # ── Camera Name ──────────────────────────────────────────────────
        row += 1
        ttk.Label(main_frame, text="Camera Name:", width=LABEL_WIDTH).grid(
            row=row, column=0, sticky=tk.W, pady=4
        )
        ttk.Entry(
            main_frame,
            textvariable=self._camera_name_var,
            width=40,
        ).grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=4)

        # ── RTSP URL ─────────────────────────────────────────────────────
        row += 1
        ttk.Label(main_frame, text="RTSP URL:", width=LABEL_WIDTH).grid(
            row=row, column=0, sticky=tk.W, pady=4
        )
        ttk.Entry(
            main_frame,
            textvariable=self._rtsp_url_var,
            width=40,
        ).grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=4)

        # ── Camera Mode ──────────────────────────────────────────────────
        row += 1
        ttk.Label(main_frame, text="Camera Mode:", width=LABEL_WIDTH).grid(
            row=row, column=0, sticky=tk.W, pady=4
        )
        mode_combo = ttk.Combobox(
            main_frame,
            textvariable=self._mode_var,
            values=CAMERA_MODES,
            state="readonly",
            width=37,
        )
        mode_combo.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=4)

        # ── Audio Enabled ────────────────────────────────────────────────
        row += 1
        ttk.Checkbutton(
            main_frame,
            text="Audio Enabled (YAMNet sound classification)",
            variable=self._audio_enabled_var,
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=4)

        # ── Auto Start ───────────────────────────────────────────────────
        row += 1
        ttk.Checkbutton(
            main_frame,
            text="Auto Start on Launch",
            variable=self._auto_start_var,
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=4)

        # ── Spacer ───────────────────────────────────────────────────────
        row += 1
        main_frame.grid_rowconfigure(row, weight=1)

        # ── Save Button ──────────────────────────────────────────────────
        row += 1
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="Save",
            command=self._on_save,
            width=15,
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            btn_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15,
        ).pack(side=tk.LEFT)

        # Make the entry column expandable
        main_frame.columnconfigure(1, weight=1)

    # ── Internal: Actions ────────────────────────────────────────────────────

    def _on_save(self) -> None:
        """Validate form fields and save the configuration.

        Performs basic validation:
        - API Key must not be empty
        - RTSP URL must not be empty
        - Camera Name must not be empty

        On success, saves to disk and closes the window.
        On validation failure, shows an error message.
        """
        api_key = self._api_key_var.get().strip()
        camera_name = self._camera_name_var.get().strip()
        rtsp_url = self._rtsp_url_var.get().strip()

        # Validation
        errors = []
        if not api_key:
            errors.append("API Key is required")
        if not camera_name:
            errors.append("Camera Name is required")
        if not rtsp_url:
            errors.append("RTSP URL is required")

        if errors:
            error_msg = "\n".join(errors)
            if self._window is not None:
                tk.messagebox.showerror(
                    "Validation Error",
                    error_msg,
                    parent=self._window,
                )
            return

        # Build updated config
        updated = AppConfig(
            api_key=api_key,
            camera_id=self._config.camera_id,  # keep existing camera_id
            camera_name=camera_name,
            rtsp_url=rtsp_url,
            mode=self._mode_var.get(),
            backend_url=self._config.backend_url,  # keep existing backend_url
            audio_enabled=self._audio_enabled_var.get(),
            auto_start=self._auto_start_var.get(),
            ignore_zones=self._config.ignore_zones,  # keep existing zones
        )

        # Save to disk
        save_config(updated)

        logger.info("Settings saved successfully")

        # Close the window
        self._close()

    def _on_cancel(self) -> None:
        """Close the settings window without saving."""
        logger.debug("Settings window closed without saving")
        self._close()

    def _on_qr_scan(self) -> None:
        """Placeholder for QR code scan functionality.

        Future enhancement: open camera to scan QR code containing
        API key and backend URL for quick setup.
        """
        if self._window is not None:
            tk.messagebox.showinfo(
                "QR Scan",
                "QR code scanning is not yet implemented.\n"
                "Please enter your API Key manually.",
                parent=self._window,
            )

    def _close(self) -> None:
        """Close the settings window."""
        if self._window is not None:
            self._window.quit()
            self._window.destroy()
            self._window = None
