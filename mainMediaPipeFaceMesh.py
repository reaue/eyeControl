import mediapipe as mp
import cv2 as cv
import time
import math
# MediaPipe tasks provides prebuilt libraries for different languages like Python, Java, ...
from mediapipe.tasks import python
# MediaPipe Tasks provides three prebuilt libraries: vision, text and audio
from mediapipe.tasks.python import vision


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

CALIB_PHASE = "OPEN"
open_sample1 = []
open_sample2 = []
CALIBRATING_DURATION = 5 # [s]

close_sample1 = []
close_sample2 = []

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
    left_iris = [469, 470, 471, 472]
    right_iris = [474, 475, 476, 477]

    for i in range(4):
        img = cv.line(img, to_px(landmarks, left_iris[i]), to_px(landmarks, left_iris[(i+1) % 4]), red, 1)
        img = cv.line(img, to_px(landmarks, right_iris[i]), to_px(landmarks, right_iris[(i+1) % 4]), red, 1)

    cv.putText(img, "eye_1", (to_px(landmarks, left_iris[1])[0]-10, to_px(landmarks, left_iris[1])[1]-5), cv.FONT_HERSHEY_SIMPLEX, 0.4, red, 2)
    cv.putText(img, "eye_2", (to_px(landmarks, right_iris[1])[0]-10, to_px(landmarks, right_iris[1])[1]-5), cv.FONT_HERSHEY_SIMPLEX, 0.4, red, 2)

    return img


def eye_aspect_ratio(p1, p2, p3, p4, p5, p6):
    return (math.dist(list(p2), list(p6))+(math.dist(list(p3), list(p5))))/(2 * math.dist(list(p1), list(p4)))


need_calibrating = input("Do you want to calibrate your EAR (Y or N) : ")
while need_calibrating != "Y" and need_calibrating != "N":
    need_calibrating = input("You must answer by Y or N : ")
if need_calibrating == "Y":
    APP_STATE = "CALIBRATING" # "CALIBRATING" or "RUNNING"
else:
    APP_STATE = "RUNNING"


# Frame decomposition from a video feed
# Open webcam, the 0 one is the main by default
cap = cv.VideoCapture(0, cv.CAP_DSHOW)

if not cap.isOpened():
    print("Cannot open camera")
    exit()

start_time, calib_start = time.time(), time.time()


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
            if CALIB_PHASE == "OPEN":
                open_sample1.append(EAR_1)
                open_sample2.append(EAR_2)

                remaining = CALIBRATING_DURATION - (time.time() - calib_start)
                cv.putText(frame, f"Keep your eyes open during {max(0, round(remaining, 1))} s.", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, red, 2)

                if remaining <= 0:
                    CALIB_PHASE = "CLOSE"
                    calib_start = time.time()

                    average_open_EAR_1 = sum(open_sample1) / len(open_sample1)
                    average_open_EAR_2 = sum(open_sample2) / len(open_sample2)

            else:
                if EAR_1 <= 0.15: close_sample1.append(EAR_1)
                if EAR_2 <= 0.15: close_sample2.append(EAR_2)

                remaining = CALIBRATING_DURATION - (time.time() - calib_start)
                cv.putText(frame, f"Keep your eyes close during {max(0, round(remaining, 1))} s.", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, red, 2)

                if remaining <= 0:
                    APP_STATE = "RUNNING"

                    average_close_EAR_1 = sum(close_sample1) / len(close_sample1)
                    average_close_EAR_2 = sum(close_sample2) / len(close_sample2)

                    EAR_1_threshold = EAR_threshold_calculate(average_open_EAR_1, average_close_EAR_1)
                    EAR_2_threshold = EAR_threshold_calculate(average_open_EAR_2, average_close_EAR_2)  

                    print(f"EAR_1_threshold = {EAR_1_threshold}, EAR_2_threshold = {EAR_2_threshold}")
                

    else:
        # result.face_landmarks is a list of 478 points of detected visage
        if result.face_landmarks:
            r = result.face_landmarks[0]
            frame = draw_eye(frame, r)

            EAR_1 = eye_aspect_ratio(to_px(r, 33), to_px(r, 160), to_px(r, 158), to_px(r, 133), to_px(r, 153), to_px(r, 144))
            EAR_2 = eye_aspect_ratio(to_px(r, 263), to_px(r, 385), to_px(r, 387), to_px(r, 362), to_px(r, 373), to_px(r, 380))

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

    cv.imshow("frame", frame)
    
    # Press 'q' to quit
    if cv.waitKey(1) == ord('q'):
        break

    
# Release ressources
cap.release()
cv.destroyAllWindows()