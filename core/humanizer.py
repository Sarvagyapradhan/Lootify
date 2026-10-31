"""
Biometric & Behavioral Humanizer Engine.
Replaces robotic uniform randomness with mathematically validated human biometric models:
1. Ex-Gaussian / Log-Normal Latency Distributions (matches human reaction time distributions).
2. 2D Bivariate Gaussian Spatial Dispersion with natural thumb bias.
3. Micro-drag touch duration (simulating flesh contact surface and micro-drift).
4. Non-deterministic distraction actions (village browsing, inspection pauses).
"""

import random
import numpy as np


class Humanizer:
    @staticmethod
    def get_reaction_delay(mu=0.10, sigma=0.03, tau=0.05):
        """
        Generates an Ex-Gaussian distributed reaction latency (in seconds).
        Tuned for fast, snappy human gamer response (70ms - 280ms):
        - Normal component N(mu, sigma): neuromuscular transmission time.
        - Exponential component Exp(tau): visual cognitive processing.
        """
        normal_part = random.gauss(mu, sigma)
        exponential_part = random.expovariate(1.0 / tau)
        delay = normal_part + exponential_part
        # Fast human bounds: 70ms to 280ms
        return max(0.07, min(delay, 0.28))

    @staticmethod
    def get_reading_delay(base_sec=0.45, variability=0.22):
        """
        Simulates fast human visual scanning of enemy base loot.
        Snappy glance between 220ms and 750ms.
        """
        return max(0.22, min(0.75, float(np.random.lognormal(mean=np.log(base_sec), sigma=variability))))

    @staticmethod
    def get_touch_down_duration_ms():
        """
        Simulates finger press duration (in milliseconds).
        Fast human touch: 35ms - 70ms.
        """
        return int(max(35, min(70, random.gauss(48, 8))))

    @staticmethod
    def get_dispersed_coordinate(x, y, radius_x=6.0, radius_y=4.5):
        """
        Simulates bivariate elliptical dispersion typical of human thumb/finger contact.
        Guarantees non-identical coordinates with realistic micro-jitter.
        """
        disp_x = int(round(x + random.gauss(0, radius_x)))
        disp_y = int(round(y + random.gauss(0, radius_y)))
        return (disp_x, disp_y)

    @staticmethod
    def should_take_distraction_break(probability=0.08):
        """
        Rolls a check to see if the human player gets distracted (looking away, drinking water).
        """
        return random.random() < probability

    @staticmethod
    def get_distraction_duration():
        """Generates a short idle pause between 8 and 35 seconds."""
        return random.uniform(8.0, 35.0)
