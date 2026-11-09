
import math
import matplotlib.pyplot as plt

# Initial model parameters
STEPS_PER_REV = 2048
rpm = 5
commanded_steps = 2048

# Predicted shaft movement
predicted_angle = (
    commanded_steps / STEPS_PER_REV
) * 360

angular_velocity = 2 * math.pi * rpm / 60

# Ideal time for the commanded movement
predicted_time = (
    commanded_steps / STEPS_PER_REV
) * (60 / rpm)

print("28BYJ-48 Digital Twin")
print("---------------------")
print(f"Commanded RPM: {rpm}")
print(f"Commanded steps: {commanded_steps}")
print(f"Predicted angle: {predicted_angle:.2f} degrees")
print(f"Angular velocity: {angular_velocity:.4f} rad/s")
print(f"Ideal movement time: {predicted_time:.3f} seconds")

# Predicted position over time
time = []
angle = []

for i in range(101):
    t = predicted_time * i / 100
    position = min(
        t / predicted_time, 1
    ) * predicted_angle

    time.append(t)
    angle.append(position)

plt.plot(time, angle, label="Predicted position")
plt.xlabel("Time (seconds)")
plt.ylabel("Shaft angle (degrees)")
plt.title("28BYJ-48 Digital Twin")
plt.grid(True)
plt.legend()
plt.show()
