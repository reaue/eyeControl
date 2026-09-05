# eyeControl
 
A webcam-controlled game inspired by Geometry Dash, where the player uses eye blinks as the main input.

![demo](<Enregistrement 2026-09-01 161351.gif>)

## Try it
 
You can find a video presenting all the features here : [YouTube](https://www.youtube.com/watch?v=K8VPI4zUYcw).
 
## Quick start
 
```bash
pip install mediapipe opencv-python pygame
python EyeDash.py
```

When you start the program, you can choose between two buttons, the first one `YES, CALIBRATE` and the second one `NO, PLAY DIRECTLY`. Calibrate to have a better experience of the program, it's only takes 10 seconds (it's 5 with your both eyes open and then 5 secondes eyes closed). You can choose to play directly, it will use the default thresholds. To try the full experience, a webcam is required but you can play with the space key if you don't have one.

## Controls

| Input | Action |
|---|---|
| Blink one eye | Jump |
| `SPACE` | Jump (keyboard fallback) |
| `R` | Restart after game over |

## Features

What I have implemented :

- Blink detection with a high level of precision in real time (with MediaPipe Face Landmarker);
- A way to distinguish dual blinking vs single eye blinks (left or right);
- An eye aspect ratio (calculated independently for each eye) to otpimise detection;
- This eye aspect ratio (EAR) can be calculated at the start of the program for your own eyes;
- A game inspired by GeometryDash, where you control the player with your blinks (a single-eye blink triggers a jump).

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

I look at the eye aspect ratio which can be calculated as `threshold = open_EAR - k * (open_EAR - close_EAR)`, where `k` can be adjusted between 0.7 and 0.8. So, when during at least two frames, you close one eye and the other not, the program triggers and jump, I optimize this algorithm with a 50 percent ratio, if you keep your eyes closed during more than 50 % of the longest one it's count like a dual blink.

## Game

EyeDash is inspired by Geometry Dash. The player must avoid spikes and use blocks as platforms while obstacles move toward them.

The game includes gravity, jumping, moving obstacles, platforms, collision detection, a game-over state and a restart system.

## Known limitations

- I limited the number of face detecting to one for optimization;
- The angle of your camera can be an issue. Try to put the game screen as close to the camera as possible.
- When you try to close only one eye, the other follows, it's physiological, try to exaggerate your blink if it happends.  

## AI used

- find math formula in research document
- Figma AI to give me inspiration about design

## Credits

Built with [MediaPipe](https://ai.google.dev/edge/mediapipe) (Google), [OpenCV](https://opencv.org/) and [Pygame](https://www.pygame.org/).