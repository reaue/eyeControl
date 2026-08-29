import cv2 as cv
import numpy as np
import os


cv2_base_dir = os.path.dirname(os.path.abspath(cv.__file__))
cascadeEye = cv.CascadeClassifier(os.path.join(cv2_base_dir, 'data/haarcascade_eye.xml'))
cascadeFace = cv.CascadeClassifier(os.path.join(cv2_base_dir, 'data/haarcascade_frontalface_default.xml'))


def faceDetection(img, cascade):
    # Convert to grayscale
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    # Increase the contrast
    gray = cv.equalizeHist(gray)
    
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5, # How many similar rectangle are nearby
        minSize=(30, 30) # Maybe need to be change !!!
    )
    
    return faces


def eyeDetection(img, cascade):
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    gray = cv.equalizeHist(gray)

    eyes, _, levelWeights = cascade.detectMultiScale3(
        gray,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(20, 20), # Maybe need to be change !!!
        outputRejectLevels=True
    )

    return eyes, levelWeights


def drawEye(img, eyes):
    for (x, y, w, h, weight) in eyes:
        cv.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv.putText(img, f"eye {weight:.1f}", (x, y-10), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)


def drawFace(img, faces):
    for (x, y, w, h) in faces:
            cv.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv.putText(img, "face", (x, y-10), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0),2)


# Open webcam, the 0 one is the main by default
cap = cv.VideoCapture(0, cv.CAP_DSHOW)


if not cap.isOpened():
    print("Cannot open camera")
    exit()


while True:
    # Capture frame-by-frame
    # ret is a boolean value that returns true if the frame is available and frame is the image
    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame. Exiting...")
        break

    faces = faceDetection(frame, cascadeFace)

    allEyes = []
    for (x, y, w, h) in faces:
        eyesInFace, weights = eyeDetection(frame[y:y+h, x:x+w], cascadeEye)
        for (ex, ey, ew, eh), weight in zip(eyesInFace, weights):
            allEyes.append((x+ex, y+ey, ew, eh, weight))

    drawFace(frame, faces)
    drawEye(frame, allEyes)

    # Display the frame
    cv.imshow('eyedetect', frame)

    # Press 'q' to quit
    if cv.waitKey(1) == ord('q'):
        break


# Release ressources
cap.release()
cv.destroyAllWindows()