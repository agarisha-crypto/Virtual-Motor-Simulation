"""
28BYJ-48 Digital Twin V10 — literature-informed scenario model

Install:
    python -m pip install matplotlib
Run:
    python motor_twin_v10.py

Important:
This is an engineering approximation, not a manufacturer-certified model.
Published 28BYJ-48 specifications vary substantially between vendors and batches.
The model separates published reference values from tunable assumptions.
Stall is represented by a simplified torque-margin heuristic; vibration is a
qualitative proxy, not a calibrated acceleration/noise prediction.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import time

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# Reference values from commonly circulated 5 V 28BYJ-48 datasheets.
# Treat as indicative; variants differ.
PUBLISHED = {
    "rated_voltage_v": 5.0,
    "phase_resistance_ohm": 50.0,
    "holding_torque_nm": 0.0343,       # 34.3 mN·m (datasheet value)
    "pull_in_torque_nm": 0.0294,       # 300 gf·cm ≈ 29.4 mN·m (reference sheet)
    "in_traction_torque_nm": 0.0343,   # specified at 120 Hz in one common sheet
    "nominal_output_steps_per_rev": 2048,  # full-step convention; gear ratio varies
}

# User's measured Arduino command durations for 2048 commanded steps.
MEASURED_MS_PER_2048 = {5: 11997, 6: 9999, 10: 6004, 15: 4007}
CALIBRATED_DEG_PER_2048 = 359.5

# These are MODEL ASSUMPTIONS, not published manufacturer specifications.
DEFAULT_FRICTION_NM = 0.0020
DEFAULT_LOAD_NM = 0.0020
DEFAULT_AIR_DRAG_NM_AT_15RPM = 0.00005
DEFAULT_INERTIA_KGM2 = 0.00005
DEFAULT_DAMPING_NM_PER_RAD_S = 0.0005


class MotorTwin:
    def __init__(self, root):
        self.root = root
        root.title("28BYJ-48 Digital Twin V10 — Literature-informed")
        root.geometry("1240x820")
        root.minsize(1000, 700)

        self.running = False
        self.after_id = None
        self.start_time = 0.0
        self.last_tick = 0.0
        self.elapsed = 0.0
        self.duration = 12.0
        self.rpm = 5.0
        self.steps = 2048
        self.target_angle = 359.5
        self.angle = 0.0
        self.omega = 0.0
        self.phase_error = 0.0
        self.stalled = False
        self.stall_time = 0.0
        self.history_t, self.history_angle, self.history_vib = [], [], []

        self.rpm_var = tk.StringVar(value="5")
        self.steps_var = tk.StringVar(value="2048")
        self.load_var = tk.DoubleVar(value=DEFAULT_LOAD_NM * 1000)
        self.friction_var = tk.DoubleVar(value=DEFAULT_FRICTION_NM * 1000)
        self.air_var = tk.DoubleVar(value=DEFAULT_AIR_DRAG_NM_AT_15RPM * 1000)
        self.inertia_var = tk.DoubleVar(value=DEFAULT_INERTIA_KGM2 * 1e6)
        self.status_var = tk.StringVar(value="Ready. Published values and assumptions are labeled separately.")
        self.readout_var = tk.StringVar(value="Angle: 0.0° | Speed: 0.0 RPM | Vibration index: 0.00")
        self.duration_var = tk.StringVar(value="—")
        self.margin_var = tk.StringVar(value="Torque margin: —")

        self.build_ui()
        self.draw_static()

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.LabelFrame(outer, text="Command", padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="RPM").grid(row=0, column=0, padx=4, pady=4)
        ttk.Combobox(top, textvariable=self.rpm_var, values=("2", "5", "6", "10", "15", "20", "30"), width=7).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Steps").grid(row=0, column=2, padx=4)
        ttk.Entry(top, textvariable=self.steps_var, width=9).grid(row=0, column=3, padx=4)
        ttk.Button(top, text="Run", command=self.run).grid(row=0, column=4, padx=8)
        ttk.Button(top, text="Reset", command=self.reset).grid(row=0, column=5, padx=4)
        ttk.Label(top, text="Predicted command duration:").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Label(top, textvariable=self.duration_var, font=("Segoe UI", 10, "bold")).grid(row=1, column=2, sticky="w")
        ttk.Label(top, textvariable=self.margin_var).grid(row=1, column=3, columnspan=3, sticky="w")

        param = ttk.LabelFrame(outer, text="Load and loss assumptions (adjustable; not measured)", padding=8)
        param.pack(fill="x", pady=(8, 0))
        self.add_slider(param, "External load torque (mN·m)", self.load_var, 0, 30, 0, 0)
        self.add_slider(param, "Gear/friction loss (mN·m)", self.friction_var, 0, 15, 0, 1)
        self.add_slider(param, "Air drag at 15 RPM (mN·m)", self.air_var, 0, 2, 1, 0)
        self.add_slider(param, "Effective inertia (×10⁻⁶ kg·m²)", self.inertia_var, 5, 200, 1, 1)

        self.fig = Figure(figsize=(10, 5.5), dpi=100, constrained_layout=True)
        self.ax_motor = self.fig.add_subplot(221)
        self.ax_angle = self.fig.add_subplot(222)
        self.ax_torque = self.fig.add_subplot(223)
        self.ax_vib = self.fig.add_subplot(224)
        self.canvas = FigureCanvasTkAgg(self.fig, master=outer)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=(8, 0))
        ttk.Label(outer, textvariable=self.readout_var).pack(anchor="w", pady=(5, 0))
        ttk.Label(outer, textvariable=self.status_var, wraplength=1200).pack(anchor="w")
        ttk.Label(
            outer,
            text=("Scope: literature-informed simplified model. Published reference torque is about 34.3 mN·m, "
                  "but variants differ. Friction/load/inertia controls are scenario assumptions. "
                  "Air drag is expected to be tiny at these speeds. Vibration is an illustrative index, not physical units."),
            foreground="#555555", wraplength=1200
        ).pack(anchor="w", pady=(3, 0))

    def add_slider(self, parent, label, var, lo, hi, col, row):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="ew", padx=6, pady=3)
        parent.columnconfigure(col, weight=1)
        ttk.Label(frame, text=label).pack(anchor="w")
        val_label = ttk.Label(frame, text=f"{var.get():.2f}")
        val_label.pack(anchor="e")
        def update(v):
            val_label.config(text=f"{float(v):.2f}")
        ttk.Scale(frame, variable=var, from_=lo, to=hi, command=update).pack(fill="x")

    def timing(self, rpm, steps):
        if rpm in MEASURED_MS_PER_2048:
            return steps / 2048 * MEASURED_MS_PER_2048[int(rpm)] / 1000, "measured Arduino command timing"
        return steps / 2048 * 60 / rpm, "ideal estimate; RPM not tested"

    def run(self):
        try:
            rpm = float(self.rpm_var.get())
            steps = int(self.steps_var.get())
            if rpm <= 0 or steps <= 0 or steps > 1000000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input error", "Enter a positive RPM and positive whole-number step count.")
            return
        self.stop()
        self.rpm, self.steps = rpm, steps
        self.duration, timing_label = self.timing(rpm, steps)
        self.target_angle = steps / 2048 * CALIBRATED_DEG_PER_2048
        self.elapsed = 0.0
        self.angle = 0.0
        self.omega = 0.0
        self.phase_error = 0.0
        self.stalled = False
        self.stall_time = 0.0
        self.history_t, self.history_angle, self.history_vib = [], [], []
        self.draw_static()
        self.ax_angle.set_xlim(0, max(0.1, self.duration))
        self.ax_angle.set_ylim(0, max(360, self.target_angle) * 1.1)
        self.ax_torque.set_xlim(0, max(0.1, self.duration))
        self.ax_torque.set_ylim(0, 40)
        self.ax_vib.set_xlim(0, max(0.1, self.duration))
        self.ax_vib.set_ylim(0, 1.5)
        self.duration_var.set(f"{self.duration:.3f} s ({timing_label})")
        self.start_time = time.perf_counter()
        self.last_tick = self.start_time
        self.running = True
        self.status_var.set("Running a simplified torque-margin scenario. Treat stall/vibration outputs as qualitative.")
        self._animate()

    def draw_static(self):
        self.ax_motor.clear()
        self.ax_motor.set_title("Virtual output shaft")
        self.ax_motor.set_aspect("equal", adjustable="box")
        self.ax_motor.set_xlim(-1.25, 1.25); self.ax_motor.set_ylim(-1.25, 1.25)
        self.ax_motor.set_xticks([]); self.ax_motor.set_yticks([])
        self.ax_motor.add_patch(matplotlib.patches.Circle((0, 0), 1, fill=False))
        self.arm, = self.ax_motor.plot([0, 0], [0, 1], linewidth=4)
        self.ax_motor.plot(0, 0, "o")
        self.ax_angle.clear()
        self.ax_angle.set_title("Shaft angle")
        self.ax_angle.set_xlabel("Time (s)"); self.ax_angle.set_ylabel("Angle (degrees)")
        self.ax_angle.grid(True, alpha=.25)
        self.angle_plot, = self.ax_angle.plot([], [], label="Angle")
        self.ax_angle.legend()
        self.ax_torque.clear()
        self.ax_torque.set_title("Estimated torque budget")
        self.ax_torque.set_xlabel("Time (s)"); self.ax_torque.set_ylabel("Torque (mN·m)")
        self.ax_torque.grid(True, alpha=.25)
        self.torque_plot, = self.ax_torque.plot([], [], label="Available torque (assumed)")
        self.load_plot, = self.ax_torque.plot([], [], "--", label="Load + loss demand")
        self.ax_torque.legend(fontsize=8)
        self.ax_vib.clear()
        self.ax_vib.set_title("Qualitative vibration / step-loss risk")
        self.ax_vib.set_xlabel("Time (s)"); self.ax_vib.set_ylabel("Index (0–1.5)")
        self.ax_vib.grid(True, alpha=.25)
        self.vib_plot, = self.ax_vib.plot([], [], label="Vibration proxy")
        self.ax_vib.legend(fontsize=8)
        self.canvas.draw_idle()

    def _animate(self):
        if not self.running:
            return
        now = time.perf_counter()
        dt = min(max(now - self.last_tick, 0.001), 0.05)
        self.last_tick = now
        self.elapsed = min(now - self.start_time, self.duration)

        load = self.load_var.get() / 1000.0
        friction = self.friction_var.get() / 1000.0
        air15 = self.air_var.get() / 1000.0
        inertia = max(self.inertia_var.get() * 1e-6, 5e-6)

        # Reference torque envelope: ~34.3 mN·m at modest step rate, reduced
        # heuristically with command rate. This curve is an assumption, not a datasheet curve.
        speed_ratio = max(0.0, self.rpm / 15.0)
        available = 0.0343 / (1.0 + 0.22 * max(0.0, speed_ratio - 1.0))
        air = air15 * (self.rpm / 15.0) ** 2
        demand = load + friction + air
        margin = available - demand
        self.margin_var.set(f"Torque margin: {margin*1000:.1f} mN·m")

        # Commanded ideal position progresses linearly over calibrated command duration.
        target = self.target_angle * (self.elapsed / max(self.duration, 1e-9))
        target_rad = math.radians(target)

        # Qualitative stepper synchronizing torque; this does not reproduce internal gear backlash.
        actual_rad = math.radians(self.angle)
        phase = target_rad - actual_rad
        torque = available * math.sin(phase)
        viscous = DEFAULT_DAMPING_NM_PER_RAD_S * self.omega
        net = torque - math.copysign(demand, self.omega if abs(self.omega) > 1e-5 else 1.0) - viscous
        alpha = net / inertia
        self.omega += alpha * dt
        self.angle += math.degrees(self.omega * dt)

        # Stall heuristic: demand close to/exceeding available torque, or sustained phase lag.
        lag = abs(target - self.angle)
        if demand >= available or lag > 45:
            self.stall_time += dt
        else:
            self.stall_time = max(0.0, self.stall_time - 2 * dt)
        if self.stall_time > 0.35:
            self.stalled = True
        if self.stalled:
            # Represent loss of synchronism by holding position approximately fixed.
            self.angle -= math.degrees(self.omega * dt)
            self.omega *= 0.15

        # Qualitative vibration proxy rises with torque demand ratio and command rate;
        # it is not acceleration RMS and not measured vibration.
        ratio = min(2.0, demand / max(available, 1e-6))
        vib = min(1.5, 0.12 + 0.35 * speed_ratio + 0.8 * ratio + (0.25 if self.stalled else 0))
        self.history_t.append(self.elapsed)
        self.history_angle.append(self.angle)
        self.history_vib.append(vib)

        rad = math.radians(self.angle)
        self.arm.set_data([0, math.sin(rad)], [0, math.cos(rad)])
        self.angle_plot.set_data(self.history_t, self.history_angle)
        self.torque_plot.set_data(self.history_t, [available * 1000] * len(self.history_t))
        self.load_plot.set_data(self.history_t, [demand * 1000] * len(self.history_t))
        self.vib_plot.set_data(self.history_t, self.history_vib)
        self.readout_var.set(f"Angle: {self.angle % 360:.1f}° | Speed: {self.omega * 60 / (2*math.pi):.1f} RPM | Vibration index: {vib:.2f}")
        self.canvas.draw_idle()

        if self.elapsed >= self.duration:
            self.running = False
            if self.stalled:
                self.status_var.set("Simulation ended with a predicted stall under the selected assumptions. This is a heuristic warning, not a guaranteed physical outcome.")
            else:
                self.status_var.set("Simulation ended. The simplified model did not trigger its stall heuristic; this does not guarantee the real motor won't stall.")
        else:
            self.after_id = self.root.after(30, self._animate)

    def stop(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def reset(self):
        self.stop()
        self.draw_static()
        self.duration_var.set("—")
        self.margin_var.set("Torque margin: —")
        self.readout_var.set("Angle: 0.0° | Speed: 0.0 RPM | Vibration index: 0.00")
        self.status_var.set("Ready. Published values and assumptions are labeled separately.")
        self.canvas.draw_idle()


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorTwin(root)
    root.mainloop()
