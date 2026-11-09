
import math
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation


STEPS_PER_REV = 2048


class VirtualMotor:
    def __init__(self, root):
        self.root = root
        self.root.title("28BYJ-48 Virtual Motor Simulator")
        self.root.geometry("1000x700")

        self.running = False
        self.start_time = 0
        self.duration = 0
        self.rpm = 6
        self.steps = 2048
        self.final_angle = 0
        self.times = []
        self.angles = []

        controls = ttk.Frame(root, padding=10)
        controls.pack(fill="x")

        ttk.Label(controls, text="RPM:").pack(side="left")
        self.rpm_entry = ttk.Entry(controls, width=8)
        self.rpm_entry.insert(0, "6")
        self.rpm_entry.pack(side="left", padx=5)

        ttk.Label(controls, text="Steps:").pack(side="left")
        self.steps_entry = ttk.Entry(controls, width=8)
        self.steps_entry.insert(0, "2048")
        self.steps_entry.pack(side="left", padx=5)

        ttk.Button(
            controls, text="Run Simulation",
            command=self.start
        ).pack(side="left", padx=10)

        ttk.Button(
            controls, text="Reset",
            command=self.reset
        ).pack(side="left")

        self.status = ttk.Label(root, text="Ready")
        self.status.pack(pady=5)

        self.figure = Figure(figsize=(9, 5), dpi=100)

        self.ax_motor = self.figure.add_subplot(121)
        self.ax_graph = self.figure.add_subplot(122)

        self.ax_motor.set_title("Virtual Motor Shaft")
        self.ax_motor.set_xlim(-1.2, 1.2)
        self.ax_motor.set_ylim(-1.2, 1.2)
        self.ax_motor.set_aspect("equal")
        self.ax_motor.grid(True)

        self.shaft_line, = self.ax_motor.plot(
            [0, 1], [0, 0], linewidth=4
        )
        self.ax_motor.plot(0, 0, "o", markersize=8)

        self.ax_graph.set_title("Shaft Angle vs Time")
        self.ax_graph.set_xlabel("Time (s)")
        self.ax_graph.set_ylabel("Angle (degrees)")
        self.ax_graph.grid(True)

        self.graph_line, = self.ax_graph.plot([], [])

        self.canvas = FigureCanvasTkAgg(
            self.figure, master=root
        )
        self.canvas.get_tk_widget().pack(
            fill="both", expand=True
        )

        self.animation = FuncAnimation(
            self.figure,
            self.update,
            interval=30,
            cache_frame_data=False
        )

    def start(self):
        try:
            rpm = float(self.rpm_entry.get())
            steps = int(self.steps_entry.get())

            if rpm <= 0 or steps <= 0:
                raise ValueError

        except ValueError:
            self.status.config(
                text="Enter RPM > 0 and a positive whole step count."
            )
            return

        self.rpm = rpm
        self.steps = steps

        self.final_angle = (
            steps / STEPS_PER_REV
        ) * 360

        self.duration = (
            steps / STEPS_PER_REV
        ) * 60 / rpm

        self.start_time = 0
        self.times = []
        self.angles = []
        self.running = True

        self.status.config(
            text=(
                f"Running: {rpm:g} RPM | {steps} steps | "
                f"Target angle: {self.final_angle:.2f}° | "
                f"Ideal time: {self.duration:.2f} s"
            )
        )

    def reset(self):
        self.running = False
        self.start_time = 0
        self.times = []
        self.angles = []

        self.shaft_line.set_data([0, 1], [0, 0])
        self.graph_line.set_data([], [])

        self.status.config(text="Reset — ready")
        self.canvas.draw_idle()

    def update(self, frame):
        if not self.running:
            return

        # Simulated time advances independently of wall-clock time.
        # This represents ideal constant-speed movement.
        self.start_time += self.duration / 200

        t = min(self.start_time, self.duration)
        fraction = t / self.duration

        angle_deg = self.final_angle * fraction
        angle_rad = math.radians(angle_deg)

        x = math.cos(angle_rad)
        y = math.sin(angle_rad)

        self.shaft_line.set_data([0, x], [0, y])

        self.times.append(t)
        self.angles.append(angle_deg)

        self.graph_line.set_data(self.times, self.angles)
        self.ax_graph.set_xlim(0, max(self.duration, 0.1))
        self.ax_graph.set_ylim(
            0, max(self.final_angle * 1.1, 1)
        )

        self.status.config(
            text=(
                f"RPM: {self.rpm:g} | "
                f"Time: {t:.2f}/{self.duration:.2f} s | "
                f"Angle: {angle_deg:.1f}°"
            )
        )

        if t >= self.duration:
            self.running = False
            self.status.config(
                text=(
                    f"Complete | Final angle: {angle_deg:.1f}° | "
                    f"Elapsed simulated time: {t:.2f} s"
                )
            )

        self.canvas.draw_idle()


if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualMotor(root)
    root.mainloop()
