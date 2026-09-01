# eyeControl
 
A webcam-controlled game inspired by Geometry Dash, where the player uses eye blinks as the main input.

![demo](<Enregistrement 2026-09-01 161351.gif>)

## Try it
 
No hosted demo — this needs a physical webcam, so it runs locally. See Quick start below.
 
## Quick start
 
```bash
pip install mediapipe opencv-python pygame
python EyeDash.py
```

When the program starts, choose `YES, CALIBRATE` to calibrate the EAR thresholds to your own eyes (10 seconds total: 5s eyes open, 5s eyes closed), or `NO, PLAY DIRECTLY` to use the default thresholds. A webcam is required either way.

## Controls

| Input | Action |
|---|---|
| Blink one eye | Jump |
| `SPACE` | Jump (keyboard fallback) |
| `R` | Restart after game over |

## Features

- Real-time blink detection from a live webcam feed using MediaPipe Face Landmarker (478 facial landmarks).
- Per-eye Eye Aspect Ratio (EAR) computation — detects each eye independently rather than treating "eyes" as one signal.
- Distinguishes dual blinks (both eyes) from single-eye blinks (left or right only).
- Optional personal calibration: 5 seconds eyes-open + 5 seconds eyes-closed to compute a threshold tailored to your own eye shape, instead of a fixed value.
- Pygame-based game with gravity, obstacles, platforms, collision detection and a game-over system.
- Blink-controlled gameplay — a single-eye blink triggers a jump.

## Running it locally

- **Python**: 3.9+ (required by the MediaPipe Tasks API).
- **System dependency**: a working webcam accessible via OpenCV's default backend.
- **Model file**: `face_landmarker.task` must sit at the project root. [Download here](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker#models)
- No environment variables or config files needed.

Start command:
```bash
python EyeDash.py
```

> `cv.VideoCapture(0, cv.CAP_DSHOW)` is Windows-specific. On macOS/Linux, replace it with `cv.VideoCapture(0)`.

## How it works

Blink detection isn't based on a single global threshold — each eye gets its own EAR value and its own calibrated threshold, computed as `threshold = open_EAR - k * (open_EAR - close_EAR)`, with `k = 0.75`.

During the game, the program counts how many frames each eye stays closed. If both eyes are closed for approximately the same duration, the event is classified as a dual blink. Otherwise, it is classified as a single-eye blink.

Single-eye blinks currently trigger the jump. Dual blinks are detected but have no assigned action yet, leaving room for a richer control scheme based on blink patterns.

## Game

EyeDash is inspired by Geometry Dash. The player must avoid spikes and use blocks as platforms while obstacles move toward them.

The game includes gravity, jumping, moving obstacles, platforms, collision detection, a game-over state and a restart system.

## Known limitations

- EAR thresholds are sensitive to lighting and camera angle; recalibrate if detection feels off.
- Only single-face detection is supported (`num_faces=1`); a second face in frame is ignored.
- Default (non-calibrated) thresholds are tuned for one specific person and may not generalize.
- Windows-only webcam backend by default (see note above).

## Credits

Built with [MediaPipe](https://ai.google.dev/edge/mediapipe) (Google), [OpenCV](https://opencv.org/) and [Pygame](https://www.pygame.org/).