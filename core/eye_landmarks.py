import cv2
import time
from collections import deque
import mediapipe as mp
from blink_detector import calculate_ear, LEFT_EYE, RIGHT_EYE

# Contants
EAR_THRESHOLD = 0.21
CONSEC_FRAMES = 2
CONSEC_OPEN = 3


# State
consec_below = 0
consec_above = 0
is_closed = False
blink_count = 0                 # timestamps of completed blinks
blink_times = deque()           # timestamps of completed blinks
WINDOW_SECONDS = 60             # rolling window size

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

capture = cv2.VideoCapture(0)

while capture.isOpened():
    ok, frame = capture.read()
    if not ok:
        break

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    if key == ord('r'):
        blink_count = 0
        blink_times.clear()

    now = time.time()

    # Prune expired blinks (older than 60s) from the left of the deque
    while blink_times and now - blink_times[0] > WINDOW_SECONDS:
        blink_times.popleft()

    blinks_per_min = len(blink_times)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        cv2.putText(frame, "NO FACE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imshow("Eye Landmarks", frame)
        continue

    landmarks = results.multi_face_landmarks[0].landmark
    h, w = frame.shape[:2]

    for eye_indices in [LEFT_EYE, RIGHT_EYE]:
        for idx in eye_indices:
            lm = landmarks[idx]
            x = int(lm.x * w)
            y = int(lm.y * h)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)

    left_ear  = calculate_ear(landmarks, LEFT_EYE, w, h)
    right_ear = calculate_ear(landmarks, RIGHT_EYE, w, h)
    avg_ear   = (left_ear + right_ear) / 2.0

    both_closed = (left_ear < EAR_THRESHOLD) and (right_ear < EAR_THRESHOLD)

    if both_closed:
        consec_above = 0
        consec_below += 1
        if consec_below >= CONSEC_FRAMES:
            is_closed = True
    else:
        consec_above += 1
        if consec_above >= CONSEC_OPEN:
            if is_closed:
                blink_count += 1
                blink_times.append(now)   # record timestamp on completed blink
            is_closed = False
            consec_below = 0

    # Display
    cv2.putText(frame, f"EAR: {avg_ear:.3f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(frame, f"Blinks: {blink_count}", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(frame, f"Rate: {blinks_per_min}/min", (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

    cv2.imshow("Eye Landmarks", frame)
capture.release()
cv2.destroyAllWindows()