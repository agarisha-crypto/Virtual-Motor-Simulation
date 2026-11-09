
import numpy as np
import matplotlib.pyplot as plt

# ==================================================
# 28BYJ-48: VERSION 7
# Simplified electromechanical dynamic simulation
# ==================================================

STEPS_PER_REV = 2048

# Command
RPM = 6
COMMAND_STEPS = 2048

# Assumed output-shaft-equivalent parameters.
# These are illustrative, NOT calibrated motor values.
J = 1.0e-4           # Equivalent inertia, kg m^2
B = 5.0e-4           # Viscous damping, N m s/rad
T_MAX = 0.05         # Effective restoring torque, N m
T_LOAD = 0.002       # Constant resisting load torque, N m

# Numerical integration
DT = 0.001           # Time step, seconds
STEP_ANGLE = 2 * np.pi / STEPS_PER_REV

if RPM <= 0 or COMMAND_STEPS <= 0:
    raise ValueError("RPM and commanded steps must be positive.")

STEP_INTERVAL = 60.0 / (RPM * STEPS_PER_REV)
SIM_TIME = COMMAND_STEPS * STEP_INTERVAL
N = int(np.ceil(SIM_TIME / DT)) + 1

time = np.arange(N) * DT
command = np.zeros(N)
angle = np.zeros(N)
velocity = np.zeros(N)
torque = np.zeros(N)

# Generate the commanded step position.
for i, t in enumerate(time):
    completed_steps = min(
        int(t / STEP_INTERVAL),
        COMMAND_STEPS
    )
    command[i] = completed_steps * STEP_ANGLE

# Simulate the rotor response.
for i in range(1, N):
    position_error = command[i - 1] - angle[i - 1]

    # Periodic restoring torque, representing simplified
    # magnetic synchronizing torque.
    synchronizing_torque = T_MAX * np.sin(position_error)

    net_torque = (
        synchronizing_torque
        - B * velocity[i - 1]
        - T_LOAD
    )

    acceleration = net_torque / J

    # Semi-implicit Euler integration
    velocity[i] = velocity[i - 1] + acceleration * DT
    angle[i] = angle[i - 1] + velocity[i] * DT
    torque[i] = synchronizing_torque

# Convert radians to degrees for plots.
command_deg = np.degrees(command)
angle_deg = np.degrees(angle)
error_deg = command_deg - angle_deg
speed_rpm = velocity * 60 / (2 * np.pi)

print("28BYJ-48 Dynamic Model - Version 7")
print("----------------------------------")
print(f"Command RPM:          {RPM}")
print(f"Commanded steps:      {COMMAND_STEPS}")
print(f"Simulation duration:  {SIM_TIME:.3f} s")
print(f"Commanded angle:      {command_deg[-1]:.2f} degrees")
print(f"Simulated angle:      {angle_deg[-1]:.2f} degrees")
print(f"Final simulated RPM:  {speed_rpm[-1]:.2f}")
print(f"Final position error: {error_deg[-1]:.2f} degrees")
print()
print("Reminder: dynamic parameters are assumed, not calibrated.")

# Plot commanded vs simulated position.
plt.figure(figsize=(10, 5))
plt.plot(time, command_deg, label="Commanded position")
plt.plot(time, angle_deg, label="Simulated rotor position")
plt.xlabel("Time (s)")
plt.ylabel("Output-shaft angle (degrees)")
plt.title("Dynamic Motor Model: Position Response")
plt.grid(True)
plt.legend()
plt.tight_layout()

# Plot rotor speed.
plt.figure(figsize=(10, 5))
plt.plot(time, speed_rpm)
plt.axhline(RPM, linestyle="--", label="Command RPM")
plt.xlabel("Time (s)")
plt.ylabel("Simulated shaft speed (RPM)")
plt.title("Dynamic Motor Model: Speed Response")
plt.grid(True)
plt.legend()
plt.tight_layout()

# Plot position tracking error.
plt.figure(figsize=(10, 5))
plt.plot(time, error_deg)
plt.xlabel("Time (s)")
plt.ylabel("Command minus rotor position (degrees)")
plt.title("Dynamic Motor Model: Tracking Error")
plt.grid(True)
plt.tight_layout()

plt.show()
