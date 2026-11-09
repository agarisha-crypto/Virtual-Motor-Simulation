
import math
import matplotlib.pyplot as plt

# ==========================================
# 28BYJ-48 DIGITAL TWIN - VERSION 3
# Time-based simulation
# ==========================================

STEPS_PER_REV = 2048
COMMAND_STEPS = 2048

# Your experimental data:
# RPM: measured movement time in seconds, final angle in degrees
EXPERIMENTS = {
    5:  {"time": 11.997, "angle": 357.0},
    10: {"time": 6.004,  "angle": 359.5},
    15: {"time": 4.007,  "angle": 360.0},
}


def simulate_motor(rpm, measured=False, points=500):
    """Simulate shaft angle over time using a constant-speed profile."""

    ideal_time = (COMMAND_STEPS / STEPS_PER_REV) * 60 / rpm

    if measured:
        duration = EXPERIMENTS[rpm]["time"]
        final_angle = EXPERIMENTS[rpm]["angle"]
    else:
        duration = ideal_time
        final_angle = (
            COMMAND_STEPS / STEPS_PER_REV
        ) * 360

    times = []
    angles = []

    for i in range(points + 1):
        t = duration * i / points

        # Assumed constant-speed motion profile
        angle = final_angle * t / duration

        times.append(t)
        angles.append(angle)

    return times, angles, duration, final_angle


def report(rpm):
    ideal_time = (COMMAND_STEPS / STEPS_PER_REV) * 60 / rpm
    data = EXPERIMENTS[rpm]

    print(f"\n--- {rpm} RPM ---")
    print(f"Ideal time:     {ideal_time:.3f} s")
    print(f"Measured time:  {data['time']:.3f} s")
    print(f"Ideal angle:    360.000 degrees")
    print(f"Measured angle: {data['angle']:.2f} degrees")
    print(f"Angle error:    {data['angle'] - 360:+.2f} degrees")


def plot_simulation(rpm):
    ideal_t, ideal_a, _, _ = simulate_motor(rpm, measured=False)
    real_t, real_a, real_duration, real_angle = simulate_motor(
        rpm, measured=True
    )

    plt.figure(figsize=(9, 5))
    plt.plot(ideal_t, ideal_a, label="Ideal prediction")
    plt.plot(real_t, real_a, "--", label="Measured-endpoint profile")

    plt.scatter(
        [real_duration],
        [real_angle],
        label="Measured final angle"
    )

    plt.xlabel("Time (seconds)")
    plt.ylabel("Shaft angle (degrees)")
    plt.title(f"28BYJ-48 Digital Twin — {rpm} RPM")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()


if __name__ == "__main__":
    for speed in EXPERIMENTS:
        report(speed)
        plot_simulation(speed)

    plt.show()
