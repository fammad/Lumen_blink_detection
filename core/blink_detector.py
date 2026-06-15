import numpy as np

#Fixed Reference Points for left and right eye points
LEFT_EYE  = [33,  160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

def calculate_ear(landmarks, eye_indices, image_w, image_h):
    """
    Calculate Eye Aspect Ratio (EAR) for one eye.

    Input:
        landmarks : all 468 MediaPipe face landmarks
        eye_indices : list of 6 int indices for this eye
        image_w: frame width in pixel
        image_h: frame height in pixel

    Output:
        float - EAR value
        eye open ~ 0.25-0.30
        eye closed ~ 0.05-0.08
    """
    points = []
    for idx in eye_indices:
        lm = landmarks[idx]
        x = int(lm.x * image_w)
        y = int(lm.y * image_h)
        points.append(np.array([x, y]))

    A = np.linalg.norm(points[1] - points[5])
    B = np.linalg.norm(points[2] - points[4])
    C = np.linalg.norm(points[0] - points [3])

    ear = (A + B)/(2.0 * C)

    return ear

