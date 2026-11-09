"""
28BYJ-48 Digital Twin — calibrated kinematic prototype
Requirements:
    pip install matplotlib

Run:
    python motor_twin_v9.py

Model scope:
- Uses measured Arduino command durations at 5, 6, 10, and 15 RPM.
- Uses an approximate endpoint calibration of 359.5 degrees per 2048 commanded steps.
- Animates a shaft marker and plots angle versus time.
- This is a kinematic digital-twin prototype, NOT a validated torque, acceleration,
  missed-step, or vibration model. Those effects need separate measurements.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import time

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# User's measured Arduino command durations for 2048 commanded steps.
# Values are averages where available; 6 RPM is based on three identical readings.
MEASURED_MS_PER_2048 = {
    5: 11997,
    6: 9999,
    10: 6004,
    15: 4007,
}

NOMINAL_STEPS_PER_REV = 2048
CALIBRATED_DEG_PER_2048 = 359.5  # approximate visual endpoint estimate
IDEAL_MS_PER_2048 = {
    rpm: 60_000 / rpm for rpm in MEASURED_MS_PER_2048
}


class MotorTwinApp:
    def __init__(self, root):
        self.root = root
        self.root.title("28BYJ-48 Digital Twin — Calibrated Prototype")
        self.root.geometry("1180x760")
        self.root.minsize(960, 650)

        self.running = False
        self.after_id = None
        self.start_wall_time = None
        self.last_elapsed = 0.0
        self.duration = 12.0
        self.total_steps = 2048
        self.rpm = 5
        self.final_angle = 359.5
        self.elapsed = 0.0

        self.rpm_var = tk.StringVar(value="5")
        self.steps_var = tk.StringVar(value="2048")
        self.status_var = tk.StringVar(value="Ready — set the RPM and step count, then press Run.")
        self.time_var = tk.StringVar(value="0.000 / 11.997 s")
        self.angle_var = tk.StringVar(value="0.0°")
        self.duration_var = tk.StringVar(value="11.997 s (measured at 5 RPM)")
        self.model_var = tk.StringVar(value="Calibrated timing")

        self._build_ui()
        self._reset_plot()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(outer, text="Motor controls", padding=10)
        controls.pack(fill="x")

        ttk.Label(controls, text="Speed (RPM):").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        rpm_box = ttk.Combobox(
            controls, textvariable=self.rpm_var,
            values=("2", "5", "6", "10", "15", "20"),
            width=8
        )
        rpm_box.grid(row=0, column=1, sticky="w", padx=(0, 18), pady=4)

        ttk.Label(controls, text="Commanded steps:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(controls, textvariable=self.steps_var, width=10).grid(row=0, column=3, sticky="w", padx=(0, 18), pady=4)

        ttk.Button(controls, text="Run simulation", command=self.run).grid(row=0, column=4, padx=4, pady=4)
        ttk.Button(controls, text="Reset", command=self.reset).grid(row=0, column=5, padx=4, pady=4)

        ttk.Label(controls, text="Predicted duration:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(controls, textvariable=self.duration_var, font=("Segoe UI", 10, "bold")).grid(row=1, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(controls, text="Timing model:").grid(row=1, column=3, sticky="e", pady=4)
        ttk.Label(controls, textvariable=self.model_var).grid(row=1, column=4, columnspan=2, sticky="w", pady=4)

        readouts = ttk.Frame(outer, padding=(0, 10, 0, 6))
        readouts.pack(fill="x")
        ttk.Label(readouts, text="Elapsed:").pack(side="left")
        ttk.Label(readouts, textvariable=self.time_var, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(5, 24))
        ttk.Label(readouts, text="Shaft angle:").pack(side="left")
        ttk.Label(readouts, textvariable=self.angle_var, font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)

        self.fig = Figure(figsize=(10, 5.5), dpi=100, constrained_layout=True)
        self.ax_shaft = self.fig.add_subplot(121)
        self.ax_angle = self.fig.add_subplot(122)
        self.canvas = FigureCanvasTkAgg(self.fig, master=outer)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        ttk.Label(outer, textvariable=self.status_var, wraplength=1100).pack(fill="x", pady=(8, 0))
        note = (
            "Model limitations: endpoint angle is an approximate manual calibration. "
            "Timing measurements describe Arduino command duration, not independently measured shaft motion. "
            "Torque, inertia, acceleration, missed steps and vibration are not yet modeled."
        )
        ttk.Label(outer, text=note, foreground="#555555", wraplength=1100).pack(fill="x", pady=(5, 0))

    def _get_inputs(self):
        try:
            rpm = float(self.rpm_var.get().strip())
            steps = int(self.steps_var.get().strip())
            if rpm <= 0 or steps <= 0:
                raise ValueError
            if steps > 1_000_000:
                raise ValueError
            return rpm, steps
        except ValueError:
            messagebox.showerror("Invalid input", "Enter a positive RPM and a positive whole-number step count (maximum 1,000,000).")
            return None

    def _duration_for(self, rpm, steps):
        # Use measured durations only for the tested speed points and 2048-step scale.
        if rpm in MEASURED_MS_PER_2048:
            duration = (steps / NOMINAL_STEPS_PER_REV) * (MEASURED_MS_PER_2048[int(rpm)] / 1000.0)
            model = f"Measured at {int(rpm)} RPM"
        else:
            duration = (steps / NOMINAL_STEPS_PER_REV) * (60.0 / rpm)
            model = "Ideal estimate (untested RPM)"
        return duration, model

    def _angle_for_steps(self, steps):
        return (steps / NOMINAL_STEPS_PER_REV) * CALIBRATED_DEG_PER_2048

    def _reset_plot(self):
        self.ax_shaft.clear()
        self.ax_shaft.set_title("Virtual output shaft")
        self.ax_shaft.set_aspect("equal", adjustable="box")
        self.ax_shaft.set_xlim(-1.25, 1.25)
        self.ax_shaft.set_ylim(-1.25, 1.25)
        self.ax_shaft.set_xticks([])
        self.ax_shaft.set_yticks([])
        self.ax_shaft.add_patch(matplotlib.patches.Circle((0, 0), 1.0, fill=False, linewidth=1.5))
        self.shaft_line, = self.ax_shaft.plot([0, 0], [0, 1], linewidth=4)
        self.ax_shaft.plot(0, 0, "o", markersize=7)

        self.ax_angle.clear()
        self.ax_angle.set_title("Predicted shaft angle versus time")
        self.ax_angle.set_xlabel("Time (s)")
        self.ax_angle.set_ylabel("Angle (degrees)")
        self.ax_angle.grid(True, alpha=0.3)
        self.angle_line, = self.ax_angle.plot([], [], linewidth=2, label="Predicted angle")
        self.ax_angle.legend(loc="best")
        self.canvas.draw_idle()

    def run(self):
        values = self._get_inputs()
        if values is None:
            return
        self.stop_animation()

        self.rpm, self.total_steps = values
        self.duration, model = self._duration_for(self.rpm, self.total_steps)
        self.final_angle = self._angle_for_steps(self.total_steps)
        self.model_var.set(model)
        self.duration_var.set(f"{self.duration:.3f} s")
        self.elapsed = 0.0
        self.last_elapsed = 0.0
        self._reset_plot()

        # Set plot limits and prepare the predicted curve.
        self.ax_angle.set_xlim(0, max(self.duration, 0.1))
        self.ax_angle.set_ylim(0, max(360, self.final_angle) * 1.08)
        self.ax_angle.plot(
            [0, self.duration], [0, self.final_angle],
            linestyle="--", alpha=0.35, label="Endpoint prediction"
        )
        self.ax_angle.legend(loc="best")
        self.running = True
        self.start_wall_time = time.perf_counter()
        self.status_var.set("Simulation running. The arm follows a calibrated linear angle-versus-time prediction.")
        self._animate()

    def _animate(self):
        if not self.running:
            return
        now = time.perf_counter()
        self.elapsed = min(now - self.start_wall_time, self.duration)
        fraction = 1.0 if self.duration <= 0 else self.elapsed / self.duration
        angle_deg = self.final_angle * fraction
        angle_rad = math.radians(angle_deg)

        # The virtual arm starts vertically and rotates clockwise on screen.
        x = math.sin(angle_rad)
        y = math.cos(angle_rad)
        self.shaft_line.set_data([0, x], [0, y])

        self.angle_line.set_data([0, self.elapsed], [0, angle_deg])
        self.time_var.set(f"{self.elapsed:.3f} / {self.duration:.3f} s")
        self.angle_var.set(f"{angle_deg:.1f}°")
        self.canvas.draw_idle()

        if self.elapsed >= self.duration:
            self.running = False
            self.status_var.set(
                f"Complete: predicted {self.final_angle:.2f}° in {self.duration:.3f} s. "
                "This is a kinematic prediction, not proof of physical shaft accuracy."
            )
        else:
            self.after_id = self.root.after(20, self._animate)

    def stop_animation(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def reset(self):
        self.stop_animation()
        self.elapsed = 0.0
        self.time_var.set("0.000 s")
        self.angle_var.set("0.0°")
        self.duration_var.set("—")
        self.model_var.set("Not running")
        self.status_var.set("Ready — set the RPM and step count, then press Run.")
        self._reset_plot()


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorTwinApp(root)
    root.mainloop()
