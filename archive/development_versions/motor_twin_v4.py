
import math
import matplotlib.pyplot as plt

# ==========================================
# 28BYJ-48 DIGITAL TWIN - VERSION 4
# Experiment-informed kinematic model
# ==========================================

NOMINAL_STEPS_PER_REV = 2048

# Provisional calibration based on your approximate
# measurement at 10 RPM (2048 steps -> 359.5 degrees).
CALIBRATED_ANGLE_PER_REV = 359.5

# Measured time for 2048 commanded steps, in seconds.
MEASURED_TIMES = {
    5: 11.997,
    10: 6.004,
    15: 4.007,
}

# Approximate measured endpoint angles.
MEASURED_ANGLES = {
    5: 357.0,
    10: 359.5,
    15: 360.0,
}


def predict_motor(rpm, steps):
    """Predict rotation and duration for a commanded move."""
    if rpm <= 0:
        raise ValueError("RPM must be greater than zero.")
    if steps < 0:
        raise ValueError("Steps must be zero or greater.")

    angle = steps / NOMINAL_STEPS_PER_REV * CALIBRATED_ANGLE_PER_REV

    ideal_time = (
        steps / NOMINAL_STEPS_PER_REV
    ) * (60 / rpm)

    # Scale measured timing proportionally when RPM is known.
    if rpm in MEASURED_TIMES:
        estimated_time = (
            steps / NOMINAL_STEPS_PER_REV
        ) * MEASURED_TIMES[rpm]
        timing_source = "measured timing scaled by step count"
    else:
        estimated_time = ideal_time
        timing_source = "ideal timing; no measured data at this RPM"

    omega = 2 * math.pi * rpm / 60

    return angle, ideal_time, estimated_time, omega, timing_source


def display_prediction(rpm, steps):
    angle, ideal_time, estimated_time, omega, source = predict_motor(
        rpm, steps
    )

    print("\n--- Digital Twin Prediction ---")
    print(f"Commanded RPM:       {rpm}")
    print(f"Commanded steps:     {steps}")
    print(f"Predicted angle:     {angle:.2f} degrees")
    print(f"Ideal time:          {ideal_time:.3f} s")
    print(f"Estimated time:      {estimated_time:.3f} s")
    print(f"Angular velocity:    {omega:.4f} rad/s")
    print(f"Timing basis:        {source}")


def plot_calibration():
    rpms = sorted(MEASURED_TIMES)
    ideal_times = [60 / rpm for rpm in rpms]
    measured_times = [MEASURED_TIMES[rpm] for rpm in rpms]

    plt.figure(figsize=(8, 5))
    plt.plot(rpms, ideal_times, "o-", label="Ideal time")
    plt.plot(rpms, measured_times, "s--", label="Measured time")
    plt.xlabel("RPM")
    plt.ylabel("Time for 2048 steps (seconds)")
    plt.title("28BYJ-48: Timing Calibration")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(8, 5))
    plt.plot(rpms, [360] * len(rpms), "o-", label="Ideal angle")
    plt.plot(
        rpms,
        [MEASURED_ANGLES[rpm] for rpm in rpms],
        "s--",
        label="Approximate measured angle",
    )
    plt.xlabel("RPM")
    plt.ylabel("Rotation angle (degrees)")
    plt.title("28BYJ-48: Endpoint Angle Comparison")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    print("28BYJ-48 Digital Twin V4")
    print("Angle calibration is provisional.")

    # Change these two values to simulate another command.
    rpm_input = 10
    steps_input = 1024

    display_prediction(rpm_input, steps_input)
    plot_calibration()
