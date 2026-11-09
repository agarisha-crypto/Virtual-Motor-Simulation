"""
28BYJ-48 Digital Twin V11
A smoother graphical motor simulation using Pygame.

Install:
    python -m pip install pygame matplotlib

Run:
    python motor_twin_v11.py

This is a graphical/kinematic simulation, not a validated electromagnetic model.
The 3D-like motor body, gearbox, shaft, mounting holes, and rotor are drawn in
Pygame. The simulation loop is decoupled from the UI frame rate and uses a
fixed timestep to avoid the lag and jagged animation of the previous version.
"""

import math
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue

try:
    import pygame
except ImportError:
    raise SystemExit("Pygame is required. Install it with: python -m pip install pygame")

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    raise SystemExit("Matplotlib is required. Install it with: python -m pip install matplotlib")


MEASURED_MS_PER_2048 = {5: 11997, 6: 9999, 10: 6004, 15: 4007}
STEPS_PER_REV = 2048
CALIBRATED_DEG_PER_2048 = 359.5


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class MotorRenderer:
    """Draws a stylized 2D/3D-looking geared stepper motor in a Pygame window."""

    def __init__(self, width=700, height=560):
        pygame.init()
        self.width, self.height = width, height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption("28BYJ-48 Graphical Motor View")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 18)
        self.small_font = pygame.font.SysFont("segoeui", 14)
        self.angle_deg = 0.0
        self.rpm = 5.0
        self.load_mnm = 2.0
        self.vibration = 0.0
        self.status = "READY"
        self.keep_open = True

    def draw_text(self, text, pos, color=(235, 239, 245), font=None):
        surface = (font or self.font).render(text, True, color)
        self.screen.blit(surface, pos)

    def draw_motor(self):
        screen = self.screen
        screen.fill((20, 25, 35))
        w, h = screen.get_size()
        scale = min(w / 700, h / 560)
        ox, oy = w * 0.5, h * 0.49

        # Soft floor shadow
        shadow = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 95),
                            (ox - 180 * scale, oy + 105 * scale, 360 * scale, 54 * scale))
        screen.blit(shadow, (0, 0))

        # Motor body: rear side and main metal can
        body = pygame.Rect(ox - 110 * scale, oy - 120 * scale, 220 * scale, 210 * scale)
        pygame.draw.rect(screen, (66, 78, 96), body, border_radius=int(18 * scale))
        pygame.draw.rect(screen, (118, 133, 153), body, width=max(1, int(3 * scale)),
                         border_radius=int(18 * scale))

        # Top cap and four mounting ears
        pygame.draw.rect(screen, (91, 105, 125),
                         (ox - 122 * scale, oy - 128 * scale, 244 * scale, 38 * scale),
                         border_radius=int(8 * scale))
        for dx in (-100, 100):
            for dy in (-112, 72):
                p = (int(ox + dx * scale), int(oy + dy * scale))
                pygame.draw.circle(screen, (151, 162, 177), p, max(3, int(9 * scale)))
                pygame.draw.circle(screen, (35, 42, 53), p, max(2, int(4 * scale)))

        # Gearbox front plate
        pygame.draw.rect(screen, (180, 190, 202),
                         (ox - 94 * scale, oy - 74 * scale, 188 * scale, 136 * scale),
                         border_radius=int(14 * scale))
        pygame.draw.rect(screen, (225, 231, 237),
                         (ox - 94 * scale, oy - 74 * scale, 188 * scale, 136 * scale),
                         width=max(1, int(3 * scale)), border_radius=int(14 * scale))

        # Gearcase rings and stylized screws
        pygame.draw.circle(screen, (125, 137, 152),
                           (int(ox), int(oy - 7 * scale)), int(56 * scale))
        pygame.draw.circle(screen, (226, 231, 236),
                           (int(ox), int(oy - 7 * scale)), int(47 * scale), max(1, int(3 * scale)))
        for dx, dy in [(-76, -56), (76, -56), (-76, 44), (76, 44)]:
            pygame.draw.circle(screen, (96, 106, 120),
                               (int(ox + dx * scale), int(oy + dy * scale)), max(2, int(5 * scale)))

        # Shaft and rotating pointer, drawn over housing
        center = (int(ox), int(oy - 7 * scale))
        shaft_len = 95 * scale
        a = math.radians(self.angle_deg - 90)
        tip = (int(center[0] + math.cos(a) * shaft_len),
               int(center[1] + math.sin(a) * shaft_len))
        pygame.draw.line(screen, (32, 36, 43), center, tip, max(4, int(15 * scale)))
        pygame.draw.line(screen, (222, 229, 236), center, tip, max(2, int(8 * scale)))
        pygame.draw.circle(screen, (245, 165, 55), center, max(5, int(11 * scale)))
        pygame.draw.circle(screen, (255, 221, 143), center, max(2, int(4 * scale)))

        # Status and readings
        self.draw_text("28BYJ-48  |  GRAPHICAL DIGITAL TWIN", (20, 18), (112, 205, 255))
        self.draw_text(f"State: {self.status}", (20, 48))
        self.draw_text(f"Angle: {self.angle_deg % 360:6.1f} deg", (20, 78))
        self.draw_text(f"Command: {self.rpm:g} RPM", (20, 106))
        self.draw_text(f"Load setting: {self.load_mnm:.1f} mN.m", (20, 134))
        self.draw_text(f"Vibration proxy: {self.vibration:.2f}", (20, 162))
        self.draw_text("Stylized illustration — not a photo or CAD-accurate model",
                       (20, h - 30), (180, 190, 204), self.small_font)

    def run(self, shared, stop_event):
        while self.keep_open and not stop_event.is_set():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.keep_open = False
                    stop_event.set()
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

            snap = shared.copy()
            self.angle_deg = snap.get("angle", 0.0)
            self.rpm = snap.get("rpm", 5.0)
            self.load_mnm = snap.get("load_mnm", 2.0)
            self.vibration = snap.get("vibration", 0.0)
            self.status = snap.get("status", "READY")
            self.draw_motor()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


class MotorTwinApp:
    def __init__(self, root):
        self.root = root
        root.title("28BYJ-48 Digital Twin V11 — Motor + Analytics")
        root.geometry("1120x760")
        root.minsize(920, 620)

        self.shared = {
            "angle": 0.0, "rpm": 5.0, "load_mnm": 2.0,
            "vibration": 0.0, "status": "READY",
        }
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.renderer = MotorRenderer()
        self.render_thread = threading.Thread(
            target=self.renderer.run, args=(self.shared, self.stop_event), daemon=True
        )
        self.render_thread.start()

        self.rpm_var = tk.StringVar(value="5")
        self.steps_var = tk.StringVar(value="2048")
        self.load_var = tk.DoubleVar(value=2.0)
        self.friction_var = tk.DoubleVar(value=2.0)
        self.air_var = tk.DoubleVar(value=0.05)
        self.running = False
        self.after_id = None
        self.start = 0.0
        self.last = 0.0
        self.duration = 12.0
        self.angle = 0.0
        self.hist_t, self.hist_a, self.hist_v = [], [], []

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(outer, text="Simulation controls", padding=8)
        controls.pack(fill="x")
        ttk.Label(controls, text="RPM").grid(row=0, column=0, padx=4, pady=4)
        ttk.Combobox(controls, textvariable=self.rpm_var,
                     values=("2", "5", "6", "10", "15", "20"), width=7).grid(row=0, column=1, padx=4)
        ttk.Label(controls, text="Steps").grid(row=0, column=2, padx=4)
        ttk.Entry(controls, textvariable=self.steps_var, width=9).grid(row=0, column=3, padx=4)
        ttk.Button(controls, text="Run", command=self.run_sim).grid(row=0, column=4, padx=6)
        ttk.Button(controls, text="Reset", command=self.reset).grid(row=0, column=5, padx=4)

        for label, var, lo, hi, col in [
            ("External load (mN.m)", self.load_var, 0, 30, 0),
            ("Friction loss (mN.m)", self.friction_var, 0, 15, 1),
            ("Air drag at 15 RPM (mN.m)", self.air_var, 0, 2, 2),
        ]:
            frame = ttk.Frame(controls)
            frame.grid(row=1, column=col * 2, columnspan=2, sticky="ew", padx=5, pady=5)
            ttk.Label(frame, text=label).pack(anchor="w")
            val = ttk.Label(frame, text=f"{var.get():.2f}")
            val.pack(anchor="e")
            def update(v, label_widget=val):
                label_widget.config(text=f"{float(v):.2f}")
            ttk.Scale(frame, variable=var, from_=lo, to=hi, command=update).pack(fill="x")

        self.status_var = tk.StringVar(value="Ready. Run to animate the graphical motor.")
        self.reading_var = tk.StringVar(value="Angle: 0° | Speed: 0 RPM")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))
        ttk.Label(outer, textvariable=self.reading_var, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.fig = Figure(figsize=(9, 4.0), dpi=90, constrained_layout=True)
        self.ax_angle = self.fig.add_subplot(121)
        self.ax_torque = self.fig.add_subplot(122)
        self.canvas = FigureCanvasTkAgg(self.fig, master=outer)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=(8, 0))
        self.draw_plots()

        ttk.Label(
            outer,
            text=("The motor graphic is a stylized drawing, not a photograph or CAD model. "
                  "Timing is calibrated from your Arduino command durations. Load/friction/air drag are adjustable assumptions; "
                  "stall/vibration physics remain simplified."),
            foreground="#555555", wraplength=1080
        ).pack(anchor="w", pady=(5, 0))

    def draw_plots(self):
        self.ax_angle.clear()
        self.ax_angle.set_title("Angle vs time")
        self.ax_angle.set_xlabel("Time (s)")
        self.ax_angle.set_ylabel("Angle (degrees)")
        self.ax_angle.grid(True, alpha=0.25)
        self.angle_line, = self.ax_angle.plot([], [], label="Shaft angle")
        self.ax_angle.legend(fontsize=8)

        self.ax_torque.clear()
        self.ax_torque.set_title("Torque scenario")
        self.ax_torque.set_xlabel("Time (s)")
        self.ax_torque.set_ylabel("Torque (mN.m)")
        self.ax_torque.grid(True, alpha=0.25)
        self.available_line, = self.ax_torque.plot([], [], label="Reference available torque")
        self.demand_line, = self.ax_torque.plot([], [], "--", label="Load + losses")
        self.ax_torque.legend(fontsize=8)
        self.canvas.draw_idle()

    def run_sim(self):
        try:
            rpm = float(self.rpm_var.get())
            steps = int(self.steps_var.get())
            if rpm <= 0 or steps <= 0 or steps > 1000000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input error", "Enter positive RPM and positive whole-number steps.")
            return
        self.stop_sim()
        self.rpm, self.steps = rpm, steps
        self.duration = (
            self.steps / STEPS_PER_REV * MEASURED_MS_PER_2048[int(rpm)] / 1000
            if rpm in MEASURED_MS_PER_2048 else self.steps / STEPS_PER_REV * 60 / rpm
        )
        self.angle = 0.0
        self.start = time.perf_counter()
        self.last = self.start
        self.hist_t, self.hist_a = [], []
        self.draw_plots()
        self.ax_angle.set_xlim(0, max(self.duration, 0.1))
        self.ax_angle.set_ylim(0, max(360, steps / 2048 * CALIBRATED_DEG_PER_2048) * 1.1)
        self.ax_torque.set_xlim(0, max(self.duration, 0.1))
        self.ax_torque.set_ylim(0, 40)
        self.running = True
        self.status_var.set(f"Running — expected command duration {self.duration:.3f} s.")
        self._tick()

    def _tick(self):
        if not self.running:
            return
        now = time.perf_counter()
        elapsed = min(now - self.start, self.duration)
        dt = clamp(now - self.last, 0.0, 0.05)
        self.last = now

        load = self.load_var.get()
        friction = self.friction_var.get()
        air15 = self.air_var.get()
        air = air15 * (self.rpm / 15.0) ** 2
        demand = load + friction + air
        available = 34.3 / (1 + 0.22 * max(0, self.rpm / 15.0 - 1))
        margin = available - demand

        # Kinematic target is intentionally smooth and independent of Tk redraw timing.
        target_angle = (self.steps / STEPS_PER_REV * CALIBRATED_DEG_PER_2048) * elapsed / max(self.duration, 1e-9)
        # Illustrative stall behavior: if assumed torque demand exceeds reference torque,
        # the virtual shaft stops advancing. Not a validated torque-speed motor model.
        if margin < 0:
            target_angle = self.angle
            state = "STALL SCENARIO"
        else:
            state = "RUNNING"
        self.angle = target_angle
        vibration = clamp(0.12 + 0.35 * self.rpm / 15 + 0.8 * demand / max(available, 1e-6), 0, 1.5)

        with self.lock:
            self.shared.update({
                "angle": self.angle, "rpm": self.rpm, "load_mnm": load,
                "vibration": vibration, "status": state
            })

        self.hist_t.append(elapsed)
        self.hist_a.append(self.angle)
        self.angle_line.set_data(self.hist_t, self.hist_a)
        self.available_line.set_data([0, elapsed], [available, available])
        self.demand_line.set_data([0, elapsed], [demand, demand])
        self.reading_var.set(f"Angle: {self.angle % 360:.1f}° | Commanded speed: {self.rpm:.1f} RPM | Torque margin: {margin:.1f} mN·m")
        self.canvas.draw_idle()

        if elapsed >= self.duration:
            self.running = False
            self.status_var.set(f"Finished — model state: {state}. Stall output is a simplified scenario, not a guaranteed physical prediction.")
        else:
            self.after_id = self.root.after(33, self._tick)

    def stop_sim(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def reset(self):
        self.stop_sim()
        self.angle = 0
        with self.lock:
            self.shared.update({"angle": 0, "status": "READY", "vibration": 0})
        self.hist_t, self.hist_a = [], []
        self.draw_plots()
        self.status_var.set("Reset. Ready to run.")

    def close(self):
        self.stop_sim()
        self.stop_event.set()
        self.renderer.keep_open = False
        try:
            pygame.quit()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorTwinApp(root)
    root.mainloop()
