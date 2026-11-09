
import math
import matplotlib.pyplot as plt

# ==========================================
# 28BYJ-48 DIGITAL TWIN - VERSION 5
# ==========================================

STEPS_PER_REV = 2048  # Provisional nominal value

# Measured time for 2048 commanded steps, in seconds
MEASURED_TIME = {
    5: 11.997,
    10: 6.004,
    15: 4.007,
}

# Approximate angle observations, not precise calibration data
MEASURED_ANGLE = {
    5: 357.0,
    10: 359.5,
    15: 360.0,
}


def predict_motor(rpm, steps):
    if rpm <= 0:
        raise ValueError("RPM must be greater than zero.")
    if steps < 0:
        raise ValueError("Steps cannot be negative.")

    # Kinematic prediction
    angle = steps * 360.0 / STEPS_PER_REV
    angular_velocity = 2 * math.pi * rpm / 60
    ideal_time = steps / STEPS_PER_REV * 60 / rpm

    # Use measured timing only at tested RPM values.
    if rpm in MEASURED_TIME:
        predicted_time = (
            steps / STEPS_PER_REV
        ) * MEASURED_TIME[rpm]
        time_basis = f"Measured timing at {rpm} RPM, scaled by steps"
    else:
        predicted_time = ideal_time
        time_basis = "Ideal timing; this RPM has not been calibrated"

    return angle, angular_velocity, ideal_time, predicted_time, time_basis


def show_prediction(rpm, steps):
    angle, omega, ideal_time, predicted_time, basis = (
        predict_motor(rpm, steps)
    )

    print("\n========== DIGITAL TWIN PREDICTION ==========")
    print(f"Commanded RPM:        {rpm}")
    print(f"Commanded steps:      {steps}")
    print(f"Predicted angle:      {angle:.2f} degrees")
    print(f"Angular velocity:     {omega:.4f} rad/s")
    print(f"Ideal movement time:  {ideal_time:.4f} s")
    print(f"Predicted time:       {predicted_time:.4f} s")
    print(f"Timing basis:         {basis}")

    if rpm in MEASURED_ANGLE and steps == STEPS_PER_REV:
        print(
            "Approximate observed angle: "
            f"{MEASURED_ANGLE[rpm]:.2f} degrees"
        )
        print(
            "Note: visual angle measurements are uncertain; "
            "they are not used to alter this prediction."
        )

    print("=============================================")

    return predicted_time, angle


def plot_prediction(rpm, steps):
    predicted_time, predicted_angle = show_prediction(rpm, steps)

    # Ideal constant-speed trajectory.
    times = []
    angles = []

    points = 200
    for i in range(points + 1):
        t = predicted_time * i / points
        theta = predicted_angle * i / points
        times.append(t)
        angles.append(theta)

    plt.figure(figsize=(8, 5))
    plt.plot(times, angles, label="Predicted shaft position")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Shaft angle (degrees)")
    plt.title(f"Digital Twin Prediction: {rpm} RPM, {steps} Steps")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    print("28BYJ-48 Predictive Digital Twin - V5")

    try:
        rpm = int(input("Enter commanded RPM: "))
        steps = int(input("Enter commanded steps: "))

        plot_prediction(rpm, steps)

    except ValueError as error:
        print("Invalid input:", error)
