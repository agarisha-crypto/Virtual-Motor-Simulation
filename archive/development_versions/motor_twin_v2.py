
import math
import matplotlib.pyplot as plt

# ==========================================
# 28BYJ-48 DIGITAL TWIN - VERSION 2
# ==========================================

STEPS_PER_REV = 2048

# Your experimental data
# Format: RPM: (measured_time_ms, measured_angle_deg)
EXPERIMENTS = {
    5:  (11997, 357.0),
    10: (6004, 359.5),
    15: (4007, 360.0),
}

def predict_motor(rpm, steps=2048):
    """Predict ideal motor movement."""
    angle = steps / STEPS_PER_REV * 360
    angular_velocity = 2 * math.pi * rpm / 60
    duration = steps / STEPS_PER_REV * 60 / rpm

    return angle, angular_velocity, duration


def analyze_experiment(rpm):
    """Compare ideal predictions with measured results."""
    if rpm not in EXPERIMENTS:
        print("No experimental data available for this RPM.")
        return

    measured_ms, measured_angle = EXPERIMENTS[rpm]
    predicted_angle, omega, predicted_s = predict_motor(rpm)

    measured_s = measured_ms / 1000

    time_error = measured_s - predicted_s
    angle_error = measured_angle - predicted_angle

    print(f"\n--- Motor Twin: {rpm} RPM ---")
    print(f"Commanded steps:       {STEPS_PER_REV}")
    print(f"Ideal angle:           {predicted_angle:.2f} degrees")
    print(f"Measured angle:        {measured_angle:.2f} degrees")
    print(f"Angle error:           {angle_error:+.2f} degrees")
    print(f"Ideal movement time:   {predicted_s:.3f} s")
    print(f"Measured time:         {measured_s:.3f} s")
    print(f"Timing error:          {time_error * 1000:+.1f} ms")
    print(f"Ideal angular velocity:{omega:.4f} rad/s")

    if predicted_s > 0:
        print(
            f"Relative timing error: "
            f"{time_error / predicted_s * 100:+.3f}%"
        )


def plot_results():
    rpms = list(EXPERIMENTS.keys())

    ideal_times = []
    measured_times = []
    ideal_angles = []
    measured_angles = []

    for rpm in rpms:
        ideal_angle, _, ideal_time = predict_motor(rpm)
        measured_ms, measured_angle = EXPERIMENTS[rpm]

        ideal_times.append(ideal_time)
        measured_times.append(measured_ms / 1000)
        ideal_angles.append(ideal_angle)
        measured_angles.append(measured_angle)

    # Plot 1: movement time
    plt.figure()
    plt.plot(rpms, ideal_times, "o-", label="Ideal model")
    plt.plot(rpms, measured_times, "s--", label="Measured")
    plt.xlabel("Commanded speed (RPM)")
    plt.ylabel("Time for 2048 steps (seconds)")
    plt.title("Motor Twin: Movement Time")
    plt.grid(True)
    plt.legend()

    # Plot 2: shaft angle
    plt.figure()
    plt.plot(rpms, ideal_angles, "o-", label="Ideal model")
    plt.plot(rpms, measured_angles, "s--", label="Measured")
    plt.xlabel("Commanded speed (RPM)")
    plt.ylabel("Rotation angle (degrees)")
    plt.title("Motor Twin: Rotation Accuracy")
    plt.grid(True)
    plt.legend()

    plt.show()


if __name__ == "__main__":
    print("28BYJ-48 Experimental Digital Twin")
    print("Note: measured angles are preliminary.")

    for speed in EXPERIMENTS:
        analyze_experiment(speed)

    plot_results()
