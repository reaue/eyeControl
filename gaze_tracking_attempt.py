# This version is not enough stable for actual use, I tried several different approaches without seeing any improvement, so I'm abandonig the idea of eye tracking.

import mediapipe as mp
import cv2 as cv
import time
import math
import sys
# MediaPipe tasks provides prebuilt libraries for different languages like Python, Java, ...
from mediapipe.tasks import python
# MediaPipe Tasks provides three prebuilt libraries: vision, text and audio
from mediapipe.tasks.python import vision
from PyQt6.QtWidgets import QApplication, QWidget 
from PyQt6.QtGui import QPainter, QColor, QGuiApplication 
from PyQt6.QtCore import Qt 
import numpy as np
import pyautogui


EAR_1_threshold, EAR_2_threshold = 0.15, 0.15      
RATIO_THRESHOLD = 0.5     # If the secondary eye still close more than 50% the time of the first -> dual
MIN_EVENT_FRAMES = 2      # Skip short blinking during only a frame
red = (0, 0, 255)
k = 0.75

event_active = False
frames_closed_1 = 0
frames_closed_2 = 0

dual_blinking = 0
only_eye1_blinking = 0
only_eye2_blinking = 0

CALIB_PHASE = "EYE_OPEN" # "EYE_OPEN", "EYE_CLOSE" and "EYE_TRACKING"
open_sample1 = []
open_sample2 = []
CALIBRATING_DURATION = 5 # [s]
TRACKING_DURATION = 3 # [s]
point_count = 0
close_sample1 = []
close_sample2 = []

gaze_x = []
gaze_y = []

current_gaze_x = []
current_gaze_y = []

a_x = b_x = a_y = b_y = None

recent_screen_x = []
recent_screen_y = []
SMOOTH_WINDOW = 5


app = QApplication(sys.argv)
screen_size = QGuiApplication.primaryScreen().geometry()

width = screen_size.width()
height = screen_size.height()

point_coord = [
    (width//4, height//4),
    ((width//4)*3, height//4),
    (width//2, height//2),
    (width//4, (height//4)*3),
    ((width//4)*3, (height//4)*3)
]

diameter = 10


class PointOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.current_point = point_coord[0]

        # Full size window, invisible and clickable through
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setBrush(QColor(255, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        x, y = self.current_point
        painter.drawEllipse(x - diameter//2, y - diameter//2, diameter, diameter)

    def set_point(self, coord):
        self.current_point = coord
        self.update()
    

model_path = "face_landmarker.task"

base_options = python.BaseOptions(model_asset_path=model_path)

options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
)

landmarker = vision.FaceLandmarker.create_from_options(options)


def EAR_threshold_calculate(open_EAR, close_EAR):
    threshold = open_EAR - k * (open_EAR - close_EAR) # k is a constant to choose between 0.7, 0.8
    return threshold


def to_px(landmarks, idx):
        p = landmarks[idx]
        return (int(p.x * w), int(p.y * h))


def draw_eye(img, landmarks):
    iris_1 = [469, 470, 471, 472]
    iris_2 = [474, 475, 476, 477]

    for i in range(4):
        img = cv.line(img, to_px(landmarks, iris_1[i]), to_px(landmarks, iris_1[(i+1) % 4]), red, 1)
        img = cv.line(img, to_px(landmarks, iris_2[i]), to_px(landmarks, iris_2[(i+1) % 4]), red, 1)

    cv.putText(img, "eye_1", (to_px(landmarks, iris_1[1])[0]-10, to_px(landmarks, iris_1[1])[1]-5), cv.FONT_HERSHEY_SIMPLEX, 0.4, red, 2)
    cv.putText(img, "eye_2", (to_px(landmarks, iris_2[1])[0]-10, to_px(landmarks, iris_2[1])[1]-5), cv.FONT_HERSHEY_SIMPLEX, 0.4, red, 2)

    return img


def eye_aspect_ratio(p1, p2, p3, p4, p5, p6):
    return (math.dist(list(p2), list(p6))+(math.dist(list(p3), list(p5))))/(2 * math.dist(list(p1), list(p4)))


def gaze(p1, p2, p3): # varies between 0 and 1
    denom = p3 - p2
    if denom == 0:
        return 0.5 # 0.5 is a neutral value
    return (p1 - p2) / denom


need_calibrating_EAR = input("Do you want to calibrate your EAR (Y or N) : ")
while need_calibrating_EAR != "Y" and need_calibrating_EAR != "N":
    need_calibrating_EAR = input("You must answer by Y or N : ")
if need_calibrating_EAR == "Y":
    APP_STATE = "CALIBRATING" # "CALIBRATING" or "RUNNING"
else:
    APP_STATE = "RUNNING"

need_calibrating_tracking = input("Do you want to calibrate eyes tracking (Y or N) : ")
while need_calibrating_tracking != "Y" and need_calibrating_tracking != "N":
    need_calibrating_tracking = input("You must answer by Y or N : ")
if need_calibrating_tracking == "Y":
    TRACKING_CALIB = True
    if APP_STATE == "RUNNING":
        CALIB_PHASE = "EYE_TRACKING"
        APP_STATE = "CALIBRATING"
        timer_tracking = time.time()
else:
    TRACKING_CALIB = False

# Frame decomposition from a video feed
# Open webcam, the 0 one is the main by default
cap = cv.VideoCapture(0, cv.CAP_DSHOW)

if not cap.isOpened():
    print("Cannot open camera")
    exit()

start_time, calib_start = time.time(), time.time()


overlay = PointOverlay()
overlay.show()

while True:
    # Capture frame-by-frame
    # ret is a boolean value that returns true if the frame is available and frame is the image
    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame. Exiting...")
        break

    h, w = frame.shape[:2]

    frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    timestamp_ms = int((time.time() - start_time) * 1000)
    result = landmarker.detect_for_video(mp_image, timestamp_ms)


    if APP_STATE == "CALIBRATING":
        if result.face_landmarks:
            r = result.face_landmarks[0]
            frame = draw_eye(frame, r)

            EAR_1 = eye_aspect_ratio(to_px(r, 33), to_px(r, 160), to_px(r, 158), to_px(r, 133), to_px(r, 153), to_px(r, 144))
            EAR_2 = eye_aspect_ratio(to_px(r, 263), to_px(r, 385), to_px(r, 387), to_px(r, 362), to_px(r, 373), to_px(r, 380))

            if CALIB_PHASE == "EYE_OPEN":
                open_sample1.append(EAR_1)
                open_sample2.append(EAR_2)

                remaining = CALIBRATING_DURATION - (time.time() - calib_start)
                cv.putText(frame, f"Keep your eyes open during {max(0, round(remaining, 1))} s.", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, red, 2)

                if remaining <= 0:
                    CALIB_PHASE = "EYE_CLOSE"
                    calib_start = time.time()

                    if len(open_sample1) == 0 or len(open_sample2) == 0:
                        print("Calibration has failed, there is no face detected. Restart the program !")
                        exit()

                    average_open_EAR_1 = sum(open_sample1) / len(open_sample1)
                    average_open_EAR_2 = sum(open_sample2) / len(open_sample2)

            elif CALIB_PHASE == "EYE_CLOSE":
                if EAR_1 <= 0.15: close_sample1.append(EAR_1)
                if EAR_2 <= 0.15: close_sample2.append(EAR_2)

                remaining = CALIBRATING_DURATION - (time.time() - calib_start)
                cv.putText(frame, f"Keep your eyes close during {max(0, round(remaining, 1))} s.", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, red, 2)

                if remaining <= 0:
                    if TRACKING_CALIB:
                        CALIB_PHASE = "EYE_TRACKING"
                    else:
                        APP_STATE = "RUNNING"

                    if len(close_sample1) == 0 or len(close_sample2) == 0:
                        print("Calibration has failed, there is no face detected or both close eyes. Restart the program !")
                        exit()

                    average_close_EAR_1 = sum(close_sample1) / len(close_sample1)
                    average_close_EAR_2 = sum(close_sample2) / len(close_sample2)

                    EAR_1_threshold = EAR_threshold_calculate(average_open_EAR_1, average_close_EAR_1)
                    EAR_2_threshold = EAR_threshold_calculate(average_open_EAR_2, average_close_EAR_2)  

                    print(f"EAR_1_threshold = {EAR_1_threshold}, EAR_2_threshold = {EAR_2_threshold}")

                    timer_tracking = time.time()

            else:
                if point_count < 5:
                    overlay.set_point(point_coord[point_count])
                    cv.putText(frame, "Look at the red point on your screen", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, red, 2)

                    gx = (gaze(to_px(r, 468)[0], to_px(r, 133)[0], to_px(r, 33)[0]) + gaze(to_px(r, 473)[0], to_px(r, 362)[0], to_px(r, 263)[0])) / 2
                    gy = (gaze(to_px(r, 468)[1], to_px(r, 145)[1], to_px(r, 159)[1]) + gaze(to_px(r, 473)[1], to_px(r, 374)[1], to_px(r, 386)[1])) / 2
                    current_gaze_x.append(gx)
                    current_gaze_y.append(gy)

                if point_count == 0 and (time.time() - timer_tracking) >= CALIBRATING_DURATION:
                    timer_tracking = time.time()
                    point_count += 1
                    gaze_x.append(sum(current_gaze_x) / len(current_gaze_x))
                    gaze_y.append(sum(current_gaze_y) / len(current_gaze_y))
                    current_gaze_x, current_gaze_y = [], []

                elif point_count < 5 and point_count != 0 and (time.time() - timer_tracking) >= TRACKING_DURATION:
                    timer_tracking = time.time()
                    point_count += 1

                    gaze_x.append(sum(current_gaze_x) / len(current_gaze_x))
                    gaze_y.append(sum(current_gaze_y) / len(current_gaze_y))
                    current_gaze_x, current_gaze_y = [], []

                elif point_count == 5:
                    overlay.hide()
                    APP_STATE = "RUNNING"

                    screen_xs = [pc[0] for pc in point_coord]
                    screen_ys = [pc[1] for pc in point_coord]
                    a_x, b_x = np.polyfit(gaze_x, screen_xs, 1)
                    a_y, b_y = np.polyfit(gaze_y, screen_ys, 1)
                    print(f"a_x={a_x}, b_x={b_x}, a_y={a_y}, b_y={b_y}")
                    

    else:
        # result.face_landmarks is a list of 478 points of detected visage
        if result.face_landmarks:
            r = result.face_landmarks[0]
            frame = draw_eye(frame, r)

            EAR_1 = eye_aspect_ratio(to_px(r, 33), to_px(r, 160), to_px(r, 158), to_px(r, 133), to_px(r, 153), to_px(r, 144))
            EAR_2 = eye_aspect_ratio(to_px(r, 263), to_px(r, 385), to_px(r, 387), to_px(r, 362), to_px(r, 373), to_px(r, 380))

            if a_x is not None:
                gx = (gaze(to_px(r, 468)[0], to_px(r, 133)[0], to_px(r, 33)[0]) + gaze(to_px(r, 473)[0], to_px(r, 362)[0], to_px(r, 263)[0])) / 2
                gy = (gaze(to_px(r, 468)[1], to_px(r, 145)[1], to_px(r, 159)[1]) + gaze(to_px(r, 473)[1], to_px(r, 374)[1], to_px(r, 386)[1])) / 2 

                screen_x = a_x * gx + b_x
                screen_y = a_y * gy + b_y

                recent_screen_x.append(screen_x)
                recent_screen_y.append(screen_y)
                if len(recent_screen_x) > SMOOTH_WINDOW:
                    recent_screen_x.pop(0)
                    recent_screen_y.pop(0)

                pyautogui.moveTo(sum(recent_screen_x) / len(recent_screen_x), sum(recent_screen_y) / len(recent_screen_y))

            closed_1 = EAR_1 < EAR_1_threshold
            closed_2 = EAR_2 < EAR_2_threshold

            if closed_1 or closed_2:
                event_active = True
                if closed_1:
                    frames_closed_1 += 1
                if closed_2:
                    frames_closed_2 += 1
            else:
                if event_active:
                    total = max(frames_closed_1, frames_closed_2)
                    if total >= MIN_EVENT_FRAMES:
                        ratio = min(frames_closed_1, frames_closed_2) / total

                        if ratio > RATIO_THRESHOLD:
                            dual_blinking += 1
                        elif frames_closed_1 > frames_closed_2:
                            if only_eye1_blinking == 1 and (time.time() - time_start_eye1) < 1:
                                only_eye1_blinking += 1
                                print("Double1")
                                only_eye1_blinking = 0
                            else:
                                only_eye1_blinking = 1
                            time_start_eye1 = time.time()
                        else:
                            if only_eye2_blinking == 1 and (time.time() - time_start_eye2) < 1:
                                only_eye2_blinking += 1
                                print("Double2")
                                only_eye2_blinking = 0
                            else:
                                only_eye2_blinking = 1
                            time_start_eye2 = time.time()

                        # print("dual_blinking =", dual_blinking, ", only_eye1_blinking =", only_eye1_blinking, ", only_eye2_blinking =", only_eye2_blinking)

                event_active = False
                frames_closed_1 = 0
                frames_closed_2 = 0

    app.processEvents()
    cv.imshow("frame", frame)
    
    # Press 'q' to quit
    if cv.waitKey(1) == ord('q'):
        break

    
# Release ressources
cap.release()
cv.destroyAllWindows()