"""
Pro AutoClicker - Advanced High-Performance Mouse Automation
Features:
- Action Modes: Single/Repeated Clicks OR Mouse Holding (Continuous or Pulse Cycle)
- Mouse Buttons: Left, Right, Middle
- Click Types: Single, Double, Triple
- Timed Intervals: Hours, Minutes, Seconds, Milliseconds with Random Jitter
- Stop Conditions: Infinite (Manual), Timed Duration, or Max Click Count
- Location Modes: Follow Cursor or Fixed Screen Coordinates (with coordinate picker)
- Global Hotkeys: Configurable Start/Stop (Default: F6) and Pick Coordinate (Default: F7)
- Safety: Top-Left Screen Corner Failsafe, Safe Mouse Button Release on Stop
- Live Statistics: Elapsed Time, Countdown Timer, Total Clicks, CPS Monitor
"""

import sys
import time
import random
import threading
import winsound
import ctypes
from ctypes import wintypes
import customtkinter as ctk
from pynput import keyboard

# Enable DPI Awareness for crisp UI and accurate coordinates on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Win32 Constants
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040

user32 = ctypes.windll.user32
winmm = ctypes.windll.winmm


class MouseController:
    """Direct Windows user32 mouse simulation with ultra-low latency."""

    def __init__(self):
        # Request 1ms timer resolution from the Windows kernel
        try:
            winmm.timeBeginPeriod(1)
        except Exception:
            pass
        self._is_holding = False
        self._held_button = None

    def __del__(self):
        self.release_all()
        try:
            winmm.timeEndPeriod(1)
        except Exception:
            pass

    def get_cursor_pos(self):
        """Returns the current mouse cursor position as (x, y)."""
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def set_cursor_pos(self, x, y):
        """Moves cursor to specific screen coordinates."""
        user32.SetCursorPos(int(x), int(y))

    def press(self, button: str):
        """Presses down a mouse button and keeps it held."""
        button = button.lower()
        if button == "left":
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        elif button == "right":
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        elif button == "middle":
            user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
        self._is_holding = True
        self._held_button = button

    def release(self, button: str):
        """Releases a mouse button."""
        button = button.lower()
        if button == "left":
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif button == "right":
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        elif button == "middle":
            user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
        if self._held_button == button:
            self._is_holding = False
            self._held_button = None

    def release_all(self):
        """Safety release for all mouse buttons to prevent stuck keys."""
        flags = MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP
        user32.mouse_event(flags, 0, 0, 0, 0)
        self._is_holding = False
        self._held_button = None

    def click(self, button: str, count: int = 1):
        """Performs one or multiple rapid clicks."""
        for i in range(count):
            self.press(button)
            time.sleep(0.003)  # 3ms press duration for reliable OS event registration
            self.release(button)
            if i < count - 1:
                time.sleep(0.030)  # Gap between multiple clicks (e.g. double click)


class ClickerEngine:
    """Background engine handling clicking or holding loops."""

    def __init__(self, mouse: MouseController, on_update_callback, on_stop_callback):
        self.mouse = mouse
        self.on_update = on_update_callback
        self.on_stop = on_stop_callback
        
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        
        self.total_clicks = 0
        self.start_time = 0.0

    def start(self, config: dict):
        if self.running:
            return
        
        self.config = config
        self.running = True
        self.total_clicks = 0
        self.start_time = time.perf_counter()
        self._stop_event.clear()

        # Play sound cue if enabled
        if config.get("sound_cue", False):
            try:
                winsound.Beep(900, 80)
            except Exception:
                pass

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self, reason: str = "Stopped"):
        if not self.running:
            return
        self.running = False
        self._stop_event.set()
        
        # Always guarantee all mouse buttons are released
        self.mouse.release_all()

        # Play stop sound cue if enabled
        if self.config.get("sound_cue", False):
            try:
                winsound.Beep(600, 80)
            except Exception:
                pass

        if self.on_stop:
            self.on_stop(reason)

    def _sleep_interruptible(self, duration_sec: float) -> bool:
        """Sleeps for duration_sec while checking stop event frequently. Returns False if interrupted."""
        if duration_sec <= 0:
            return not self._stop_event.is_set()
        
        end_time = time.perf_counter() + duration_sec
        while time.perf_counter() < end_time:
            if self._stop_event.is_set() or not self.running:
                return False
            # Check corner failsafe
            if self.config.get("failsafe", True):
                cx, cy = self.mouse.get_cursor_pos()
                if cx <= 3 and cy <= 3:
                    self.stop("Failsafe triggered (Mouse moved to top-left corner)")
                    return False
            time.sleep(0.003)
        return True

    def _run_loop(self):
        button = self.config["button"]
        mode = self.config["mode"]  # "Single Click" or "Hold Mouse"
        click_type_count = self.config.get("click_type_count", 1)  # 1=single, 2=double, 3=triple
        
        stop_cond = self.config["stop_condition"]  # "Infinite", "Duration", "Clicks"
        max_duration_sec = self.config.get("max_duration_sec", 0.0)
        max_clicks = self.config.get("max_clicks", 0)
        
        interval_sec = self.config.get("interval_sec", 0.1)
        jitter_sec = self.config.get("jitter_sec", 0.0)
        
        is_fixed_loc = self.config.get("fixed_location", False)
        fixed_x = self.config.get("fixed_x", 0)
        fixed_y = self.config.get("fixed_y", 0)

        # Holding specific config
        hold_type = self.config.get("hold_type", "Continuous Hold")
        hold_time_sec = self.config.get("hold_time_sec", 1.0)
        release_time_sec = self.config.get("release_time_sec", 0.2)

        try:
            if mode == "Hold Mouse" and hold_type == "Continuous Hold":
                # Continuous Hold mode: press down once and hold until duration ends or stopped
                if is_fixed_loc:
                    self.mouse.set_cursor_pos(fixed_x, fixed_y)
                self.mouse.press(button)
                self.total_clicks = 1

                while self.running and not self._stop_event.is_set():
                    elapsed = time.perf_counter() - self.start_time
                    
                    if stop_cond == "Duration" and elapsed >= max_duration_sec:
                        self.mouse.release(button)
                        self.stop("Duration reached")
                        return

                    if self.on_update:
                        rem = (max_duration_sec - elapsed) if stop_cond == "Duration" else -1.0
                        self.on_update(elapsed, rem, self.total_clicks)

                    if not self._sleep_interruptible(0.02):
                        break

            elif mode == "Hold Mouse" and hold_type == "Hold & Release Cycle":
                # Hold & Release cycle mode: press for X sec, release for Y sec, repeat
                while self.running and not self._stop_event.is_set():
                    elapsed = time.perf_counter() - self.start_time
                    if stop_cond == "Duration" and elapsed >= max_duration_sec:
                        self.stop("Duration reached")
                        return

                    if is_fixed_loc:
                        self.mouse.set_cursor_pos(fixed_x, fixed_y)

                    # Press and hold
                    self.mouse.press(button)
                    self.total_clicks += 1

                    hold_start = time.perf_counter()
                    while time.perf_counter() - hold_start < hold_time_sec:
                        if not self.running or self._stop_event.is_set():
                            break
                        elapsed = time.perf_counter() - self.start_time
                        if stop_cond == "Duration" and elapsed >= max_duration_sec:
                            self.mouse.release(button)
                            self.stop("Duration reached")
                            return
                        if self.on_update:
                            rem = (max_duration_sec - elapsed) if stop_cond == "Duration" else -1.0
                            self.on_update(elapsed, rem, self.total_clicks)
                        time.sleep(0.005)

                    # Release
                    self.mouse.release(button)
                    if not self.running or self._stop_event.is_set():
                        break

                    # Wait release duration
                    if not self._sleep_interruptible(release_time_sec):
                        break

            else:
                # Repeated Click Mode
                while self.running and not self._stop_event.is_set():
                    elapsed = time.perf_counter() - self.start_time
                    
                    # Check stop conditions
                    if stop_cond == "Duration" and elapsed >= max_duration_sec:
                        self.stop("Duration reached")
                        return
                    if stop_cond == "Clicks" and self.total_clicks >= max_clicks:
                        self.stop("Target click count reached")
                        return

                    # Move to fixed coordinates if enabled
                    if is_fixed_loc:
                        self.mouse.set_cursor_pos(fixed_x, fixed_y)

                    # Execute click
                    self.mouse.click(button, count=click_type_count)
                    self.total_clicks += click_type_count

                    # Compute next sleep interval with jitter
                    current_interval = interval_sec
                    if jitter_sec > 0:
                        current_interval += random.uniform(-jitter_sec, jitter_sec)
                        current_interval = max(0.001, current_interval)

                    # Update UI progress
                    if self.on_update:
                        rem = (max_duration_sec - elapsed) if stop_cond == "Duration" else -1.0
                        self.on_update(elapsed, rem, self.total_clicks)

                    # Sleep until next click
                    if not self._sleep_interruptible(current_interval):
                        break

        finally:
            self.mouse.release_all()


class AutoClickerApp(ctk.CTk):
    """Modern GUI for the Pro AutoClicker."""

    def __init__(self):
        super().__init__()

        self.title("⚡ Pro AutoClicker")
        self.geometry("640x790")
        self.minsize(580, 720)

        # Set CustomTkinter theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.mouse = MouseController()
        self.engine = ClickerEngine(
            mouse=self.mouse,
            on_update_callback=self._on_engine_update,
            on_stop_callback=self._on_engine_stop
        )

        # State Variables
        self.start_hotkey_str = "F6"
        self.pick_hotkey_str = "F7"
        self.is_rebinding_start = False
        self.is_picking_location = False

        self._init_hotkey_listener()
        self._build_ui()
        self._start_cursor_tracker()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_hotkey_listener(self):
        """Initializes global hotkey listener with pynput."""
        def on_press(key):
            key_name = self._format_key(key)
            
            # If rebinding start/stop hotkey
            if self.is_rebinding_start:
                self.start_hotkey_str = key_name
                self.is_rebinding_start = False
                self.after(0, self._update_hotkey_labels)
                return

            # Check Start/Stop toggle
            if key_name == self.start_hotkey_str:
                self.after(0, self.toggle_start_stop)
                return

            # Check Pick Coordinates
            if key_name == self.pick_hotkey_str:
                cx, cy = self.mouse.get_cursor_pos()
                self.after(0, lambda: self._apply_picked_location(cx, cy))
                return

        self.kb_listener = keyboard.Listener(on_press=on_press)
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def _format_key(self, key):
        if hasattr(key, 'name') and key.name:
            return key.name.upper()
        if hasattr(key, 'char') and key.char:
            return key.char.upper()
        return str(key).upper()

    def _build_ui(self):
        # Main scrollable or structured frame
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=16, pady=12)

        # Top Header Bar
        self._build_header(self.main_container)

        # Status Banner
        self._build_status_banner(self.main_container)

        # Card 1: Action Mode & Mouse Button
        self._build_mode_and_button_card(self.main_container)

        # Card 2: Timing & Intervals
        self._build_interval_card(self.main_container)

        # Card 3: Stop Condition ("How Much Time")
        self._build_duration_card(self.main_container)

        # Card 4: Cursor Location
        self._build_location_card(self.main_container)

        # Card 5: Live Statistics Dashboard
        self._build_stats_card(self.main_container)

        # Bottom Action Buttons
        self._build_action_buttons(self.main_container)

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")

        title = ctk.CTkLabel(
            title_frame, 
            text="⚡ PRO AUTOCLICKER", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_frame, 
            text="High Precision Mouse Automation • v2.0", 
            font=ctk.CTkFont(size=12), 
            text_color="gray"
        )
        subtitle.pack(anchor="w")

        # Right side toggles
        toggles_frame = ctk.CTkFrame(header, fg_color="transparent")
        toggles_frame.pack(side="right", pady=4)

        self.topmost_var = ctk.BooleanVar(value=True)
        self.always_on_top_chk = ctk.CTkCheckBox(
            toggles_frame, 
            text="Always on Top", 
            variable=self.topmost_var,
            command=self._toggle_topmost,
            font=ctk.CTkFont(size=12)
        )
        self.always_on_top_chk.pack(side="top", anchor="e", pady=2)
        self.attributes("-topmost", True)

        self.sound_var = ctk.BooleanVar(value=True)
        self.sound_chk = ctk.CTkCheckBox(
            toggles_frame, 
            text="Sound Cue", 
            variable=self.sound_var,
            font=ctk.CTkFont(size=12)
        )
        self.sound_chk.pack(side="top", anchor="e", pady=2)

    def _toggle_topmost(self):
        self.attributes("-topmost", self.topmost_var.get())

    def _build_status_banner(self, parent):
        self.status_frame = ctk.CTkFrame(parent, fg_color="#1e222d", corner_radius=8, border_width=1, border_color="#2c3242")
        self.status_frame.pack(fill="x", pady=6)

        self.status_dot = ctk.CTkLabel(
            self.status_frame, 
            text="●", 
            font=ctk.CTkFont(size=16), 
            text_color="#8892b0"
        )
        self.status_dot.pack(side="left", padx=(12, 6), pady=8)

        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text=f"STOPPED • Press {self.start_hotkey_str} to Start", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#cbd5e1"
        )
        self.status_label.pack(side="left", pady=8)

        # Failsafe indicator
        self.failsafe_label = ctk.CTkLabel(
            self.status_frame,
            text="🛡️ Failsafe: Move cursor to top-left corner",
            font=ctk.CTkFont(size=11),
            text_color="#64748b"
        )
        self.failsafe_label.pack(side="right", padx=12, pady=8)

    def _build_mode_and_button_card(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", pady=6, padx=2)

        card_title = ctk.CTkLabel(card, text="1. ACTION MODE & MOUSE BUTTON", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        card_title.pack(anchor="w", padx=14, pady=(10, 6))

        # Mode Selection Row
        mode_row = ctk.CTkFrame(card, fg_color="transparent")
        mode_row.pack(fill="x", padx=14, pady=4)

        mode_lbl = ctk.CTkLabel(mode_row, text="Action Mode:", font=ctk.CTkFont(size=12, weight="bold"), width=90, anchor="w")
        mode_lbl.pack(side="left")

        self.mode_var = ctk.StringVar(value="Single Click")
        self.mode_seg = ctk.CTkSegmentedButton(
            mode_row, 
            values=["Single Click", "Hold Mouse"], 
            variable=self.mode_var,
            command=self._on_mode_change
        )
        self.mode_seg.pack(side="left", fill="x", expand=True)

        # Mouse Button Selection Row
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=6)

        btn_lbl = ctk.CTkLabel(btn_row, text="Mouse Button:", font=ctk.CTkFont(size=12, weight="bold"), width=90, anchor="w")
        btn_lbl.pack(side="left")

        self.button_var = ctk.StringVar(value="Left")
        self.button_seg = ctk.CTkSegmentedButton(
            btn_row, 
            values=["Left", "Right", "Middle"], 
            variable=self.button_var
        )
        self.button_seg.pack(side="left", fill="x", expand=True)

        # Dynamic Submode Row (Click Type or Hold Mode)
        self.submode_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.submode_frame.pack(fill="x", padx=14, pady=(2, 10))
        self._update_submode_ui()

    def _on_mode_change(self, value):
        self._update_submode_ui()
        self._update_interval_ui()

    def _update_submode_ui(self):
        for w in self.submode_frame.winfo_children():
            w.destroy()

        mode = self.mode_var.get()
        if mode == "Single Click":
            lbl = ctk.CTkLabel(self.submode_frame, text="Click Type:", font=ctk.CTkFont(size=12, weight="bold"), width=90, anchor="w")
            lbl.pack(side="left")
            self.click_type_var = ctk.StringVar(value="Single")
            self.click_type_seg = ctk.CTkSegmentedButton(
                self.submode_frame,
                values=["Single", "Double", "Triple"],
                variable=self.click_type_var
            )
            self.click_type_seg.pack(side="left", fill="x", expand=True)
        else:
            lbl = ctk.CTkLabel(self.submode_frame, text="Hold Mode:", font=ctk.CTkFont(size=12, weight="bold"), width=90, anchor="w")
            lbl.pack(side="left")
            self.hold_type_var = ctk.StringVar(value="Continuous Hold")
            self.hold_type_seg = ctk.CTkSegmentedButton(
                self.submode_frame,
                values=["Continuous Hold", "Hold & Release Cycle"],
                variable=self.hold_type_var,
                command=lambda _: self._update_interval_ui()
            )
            self.hold_type_seg.pack(side="left", fill="x", expand=True)

    def _build_interval_card(self, parent):
        self.interval_card = ctk.CTkFrame(parent, corner_radius=10)
        self.interval_card.pack(fill="x", pady=6, padx=2)

        self.interval_title = ctk.CTkLabel(
            self.interval_card, 
            text="2. TIMED INTERVALS (CLICK FREQUENCY)", 
            font=ctk.CTkFont(size=13, weight="bold"), 
            text_color="#38bdf8"
        )
        self.interval_title.pack(anchor="w", padx=14, pady=(10, 6))

        # Dynamic body container for interval inputs
        self.interval_body = ctk.CTkFrame(self.interval_card, fg_color="transparent")
        self.interval_body.pack(fill="x", padx=14, pady=(0, 10))

        # Build initial interval widgets
        self._update_interval_ui()

    def _update_interval_ui(self):
        for w in self.interval_body.winfo_children():
            w.destroy()

        mode = self.mode_var.get()
        
        if mode == "Single Click":
            self.interval_title.configure(text="2. TIMED INTERVALS (DELAY BETWEEN CLICKS)")
            
            # Hours / Mins / Secs / Millis inputs
            inputs_row = ctk.CTkFrame(self.interval_body, fg_color="transparent")
            inputs_row.pack(fill="x", pady=4)

            # Hours
            self.int_h_var = ctk.StringVar(value="0")
            h_box = self._create_spin_field(inputs_row, "Hours", self.int_h_var, width=54)
            h_box.pack(side="left", expand=True, fill="x", padx=2)

            # Minutes
            self.int_m_var = ctk.StringVar(value="0")
            m_box = self._create_spin_field(inputs_row, "Mins", self.int_m_var, width=54)
            m_box.pack(side="left", expand=True, fill="x", padx=2)

            # Seconds
            self.int_s_var = ctk.StringVar(value="0")
            s_box = self._create_spin_field(inputs_row, "Secs", self.int_s_var, width=54)
            s_box.pack(side="left", expand=True, fill="x", padx=2)

            # Milliseconds
            self.int_ms_var = ctk.StringVar(value="100")
            ms_box = self._create_spin_field(inputs_row, "Millis (ms)", self.int_ms_var, width=70)
            ms_box.pack(side="left", expand=True, fill="x", padx=2)

            # Quick Presets Buttons Row
            presets_row = ctk.CTkFrame(self.interval_body, fg_color="transparent")
            presets_row.pack(fill="x", pady=(6, 4))
            
            p_lbl = ctk.CTkLabel(presets_row, text="Presets:", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray", width=55, anchor="w")
            p_lbl.pack(side="left")

            presets = [
                ("1 CPS", 1000),
                ("5 CPS", 200),
                ("10 CPS", 100),
                ("20 CPS", 50),
                ("50 CPS", 20),
                ("Max (1ms)", 1)
            ]
            for label, ms in presets:
                btn = ctk.CTkButton(
                    presets_row, 
                    text=label, 
                    width=48, 
                    height=24, 
                    font=ctk.CTkFont(size=11),
                    fg_color="#334155",
                    hover_color="#475569",
                    command=lambda m=ms: self._apply_interval_preset(m)
                )
                btn.pack(side="left", expand=True, fill="x", padx=2)

            # Jitter Row
            jitter_row = ctk.CTkFrame(self.interval_body, fg_color="transparent")
            jitter_row.pack(fill="x", pady=(6, 2))

            self.jitter_enable_var = ctk.BooleanVar(value=False)
            jitter_chk = ctk.CTkCheckBox(
                jitter_row,
                text="Random Jitter (Anti-Detection): ±",
                variable=self.jitter_enable_var,
                font=ctk.CTkFont(size=12)
            )
            jitter_chk.pack(side="left")

            self.jitter_ms_var = ctk.StringVar(value="15")
            jitter_ent = ctk.CTkEntry(jitter_row, textvariable=self.jitter_ms_var, width=55, font=ctk.CTkFont(size=12))
            jitter_ent.pack(side="left", padx=4)

            ms_unit = ctk.CTkLabel(jitter_row, text="ms", font=ctk.CTkFont(size=12), text_color="gray")
            ms_unit.pack(side="left")

        else:
            # Hold Mode
            hold_sub = getattr(self, "hold_type_var", None)
            hold_sub_val = hold_sub.get() if hold_sub else "Continuous Hold"
            
            if hold_sub_val == "Continuous Hold":
                self.interval_title.configure(text="2. HOLD CONFIGURATION")
                info_lbl = ctk.CTkLabel(
                    self.interval_body,
                    text="⚡ In Continuous Hold mode, the mouse button is pressed and held down\ncontinuously until the duration expires or you press the Stop hotkey.",
                    font=ctk.CTkFont(size=12),
                    text_color="#94a3b8",
                    justify="left"
                )
                info_lbl.pack(anchor="w", pady=6)
            else:
                self.interval_title.configure(text="2. HOLD & RELEASE CYCLE TIMINGS")
                
                cycle_frame = ctk.CTkFrame(self.interval_body, fg_color="transparent")
                cycle_frame.pack(fill="x", pady=4)

                # Hold Duration
                hold_lbl = ctk.CTkLabel(cycle_frame, text="Hold Down Time (ms):", font=ctk.CTkFont(size=12), width=140, anchor="w")
                hold_lbl.grid(row=0, column=0, pady=4, sticky="w")
                self.cycle_hold_ms_var = ctk.StringVar(value="1000")
                hold_ent = ctk.CTkEntry(cycle_frame, textvariable=self.cycle_hold_ms_var, width=100)
                hold_ent.grid(row=0, column=1, pady=4, sticky="w")

                # Release Duration
                rel_lbl = ctk.CTkLabel(cycle_frame, text="Release Pause Time (ms):", font=ctk.CTkFont(size=12), width=140, anchor="w")
                rel_lbl.grid(row=1, column=0, pady=4, sticky="w")
                self.cycle_rel_ms_var = ctk.StringVar(value="250")
                rel_ent = ctk.CTkEntry(cycle_frame, textvariable=self.cycle_rel_ms_var, width=100)
                rel_ent.grid(row=1, column=1, pady=4, sticky="w")

    def _apply_interval_preset(self, ms: int):
        self.int_h_var.set("0")
        self.int_m_var.set("0")
        if ms >= 1000:
            self.int_s_var.set(str(ms // 1000))
            self.int_ms_var.set(str(ms % 1000))
        else:
            self.int_s_var.set("0")
            self.int_ms_var.set(str(ms))

    def _build_duration_card(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", pady=6, padx=2)

        card_title = ctk.CTkLabel(card, text="3. HOW MUCH TIME / STOP CONDITION", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        card_title.pack(anchor="w", padx=14, pady=(10, 6))

        # Stop Condition Selector
        cond_row = ctk.CTkFrame(card, fg_color="transparent")
        cond_row.pack(fill="x", padx=14, pady=4)

        self.stop_cond_var = ctk.StringVar(value="Infinite")
        self.stop_cond_seg = ctk.CTkSegmentedButton(
            cond_row,
            values=["Infinite (Manual)", "Set Duration", "Max Clicks"],
            variable=self.stop_cond_var,
            command=self._on_stop_cond_change
        )
        self.stop_cond_seg.pack(fill="x", expand=True)

        # Dynamic Stop Body
        self.stop_body = ctk.CTkFrame(card, fg_color="transparent")
        self.stop_body.pack(fill="x", padx=14, pady=(4, 10))
        self._update_stop_cond_ui()

    def _on_stop_cond_change(self, value):
        self._update_stop_cond_ui()

    def _update_stop_cond_ui(self):
        for w in self.stop_body.winfo_children():
            w.destroy()

        cond = self.stop_cond_var.get()

        if cond == "Infinite (Manual)":
            lbl = ctk.CTkLabel(
                self.stop_body,
                text=f"Runs continuously until you press the hotkey ({self.start_hotkey_str}) or click Stop.",
                font=ctk.CTkFont(size=12),
                text_color="#94a3b8"
            )
            lbl.pack(anchor="w", pady=4)

        elif cond == "Set Duration":
            # Time Inputs for Duration
            inputs_row = ctk.CTkFrame(self.stop_body, fg_color="transparent")
            inputs_row.pack(fill="x", pady=4)

            self.dur_h_var = ctk.StringVar(value="0")
            h_box = self._create_spin_field(inputs_row, "Hours", self.dur_h_var, width=54)
            h_box.pack(side="left", expand=True, fill="x", padx=2)

            self.dur_m_var = ctk.StringVar(value="1")
            m_box = self._create_spin_field(inputs_row, "Mins", self.dur_m_var, width=54)
            m_box.pack(side="left", expand=True, fill="x", padx=2)

            self.dur_s_var = ctk.StringVar(value="0")
            s_box = self._create_spin_field(inputs_row, "Secs", self.dur_s_var, width=54)
            s_box.pack(side="left", expand=True, fill="x", padx=2)

            self.dur_ms_var = ctk.StringVar(value="0")
            ms_box = self._create_spin_field(inputs_row, "Millis (ms)", self.dur_ms_var, width=70)
            ms_box.pack(side="left", expand=True, fill="x", padx=2)

            # Quick Time Preset Buttons
            p_row = ctk.CTkFrame(self.stop_body, fg_color="transparent")
            p_row.pack(fill="x", pady=(6, 2))

            p_lbl = ctk.CTkLabel(p_row, text="Presets:", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray", width=55, anchor="w")
            p_lbl.pack(side="left")

            dur_presets = [
                ("10s", 0, 0, 10),
                ("30s", 0, 0, 30),
                ("1 min", 0, 1, 0),
                ("5 min", 0, 5, 0),
                ("15 min", 0, 15, 0),
                ("1 hour", 1, 0, 0)
            ]
            for label, h, m, s in dur_presets:
                btn = ctk.CTkButton(
                    p_row,
                    text=label,
                    width=48,
                    height=24,
                    font=ctk.CTkFont(size=11),
                    fg_color="#334155",
                    hover_color="#475569",
                    command=lambda h=h, m=m, s=s: self._apply_duration_preset(h, m, s)
                )
                btn.pack(side="left", expand=True, fill="x", padx=2)

        elif cond == "Max Clicks":
            click_row = ctk.CTkFrame(self.stop_body, fg_color="transparent")
            click_row.pack(fill="x", pady=4)

            lbl = ctk.CTkLabel(click_row, text="Stop after exactly:", font=ctk.CTkFont(size=12), width=120, anchor="w")
            lbl.pack(side="left")

            self.max_clicks_var = ctk.StringVar(value="500")
            ent = ctk.CTkEntry(click_row, textvariable=self.max_clicks_var, width=90)
            ent.pack(side="left", padx=4)

            unit = ctk.CTkLabel(click_row, text="clicks", font=ctk.CTkFont(size=12), text_color="gray")
            unit.pack(side="left")

            # Presets
            for count in [100, 500, 1000, 5000]:
                btn = ctk.CTkButton(
                    click_row,
                    text=str(count),
                    width=44,
                    height=24,
                    font=ctk.CTkFont(size=11),
                    fg_color="#334155",
                    hover_color="#475569",
                    command=lambda c=count: self.max_clicks_var.set(str(c))
                )
                btn.pack(side="left", padx=2)

    def _apply_duration_preset(self, h, m, s):
        self.dur_h_var.set(str(h))
        self.dur_m_var.set(str(m))
        self.dur_s_var.set(str(s))
        self.dur_ms_var.set("0")

    def _build_location_card(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", pady=6, padx=2)

        card_title = ctk.CTkLabel(card, text="4. CLICK LOCATION", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        card_title.pack(anchor="w", padx=14, pady=(10, 6))

        loc_row = ctk.CTkFrame(card, fg_color="transparent")
        loc_row.pack(fill="x", padx=14, pady=4)

        self.loc_mode_var = ctk.StringVar(value="Current Cursor")
        self.loc_seg = ctk.CTkSegmentedButton(
            loc_row,
            values=["Current Cursor", "Fixed Coordinates"],
            variable=self.loc_mode_var,
            command=self._on_loc_mode_change
        )
        self.loc_seg.pack(side="left", fill="x", expand=True)

        # Coordinate inputs and pick button
        self.coords_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.coords_frame.pack(fill="x", padx=14, pady=(4, 10))

        # Fixed coordinates X, Y
        x_lbl = ctk.CTkLabel(self.coords_frame, text="X:", font=ctk.CTkFont(size=12, weight="bold"))
        x_lbl.pack(side="left", padx=(0, 2))
        self.coord_x_var = ctk.StringVar(value="500")
        self.coord_x_ent = ctk.CTkEntry(self.coords_frame, textvariable=self.coord_x_var, width=65)
        self.coord_x_ent.pack(side="left", padx=(0, 8))

        y_lbl = ctk.CTkLabel(self.coords_frame, text="Y:", font=ctk.CTkFont(size=12, weight="bold"))
        y_lbl.pack(side="left", padx=(0, 2))
        self.coord_y_var = ctk.StringVar(value="500")
        self.coord_y_ent = ctk.CTkEntry(self.coords_frame, textvariable=self.coord_y_var, width=65)
        self.coord_y_ent.pack(side="left", padx=(0, 10))

        # Pick location button
        self.pick_btn = ctk.CTkButton(
            self.coords_frame,
            text=f"🎯 Pick Location ({self.pick_hotkey_str})",
            font=ctk.CTkFont(size=12),
            height=28,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._start_pick_location
        )
        self.pick_btn.pack(side="left", padx=4)

        # Live cursor display
        self.live_cursor_lbl = ctk.CTkLabel(
            self.coords_frame,
            text="Current: (0, 0)",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.live_cursor_lbl.pack(side="right", padx=4)

        self._update_coord_visibility()

    def _on_loc_mode_change(self, value):
        self._update_coord_visibility()

    def _update_coord_visibility(self):
        is_fixed = (self.loc_mode_var.get() == "Fixed Coordinates")
        state = "normal" if is_fixed else "disabled"
        self.coord_x_ent.configure(state=state)
        self.coord_y_ent.configure(state=state)
        self.pick_btn.configure(state=state)

    def _start_pick_location(self):
        self.loc_mode_var.set("Fixed Coordinates")
        self._update_coord_visibility()
        self.status_label.configure(text=f"🎯 Hover over target & press {self.pick_hotkey_str} to lock coordinates!")
        self.status_dot.configure(text_color="#a855f7")

    def _apply_picked_location(self, x, y):
        self.coord_x_var.set(str(x))
        self.coord_y_var.set(str(y))
        self.loc_mode_var.set("Fixed Coordinates")
        self._update_coord_visibility()
        self.status_label.configure(text=f"✓ Locked Coordinates: ({x}, {y})")
        self.status_dot.configure(text_color="#10b981")
        try:
            winsound.Beep(1200, 60)
        except Exception:
            pass

    def _build_stats_card(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color="#181c25")
        card.pack(fill="x", pady=6, padx=2)

        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=14, pady=(8, 4))

        title = ctk.CTkLabel(header_row, text="📊 LIVE DASHBOARD", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        title.pack(side="left")

        self.reset_stats_btn = ctk.CTkButton(
            header_row,
            text="↺ Reset",
            width=55,
            height=22,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._reset_stats
        )
        self.reset_stats_btn.pack(side="right")

        # Stats Grid
        stats_grid = ctk.CTkFrame(card, fg_color="transparent")
        stats_grid.pack(fill="x", padx=14, pady=(0, 10))

        # Clicks
        col1 = ctk.CTkFrame(stats_grid, fg_color="#202634", corner_radius=6)
        col1.pack(side="left", expand=True, fill="both", padx=3, pady=2)
        ctk.CTkLabel(col1, text="CLICKS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(4, 0))
        self.stat_clicks_lbl = ctk.CTkLabel(col1, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#38bdf8")
        self.stat_clicks_lbl.pack(pady=(0, 4))

        # Elapsed
        col2 = ctk.CTkFrame(stats_grid, fg_color="#202634", corner_radius=6)
        col2.pack(side="left", expand=True, fill="both", padx=3, pady=2)
        ctk.CTkLabel(col2, text="ELAPSED", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(4, 0))
        self.stat_elapsed_lbl = ctk.CTkLabel(col2, text="00:00.0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#e2e8f0")
        self.stat_elapsed_lbl.pack(pady=(0, 4))

        # Remaining
        col3 = ctk.CTkFrame(stats_grid, fg_color="#202634", corner_radius=6)
        col3.pack(side="left", expand=True, fill="both", padx=3, pady=2)
        ctk.CTkLabel(col3, text="REMAINING", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(4, 0))
        self.stat_remaining_lbl = ctk.CTkLabel(col3, text="∞", font=ctk.CTkFont(size=16, weight="bold"), text_color="#e2e8f0")
        self.stat_remaining_lbl.pack(pady=(0, 4))

        # CPS
        col4 = ctk.CTkFrame(stats_grid, fg_color="#202634", corner_radius=6)
        col4.pack(side="left", expand=True, fill="both", padx=3, pady=2)
        ctk.CTkLabel(col4, text="SPEED", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(4, 0))
        self.stat_cps_lbl = ctk.CTkLabel(col4, text="0.0 CPS", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10b981")
        self.stat_cps_lbl.pack(pady=(0, 4))

    def _reset_stats(self):
        self.stat_clicks_lbl.configure(text="0")
        self.stat_elapsed_lbl.configure(text="00:00.0")
        self.stat_remaining_lbl.configure(text="∞")
        self.stat_cps_lbl.configure(text="0.0 CPS")

    def _build_action_buttons(self, parent):
        # Hotkey Configuration Row
        hk_frame = ctk.CTkFrame(parent, fg_color="transparent")
        hk_frame.pack(fill="x", pady=(4, 6))

        self.hk_label = ctk.CTkLabel(
            hk_frame, 
            text=f"Start/Stop Hotkey: [{self.start_hotkey_str}]", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#94a3b8"
        )
        self.hk_label.pack(side="left", padx=4)

        self.rebind_btn = ctk.CTkButton(
            hk_frame,
            text="Change Hotkey",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._start_rebind_hotkey
        )
        self.rebind_btn.pack(side="left", padx=6)

        # Big Action Buttons
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=6)

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text=f"▶ START ({self.start_hotkey_str})",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color="#10b981",
            hover_color="#059669",
            command=self.start_clicker
        )
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text=f"⏹ STOP ({self.start_hotkey_str})",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color="#ef4444",
            hover_color="#dc2626",
            state="disabled",
            command=self.stop_clicker
        )
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _start_rebind_hotkey(self):
        self.is_rebinding_start = True
        self.hk_label.configure(text="Press ANY key to bind as Start/Stop...")
        self.rebind_btn.configure(state="disabled")

    def _update_hotkey_labels(self):
        self.is_rebinding_start = False
        self.rebind_btn.configure(state="normal")
        self.hk_label.configure(text=f"Start/Stop Hotkey: [{self.start_hotkey_str}]")
        self.start_btn.configure(text=f"▶ START ({self.start_hotkey_str})")
        self.stop_btn.configure(text=f"⏹ STOP ({self.start_hotkey_str})")
        if not self.engine.running:
            self.status_label.configure(text=f"STOPPED • Press {self.start_hotkey_str} to Start")

    def _create_spin_field(self, parent, label_text, var, width=60):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        lbl = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=11), text_color="gray")
        lbl.pack(side="top", anchor="center")
        ent = ctk.CTkEntry(frame, textvariable=var, width=width, justify="center", font=ctk.CTkFont(size=13, weight="bold"))
        ent.pack(side="top", pady=(2, 0))
        return frame

    def _start_cursor_tracker(self):
        def update_coords():
            try:
                cx, cy = self.mouse.get_cursor_pos()
                self.live_cursor_lbl.configure(text=f"Current: ({cx}, {cy})")
            except Exception:
                pass
            self.after(100, update_coords)
        self.after(100, update_coords)

    def _parse_safe_int(self, val_str, default=0):
        try:
            return max(0, int(val_str.strip()))
        except Exception:
            return default

    def _parse_safe_float(self, val_str, default=0.0):
        try:
            return max(0.0, float(val_str.strip()))
        except Exception:
            return default

    def toggle_start_stop(self):
        if self.engine.running:
            self.stop_clicker()
        else:
            self.start_clicker()

    def start_clicker(self):
        if self.engine.running:
            return

        mode = self.mode_var.get()
        button = self.button_var.get()
        
        # Calculate Interval
        h = self._parse_safe_int(getattr(self, "int_h_var", ctk.StringVar(value="0")).get())
        m = self._parse_safe_int(getattr(self, "int_m_var", ctk.StringVar(value="0")).get())
        s = self._parse_safe_int(getattr(self, "int_s_var", ctk.StringVar(value="0")).get())
        ms = self._parse_safe_int(getattr(self, "int_ms_var", ctk.StringVar(value="100")).get())
        total_interval_sec = (h * 3600) + (m * 60) + s + (ms / 1000.0)
        if total_interval_sec < 0.001:
            total_interval_sec = 0.001

        # Jitter
        jitter_sec = 0.0
        if getattr(self, "jitter_enable_var", ctk.BooleanVar(value=False)).get():
            jitter_ms = self._parse_safe_float(getattr(self, "jitter_ms_var", ctk.StringVar(value="15")).get())
            jitter_sec = jitter_ms / 1000.0

        # Click Type
        click_type_map = {"Single": 1, "Double": 2, "Triple": 3}
        click_type_count = click_type_map.get(getattr(self, "click_type_var", ctk.StringVar(value="Single")).get(), 1)

        # Stop Condition & Durations
        stop_cond = self.stop_cond_var.get()
        max_duration_sec = 0.0
        max_clicks = 0

        if stop_cond == "Set Duration":
            dh = self._parse_safe_int(getattr(self, "dur_h_var", ctk.StringVar(value="0")).get())
            dm = self._parse_safe_int(getattr(self, "dur_m_var", ctk.StringVar(value="0")).get())
            ds = self._parse_safe_int(getattr(self, "dur_s_var", ctk.StringVar(value="0")).get())
            dms = self._parse_safe_int(getattr(self, "dur_ms_var", ctk.StringVar(value="0")).get())
            max_duration_sec = (dh * 3600) + (dm * 60) + ds + (dms / 1000.0)
            if max_duration_sec <= 0:
                max_duration_sec = 1.0  # safety minimum
        elif stop_cond == "Max Clicks":
            max_clicks = self._parse_safe_int(getattr(self, "max_clicks_var", ctk.StringVar(value="500")).get(), default=100)

        # Location
        is_fixed = (self.loc_mode_var.get() == "Fixed Coordinates")
        fx = self._parse_safe_int(self.coord_x_var.get(), 0)
        fy = self._parse_safe_int(self.coord_y_var.get(), 0)

        # Hold timings
        hold_type = getattr(self, "hold_type_var", ctk.StringVar(value="Continuous Hold")).get()
        hold_time_ms = self._parse_safe_float(getattr(self, "cycle_hold_ms_var", ctk.StringVar(value="1000")).get(), 1000)
        rel_time_ms = self._parse_safe_float(getattr(self, "cycle_rel_ms_var", ctk.StringVar(value="250")).get(), 250)

        config = {
            "mode": mode,
            "button": button,
            "click_type_count": click_type_count,
            "interval_sec": total_interval_sec,
            "jitter_sec": jitter_sec,
            "stop_condition": "Duration" if stop_cond == "Set Duration" else ("Clicks" if stop_cond == "Max Clicks" else "Infinite"),
            "max_duration_sec": max_duration_sec,
            "max_clicks": max_clicks,
            "fixed_location": is_fixed,
            "fixed_x": fx,
            "fixed_y": fy,
            "hold_type": hold_type,
            "hold_time_sec": hold_time_ms / 1000.0,
            "release_time_sec": rel_time_ms / 1000.0,
            "failsafe": True,
            "sound_cue": self.sound_var.get()
        }

        # Update UI state
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        if mode == "Hold Mouse":
            self.status_label.configure(text=f"HOLDING: {button} Button ({hold_type})")
            self.status_dot.configure(text_color="#f59e0b")
        else:
            self.status_label.configure(text=f"RUNNING: {button} Click @ {int(total_interval_sec * 1000)}ms")
            self.status_dot.configure(text_color="#10b981")

        self.engine.start(config)

    def stop_clicker(self):
        self.engine.stop("User stopped")

    def _on_engine_update(self, elapsed_sec, remaining_sec, total_clicks):
        def update():
            # Format elapsed mm:ss.s
            em = int(elapsed_sec // 60)
            es = elapsed_sec % 60
            self.stat_elapsed_lbl.configure(text=f"{em:02d}:{es:04.1f}")

            # Format remaining
            if remaining_sec >= 0:
                rm = int(remaining_sec // 60)
                rs = remaining_sec % 60
                self.stat_remaining_lbl.configure(text=f"{rm:02d}:{rs:04.1f}")
            else:
                self.stat_remaining_lbl.configure(text="∞")

            # Clicks and CPS
            self.stat_clicks_lbl.configure(text=f"{total_clicks:,}")
            cps = (total_clicks / elapsed_sec) if elapsed_sec > 0.1 else 0.0
            self.stat_cps_lbl.configure(text=f"{cps:.1f} CPS")

        self.after(0, update)

    def _on_engine_stop(self, reason):
        def update():
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_label.configure(text=f"STOPPED ({reason}) • Press {self.start_hotkey_str} to Start")
            self.status_dot.configure(text_color="#ef4444")

        self.after(0, update)

    def _on_close(self):
        """Clean shutdown handler."""
        try:
            self.engine.stop("Application exiting")
            self.mouse.release_all()
            if hasattr(self, 'kb_listener') and self.kb_listener:
                self.kb_listener.stop()
        except Exception:
            pass
        self.destroy()


def main():
    app = AutoClickerApp()
    app.mainloop()


if __name__ == "__main__":
    main()

