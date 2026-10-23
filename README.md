# ⚡ Pro AutoClicker

A modern, high-performance, ultra-low latency mouse automation tool for Windows built with Python and CustomTkinter.

---

## ✨ Features

### 1. Action Modes
- **Single / Repeated Click**: Clicks repeatedly at your designated interval.
  - Choose click type: **Single Click**, **Double Click**, or **Triple Click**.
- **Mouse Holding**:
  - **Continuous Hold**: Presses down and holds the mouse button continuously until the timer expires or you press Stop.
  - **Hold & Release Cycle**: Presses down and holds for $X$ milliseconds, releases for $Y$ milliseconds, and repeats in a loop (ideal for charged attacks, mining, or interacting in games).

### 2. Mouse Buttons
- **Left Mouse Button**
- **Right Mouse Button**
- **Middle Mouse Button (Scroll Wheel Click)**

### 3. Timed Intervals
- Set precise delays down to 1 millisecond using **Hours**, **Minutes**, **Seconds**, and **Milliseconds** inputs.
- **Quick CPS Presets**:
  - `1 CPS` (1000 ms)
  - `5 CPS` (200 ms)
  - `10 CPS` (100 ms)
  - `20 CPS` (50 ms)
  - `50 CPS` (20 ms)
  - `Max (1ms)` (~1000 CPS)
- **Random Jitter (Anti-Detection)**: Add a customizable random variance (e.g. $\pm 15$ ms) to avoid bot detection or anti-cheat triggers.

### 4. "How Much Time" / Stop Conditions
- **Infinite (Manual Stop)**: Runs continuously until you press the hotkey or Stop button.
- **Set Duration**: Stop automatically after a designated time limit (Hours, Minutes, Seconds, Milliseconds).
  - Quick Presets: `10s`, `30s`, `1 min`, `5 min`, `15 min`, `1 hour`.
  - Displays a real-time countdown timer while running.
- **Max Clicks**: Stop automatically after reaching a specific number of clicks (e.g. 100, 500, 1000, 5000).

### 5. Cursor Location
- **Current Cursor**: Follows your cursor dynamically wherever you move it.
- **Fixed Coordinates**: Locks clicking to specific $(X, Y)$ screen coordinates.
  - **Interactive Coordinate Picker**: Press `F7` at any time over your target to capture the coordinates instantly.

### 6. Global Hotkeys & Controls
- **Start / Stop Hotkey**: Default `F6` (works globally across all applications and full-screen games).
  - One-click **Change Hotkey** button lets you rebind to any key on your keyboard.
- **Pick Location Hotkey**: Default `F7`.

### 7. Safety & Quality-of-Life
- **Safe Mouse Release**: Mouse buttons are always physically released upon stopping, preventing any stuck cursor states.
- **Emergency Corner Failsafe**: Moving your mouse cursor to the top-left corner $(0, 0)$ immediately halts clicking.
- **Always on Top**: Keep the tool floating over games and other windows.
- **Audible Beep Cue**: Subtle audio feedback when clicking begins and ends.
- **Live Statistics**: Live tracking of elapsed time, remaining countdown, total clicks made, and real-time CPS.

---

## 🚀 How to Run

### Method 1: Standalone Executable (Recommended)
Simply double-click:
```
AutoClicker.exe
```
No Python installation or command line required!

### Method 2: Batch Launcher
Double-click:
```
run_autoclicker.bat
```
This automatically verifies dependencies and launches the app in background window mode (`pythonw`).

### Method 3: Python Terminal
```powershell
pip install -r requirements.txt
python autoclicker.py
```

---

## 🛠 Rebuilding the Executable

If you ever modify `autoclicker.py` and want to recompile the standalone `.exe`:
```powershell
.\build_exe.bat
```
This produces a fresh `AutoClicker.exe` using PyInstaller.

