"""Conservative screen-space HUD heuristic, not semantic UI segmentation."""
from __future__ import annotations

import cv2
import numpy as np


class UIRegionDetector:
    """Find stable, textured islands while a substantial part of the scene moves.

    Coordinates use 0..65535, with exclusive right/bottom bounds. Detection
    runs on the existing small grayscale guide, never on full-resolution RGB.
    No confidence is learned from a completely static desktop.
    """

    def __init__(self):
        self.previous = None
        self.age = None

    def reset(self):
        self.previous = self.age = None

    def process(self, gray, reset=False):
        if reset or self.previous is None or self.previous.shape != gray.shape:
            self.previous = gray.copy()
            self.age = np.zeros(gray.shape, np.uint8)
            return ()
        difference = cv2.absdiff(gray, self.previous)
        self.previous = gray.copy()
        stable = difference <= 3
        # Changed pixels immediately lose protection, including disappearing HUD.
        self.age[~stable] = 0
        if np.mean(difference > 8) >= .12:
            self.age[stable] = np.minimum(self.age[stable].astype(np.uint16) + 1, 30)
        # Require a stable neighbourhood, not accidental equal-valued pixels.
        trusted = cv2.erode((self.age >= 8).astype(np.uint8), np.ones((3, 3), np.uint8))
        contrast = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        islands = trusted * (contrast >= 24).astype(np.uint8)
        islands = cv2.morphologyEx(islands, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))
        contours, _ = cv2.findContours(islands, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        height, width = gray.shape
        regions = []
        area = 0
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            x, y, w, h = cv2.boundingRect(contour)
            if w < 5 or h < 3 or w * h > width * height * .12:
                continue
            # Reject boxes spanning moving scene between unrelated stable edges.
            if np.mean(self.age[y:y+h, x:x+w] >= 8) < .95:
                continue
            if area + w * h > width * height * .20:
                continue
            area += w * h
            regions.append((x * 65535 // width, y * 65535 // height,
                            (x + w) * 65535 // width, (y + h) * 65535 // height))
            if len(regions) == 32:
                break
        return tuple(regions)
