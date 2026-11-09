
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation


# ==========================================================
# 28BYJ-48 DIGITAL TWIN V8
# Interactive, simplified electromechanical simulation
# ==========================================================

STEPS_PER_REV = 2048       # Provisional nominal value
STEP_ANGLE = 2 * math.pi / STEPS_PER_REV
DT = 0.001                 # Numerical integration interval (s)

# Illustrative parameters: NOT calibrated motor specifications
DEFAULT_INERTIA = 0.00005
DEFAULT_DAMPING = 0.0005
DEFAULT_TORQUE = 0.034
DEFAULT_LOAD = 0.002


class MotorTwin:
    def __init__(self, root):
        self.root = root
        self.root.title("28BYJ-48 | Digital Twin V8")
        self.root.geometry("1250x850")
        self.root.minsize(1000, 700)

        self.running = False
        self.last_clock = time.perf_counter()
        self.accumulator = 0.0

        self.reset_state()

        # ---------------- Controls ----------------
        controls = ttk.LabelFrame(
            root, text="Simulation Parameters", padding=10
        )
        controls.pack(fill="x", padx=10, pady=(8, 4))

        self.rpm_var = tk.StringVar(value="6")
        self.steps_var = tk.StringVar(value="2048")
        self.load_var = tk.StringVar(value=str(DEFAULT_LOAD))
        self.inertia_var = tk.StringVar(value=str(DEFAULT_INERTIA))
        self.damping_var = tk.StringVar(value=str(DEFAULT_DAMPING))
        self.torque_var = tk.StringVar(value=str(DEFAULT_TORQUE))

        fields = [
            ("Target RPM", self.rpm_var),
            ("Commanded steps", self.steps_var),
            ("Load torque (N m)", self.load_var),
            ("Inertia (kg m²)", self.inertia_var),
            ("Damping", self.damping_var),
            ("Max torque (N m)", self.torque_var),
        ]

        for col, (label, variable) in enumerate(fields):
            ttk.Label(controls, text=label).grid(
                row=0, column=col, padx=5, pady=(0, 4), sticky="w"
            )
            ttk.Entry(
                controls, textvariable=variable, width=14
            ).grid(row=1, column=col, padx=5, sticky="ew")
            controls.columnconfigure(col, weight=1)

        buttons = ttk.Frame(controls)
        buttons.grid(row=2, column=0, columnspan=6, sticky="w", pady=9)

        ttk.Button(buttons, text="Run", command=self.start).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(buttons, text="Stop", command=self.stop).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text="Reset", command=self.reset).pack(
            side="left", padx=6
        )

        self.status = ttk.Label(
            root,
            text="Ready | Parameters are illustrative, not calibrated.",
            padding=(10, 5),
            anchor="w",
        )
        self.status.pack(fill="x", padx=10)

        # ---------------- Plot layout ----------------
        # constrained_layout helps prevent overlapping titles and labels.
        self.fig = Figure(
            figsize=(12, 7.2),
            dpi=100,
            constrained_layout=True,
        )

        grid = self.fig.subplots(2, 2)

        self.ax_motor = grid[0, 0]
        self.ax_position = grid[0, 1]
        self.ax_speed = grid[1, 0]
        self.ax_error = grid[1, 1]

        self.ax_motor.set_title("Virtual Output Shaft", pad=10)
        self.ax_motor.set_xlim(-1.2, 1.2)
        self.ax_motor.set_ylim(-1.2, 1.2)
        self.ax_motor.set_aspect("equal", adjustable="box")
        self.ax_motor.set_xlabel("X")
        self.ax_motor.set_ylabel("Y")
        self.ax_motor.grid(True)

        self.shaft_line, = self.ax_motor.plot(
            [0, 1], [0, 0], linewidth=4
        )
        self.ax_motor.plot(0, 0, "o", markersize=7)

        self.ax_position.set_title(
            "Commanded vs Simulated Position", pad=10
        )
        self.ax_position.set_xlabel("Time (s)", labelpad=6)
        self.ax_position.set_ylabel("Angle (degrees)", labelpad=6)
        self.ax_position.grid(True)

        self.command_line, = self.ax_position.plot(
            [], [], "--", label="Commanded"
        )
        self.position_line, = self.ax_position.plot(
            [], [], label="Simulated shaft"
        )
        self.ax_position.legend(loc="upper left", fontsize=8)

        self.ax_speed.set_title("Simulated Shaft Speed", pad=10)
        self.ax_speed.set_xlabel("Time (s)", labelpad=6)
        self.ax_speed.set_ylabel("Speed (RPM)", labelpad=6)
        self.ax_speed.grid(True)
        self.speed_line, = self.ax_speed.plot([], [])

        self.ax_error.set_title("Position Tracking Error", pad=10)
        self.ax_error.set_xlabel("Time (s)", labelpad=6)
        self.ax_error.set_ylabel("Command − shaft (degrees)", labelpad=6)
        self.ax_error.grid(True)
        self.error_line, = self.ax_error.plot([], [])

        for ax in (
            self.ax_motor,
            self.ax_position,
            self.ax_speed,
            self.ax_error,
        ):
            ax.tick_params(axis="both", labelsize=8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(
            fill="both", expand=True, padx=10, pady=(0, 10)
        )

        # Keep a reference to the animation so Python doesn't discard it.
        self.animation = FuncAnimation(
            self.fig,
            self.update,
            interval=30,
            cache_frame_data=False,
        )

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def reset_state(self):
        self.t = 0.0
        self.theta = 0.0
        self.omega = 0.0
        self.commanded_steps = 0
        self.target_steps = 0
        self.step_interval = 1.0
        self.next_step_time = 0.0

        self.ts = []
        self.command_angles = []
        self.actual_angles = []
        self.speeds = []
        self.errors = []

    def start(self):
        try:
            rpm = float(self.rpm_var.get())
            steps = int(self.steps_var.get())
            load = float(self.load_var.get())
            inertia = float(self.inertia_var.get())
            damping = float(self.damping_var.get())
            torque = float(self.torque_var.get())

            if rpm <= 0 or steps <= 0:
                raise ValueError("RPM and steps must be positive.")
            if load < 0 or inertia <= 0 or damping < 0 or torque <= 0:
                raise ValueError(
                    "Load and damping must be non-negative; "
                    "inertia and torque must be positive."
                )

        except ValueError as error:
            messagebox.showerror("Invalid parameters", str(error))
            return

        self.rpm = rpm
        self.target_steps = steps
        self.load = load
        self.J = inertia
        self.b = damping
        self.Tmax = torque

        self.step_interval = 60.0 / (rpm * STEPS_PER_REV)
        ideal_duration = steps * self.step_interval

        self.reset_state()
        self.target_steps = steps
        self.step_interval = 60.0 / (rpm * STEPS_PER_REV)

        self.running = True
        self.last_clock = time.perf_counter()
        self.accumulator = 0.0

        # Clear old data before a new run.
        self.clear_graphs()
        self.status.config(
            text=(
                f"RUNNING | Target {rpm:g} RPM | {steps} steps | "
                f"Ideal duration {ideal_duration:.2f} s | "
                "Illustrative physics parameters"
            )
        )

    def clear_graphs(self):
        for line in (
            self.command_line,
            self.position_line,
            self.speed_line,
            self.error_line,
        ):
            line.set_data([], [])

        self.shaft_line.set_data([0, 1], [0, 0])
        self.canvas.draw_idle()

    def stop(self):
        self.running = False
        self.status.config(text=f"Paused at simulated time {self.t:.2f} s.")

    def reset(self):
        self.running = False
        self.reset_state()
        self.clear_graphs()
        self.status.config(
            text="Reset | Ready for a new simulation."
        )

    def integrate_one_step(self):
        # Advance the commanded magnetic-field position one step at a time.
        if (
            self.commanded_steps < self.target_steps
            and self.t + 1e-12 >= self.next_step_time
        ):
            self.commanded_steps += 1
            self.next_step_time = (
                self.commanded_steps * self.step_interval
            )

        theta_command = self.commanded_steps * STEP_ANGLE

        # Simplified synchronizing torque.
        position_error = theta_command - self.theta
        sync_torque = self.Tmax * math.sin(position_error)

        # Mechanical equation: J * acceleration = net torque.
        net_torque = (
            sync_torque
            - self.b * self.omega
            - self.load
        )
        acceleration = net_torque / self.J

        # Semi-implicit Euler integration.
        self.omega += acceleration * DT
        self.theta += self.omega * DT
        self.t += DT

        self.ts.append(self.t)
        self.command_angles.append(math.degrees(theta_command))
        self.actual_angles.append(math.degrees(self.theta))
        self.speeds.append(self.omega * 60 / (2 * math.pi))
        self.errors.append(math.degrees(theta_command - self.theta))

    def update(self, _frame):
        if not self.running:
            return

        now = time.perf_counter()
        elapsed = min(now - self.last_clock, 0.1)
        self.last_clock = now
        self.accumulator += elapsed

        # Fixed-step simulation, independent of GUI frame rate.
        iterations = 0
        while self.accumulator >= DT and iterations < 100:
            self.integrate_one_step()
            self.accumulator -= DT
            iterations += 1

        if not self.ts:
            return

        shaft_angle = self.theta
        self.shaft_line.set_data(
            [0, math.cos(shaft_angle)],
            [0, math.sin(shaft_angle)],
        )

        self.command_line.set_data(self.ts, self.command_angles)
        self.position_line.set_data(self.ts, self.actual_angles)
        self.speed_line.set_data(self.ts, self.speeds)
        self.error_line.set_data(self.ts, self.errors)

        for ax in (
            self.ax_position,
            self.ax_speed,
            self.ax_error,
        ):
            ax.relim()
            ax.autoscale_view()

        self.status.config(
            text=(
                f"Time {self.t:.2f} s | "
                f"Position {math.degrees(self.theta):.1f}° | "
                f"Speed {self.omega * 60 / (2 * math.pi):.2f} RPM | "
                f"Steps commanded {self.commanded_steps}/{self.target_steps}"
            )
        )

        ideal_duration = self.target_steps * self.step_interval

        # Allow a short settling period after the final command.
        if (
            self.commanded_steps >= self.target_steps
            and self.t >= ideal_duration + 2.0
        ):
            self.running = False
            self.status.config(
                text=(
                    f"COMPLETE | Final simulated angle "
                    f"{math.degrees(self.theta):.1f}° | "
                    "Model output, not a physical measurement."
                )
            )

        self.canvas.draw_idle()

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorTwin(root)
    root.mainloop()
