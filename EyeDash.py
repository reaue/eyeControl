import mediapipe as mp
import cv2 as cv
import time
import math
import pygame
# MediaPipe tasks provides prebuilt libraries for different languages like Python, Java, ...
from mediapipe.tasks import python
# MediaPipe Tasks provides three prebuilt libraries: vision, text and audio
from mediapipe.tasks.python import vision


FIRST_QUESTION = True
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
time_start_eye1 = 0
time_start_eye2 = 0

CALIB_PHASE = "OPEN"
open_sample1 = []
open_sample2 = []
CALIBRATING_DURATION = 5 # [s]
remaining = CALIBRATING_DURATION

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


pygame.init()
screen = pygame.display.set_mode((874, 431))
pygame.display.set_caption("Game Controlled by eyes blinking !")

font = pygame.font.Font('freesansbold.ttf', 16)
font_title = pygame.font.Font('freesansbold.ttf', 32)
font_subtitle = pygame.font.Font('freesansbold.ttf', 14)
font_question = pygame.font.Font('freesansbold.ttf', 18)
font_description = pygame.font.Font('freesansbold.ttf', 13)
font_button = pygame.font.Font('freesansbold.ttf', 14)
font_footer = pygame.font.Font('freesansbold.ttf', 11)
font_timer = pygame.font.Font('freesansbold.ttf', 48)

BAND_HEIGHT = 16

clock = pygame.time.Clock()
running = True

# UI colours

BACKGROUND = (8, 7, 17)
CARD_BACKGROUND = (18, 15, 36)

CYAN = (0, 240, 255)
CYAN_HOVER = (0, 200, 220)

WHITE = (245, 245, 250)
GREY = (155, 150, 185)
DARK = (8, 7, 17)

PINK = (255, 0, 110)
BORDER = (45, 40, 80)

GROUND_TOP = pygame.Color(CYAN_HOVER)
GROUND_BOTTOM = pygame.Color(0, 0, 0)

# UI rectangles

main_card = pygame.Rect(24, 144, 826, 235)
button_calibrating = pygame.Rect(392, 172, 221, 52)
button_not_calibrating = pygame.Rect(621, 172, 221, 52)

x_player = 100
y_player = 252
size = 48
player_rect = pygame.Rect(x_player, y_player, size, size)

GRAVITY = 1
JUMP_VELOCITY = -17
GROUND_Y = 300

velocity_y = 0

IS_JUMP_TRIGGERED = False
standing_on = None

# Idea : increase the speed during the game to make it harder

class Obstacle():
    def __init__(self, x, y, speed):
        self.x = x
        self.y = y
        self.speed = speed

    def update(self):
        self.x -= self.speed


class Spike(Obstacle):
    def __init__(self, x, y, size, speed=7):
        super().__init__(x, y, speed)
        self.size = size

    def draw(self, screen):
        points = [(self.x, self.y + self.size), (self.x + self.size, self.y + self.size), (self.x + self.size / 2, self.y)]
        pygame.draw.polygon(screen, PINK, points)
        pygame.draw.polygon(screen, WHITE, points, width=3)

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.size, self.size)


class Block(Obstacle):
    def __init__(self, x, y, size, speed=7):
        super().__init__(x, y, speed)
        self.size =size
        self.rect = pygame.Rect(x, y, size, size)

    def update(self):
        super().update()
        self.rect.x = self.x

    def draw(self, screen):
        pygame.draw.rect(screen, PINK, self.rect)
        pygame.draw.rect(screen, WHITE, self.rect, width=3)

obstacles = [Spike(500, GROUND_Y - size, size), Block(800, GROUND_Y - size, size), Block(848, GROUND_Y - size, size), Block(896, GROUND_Y - size, size), Block(944, GROUND_Y - size, size), Block(1088, GROUND_Y - 2 * size, size), Block(1136, GROUND_Y - 2 * size, size)]


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


def draw_closed_eye(surface, center):
    cx, cy = center
    points = []

    # Create a smooth curve
    for x in range(-24, 25):
        y = - 16 * (x / 24) ** 2 + 8
        points.append((cx + x, cy + y))

    pygame.draw.lines( surface, PINK, False, points, width=3)
    pygame.draw.line(surface, PINK, (cx - 13, cy + 2), (cx - 18, cy + 12), width=2)
    pygame.draw.line(surface, PINK, (cx - 5, cy + 7), (cx - 7, cy + 18), width=2)
    pygame.draw.line(surface, PINK, (cx + 5, cy + 7), (cx + 7, cy + 18), width=2)
    pygame.draw.line(surface, PINK, (cx + 13, cy + 2), (cx + 18, cy + 12), width=2)


def draw_ground(display, top=GROUND_TOP, bottom=GROUND_BOTTOM):
    for y in range(0, (431-300), BAND_HEIGHT):
        colour = top.lerp(bottom, y / 431 * 2)
        display.fill(colour, (0, y + 300, 874, 431))


# Frame decomposition from a video feed
# Open webcam, the 0 one is the main by default
cap = cv.VideoCapture(0, cv.CAP_DSHOW)

if not cap.isOpened():
    print("Cannot open camera")
    exit()


while running:
    screen.fill(BACKGROUND)
    if FIRST_QUESTION:
        pygame.draw.rect(screen, CARD_BACKGROUND, main_card, border_radius=22)
        pygame.draw.rect(screen, BORDER, main_card, width=1, border_radius=5)

        eye_center = (332, 84)
        pygame.draw.ellipse(screen, CYAN, (320, 76, 24, 16), width=2)
        pygame.draw.circle(screen, CYAN, eye_center, 4, width=2)

        title = font_title.render("EyeDash", True, WHITE)
        title_rect = title.get_rect(midleft=(356, 84))
        screen.blit(title, title_rect)

        subtitle = font_subtitle.render("Geometry Dash × Eye Blink Control", True, GREY)
        subtitle_rect = subtitle.get_rect(center=(405, 116))
        screen.blit(subtitle, subtitle_rect)

        circle_center = (200, 205)
        pygame.draw.circle(screen, CYAN, circle_center, 35, width=2)
        pygame.draw.circle(screen, (14, 60, 80), circle_center, 33, width=26)
        pygame.draw.circle(screen, CYAN, circle_center, 7, width=2)
        pygame.draw.circle(screen, (0, 0, 0), circle_center, 5)

        mouse_pos = pygame.mouse.get_pos()
        button_active_calibrating = button_calibrating.collidepoint(mouse_pos)

        if button_active_calibrating:
            button_colour_calibrating = CYAN_HOVER
            text_colour_calibrating = DARK
        else:
            button_colour_calibrating = CYAN
            text_colour_calibrating = DARK

        pygame.draw.rect(screen, button_colour_calibrating, button_calibrating, border_radius=15)

        text_callibration_yes = font_button.render("YES, CALIBRATE", True, text_colour_calibrating)
        text_callibration_yes_rect = text_callibration_yes.get_rect(center=button_calibrating.center)
        screen.blit(text_callibration_yes, text_callibration_yes_rect)

        button_active_not_calibrating = button_not_calibrating.collidepoint(mouse_pos)

        if button_active_not_calibrating:
            button_colour_not_calibrating = (25, 22, 45)
        else:
            button_colour_not_calibrating = BACKGROUND

        pygame.draw.rect(screen, button_colour_not_calibrating, button_not_calibrating, border_radius=15)
        pygame.draw.rect(screen, CYAN, button_not_calibrating, width=2, border_radius=15)

        text_callibration_no = font_button.render("NO, PLAY DIRECTLY", True, CYAN)
        text_callibration_no_rect = text_callibration_no.get_rect(center=button_not_calibrating.center)
        screen.blit(text_callibration_no, text_callibration_no_rect)

        question = font_question.render("Would you like to calibrate your EAR?", True, WHITE)
        question_rect = question.get_rect(topleft=(50, 265))
        screen.blit(question, question_rect)

        description_1 = font_description.render("The Eye Aspect Ratio (EAR) measures the", True, GREY)
        description_2 = font_description.render("degree of eye openness to automatically detect blinks.", True, GREY)
        screen.blit(description_1, description_1.get_rect(topleft=(84, 298)))
        screen.blit(description_2, description_2.get_rect(topleft=(50, 316)))

        
    else:
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
                    remaining = max(0, round(remaining))


                    eye_center = (332, 84)
                    pygame.draw.ellipse(screen, CYAN, (320, 76, 24, 16), width=2)
                    pygame.draw.circle(screen, CYAN, eye_center, 4, width=2)

                    title = font_title.render("EAR Calibration", True, WHITE)
                    title_rect = title.get_rect(midleft=(356, 84))
                    screen.blit(title, title_rect)
            
                    subtitle = font_subtitle.render("Step 1 of 2", True, GREY)
                    subtitle_rect = subtitle.get_rect(center=(445, 116))
                    screen.blit(subtitle, subtitle_rect)

                    description_title = font_question.render("Keep your eyes OPEN", True, WHITE)
                    description_title_rect = description_title.get_rect(topleft=(380, 225))
                    screen.blit(description_title, description_title_rect)
            
                    description = font_description.render("during 5 seconds without blinking", True, GREY)
                    screen.blit(description, description.get_rect(topleft=(365, 258)))

                    circle_center = (114, 240)
                    pygame.draw.circle(screen, CYAN_HOVER, circle_center, 90, width=4)
                    pygame.draw.circle(screen, CYAN, circle_center, 55, width=2)
                    pygame.draw.circle(screen, (14, 60, 80), circle_center, 53, width=40)
                    pygame.draw.circle(screen, CYAN, circle_center, 13, width=2)
                    pygame.draw.circle(screen, (0, 0, 0), circle_center, 11)

                    pygame.draw.line(screen, CYAN_HOVER, (24, 350), (850, 350), width=5)

                    text_progress = font_description.render("CALIBRATION IN PRORESS...", True, CYAN)
                    screen.blit(text_progress, text_progress.get_rect(topleft=(354, 368)))

                    timer_center = (770, 240)
                    pygame.draw.circle(screen, CARD_BACKGROUND, timer_center, 40)
                    pygame.draw.circle(screen, GREY, timer_center, 42, width=2)

                    text_timer = font_timer.render(f"{remaining}", True, CYAN)
                    screen.blit(text_timer, text_timer.get_rect(topleft=(757, 217)))

                    if remaining <= 0:
                        CALIB_PHASE = "CLOSE"
                        calib_start = time.time()

                        if len(open_sample1) == 0 or len(open_sample2) == 0:
                            print("Calibration has failed, there is no face detected. Restart the program !")
                            exit()

                        average_open_EAR_1 = sum(open_sample1) / len(open_sample1)
                        average_open_EAR_2 = sum(open_sample2) / len(open_sample2)

                else:
                    if EAR_1 <= 0.15: close_sample1.append(EAR_1)
                    if EAR_2 <= 0.15: close_sample2.append(EAR_2)

                    remaining = CALIBRATING_DURATION - (time.time() - calib_start)
                    remaining = max(0, round(remaining))


                    eye_center = (332, 84)
                    pygame.draw.ellipse(screen, CYAN, (320, 76, 24, 16), width=2)
                    pygame.draw.circle(screen, CYAN, eye_center, 4, width=2)

                    title = font_title.render("EAR Calibration", True, WHITE)
                    title_rect = title.get_rect(midleft=(356, 84))
                    screen.blit(title, title_rect)
            
                    subtitle = font_subtitle.render("Step 2 of 2", True, GREY)
                    subtitle_rect = subtitle.get_rect(center=(445, 116))
                    screen.blit(subtitle, subtitle_rect)

                    description_title = font_question.render("Keep your eyes CLOSE", True, WHITE)
                    description_title_rect = description_title.get_rect(topleft=(380, 225))
                    screen.blit(description_title, description_title_rect)
            
                    description = font_description.render("during 5 seconds in a row", True, GREY)
                    screen.blit(description, description.get_rect(topleft=(394, 258)))

                    circle_center = (114, 240)
                    pygame.draw.circle(screen, PINK, circle_center, 90, width=4)
                    pygame.draw.circle(screen, PINK, circle_center, 55, width=2)
                    pygame.draw.circle(screen, (57, 6, 39), circle_center, 53)
                    draw_closed_eye(screen, circle_center)


                    pygame.draw.line(screen, PINK, (24, 350), (850, 350), width=5)

                    text_progress = font_description.render("CALIBRATION IN PRORESS...", True, PINK)
                    screen.blit(text_progress, text_progress.get_rect(topleft=(354, 368)))

                    timer_center = (770, 240)
                    pygame.draw.circle(screen, CARD_BACKGROUND, timer_center, 40)
                    pygame.draw.circle(screen, GREY, timer_center, 42, width=2)

                    text_timer = font_timer.render(f"{remaining}", True, PINK)
                    screen.blit(text_timer, text_timer.get_rect(topleft=(757, 217)))


                    if remaining <= 0:
                        APP_STATE = "RUNNING"

                        if len(close_sample1) == 0 or len(close_sample2) == 0:
                            print("Calibration has failed, there is no face detected or both close eyes. Restart the program !")
                            exit()

                        average_close_EAR_1 = sum(close_sample1) / len(close_sample1)
                        average_close_EAR_2 = sum(close_sample2) / len(close_sample2)

                        EAR_1_threshold = EAR_threshold_calculate(average_open_EAR_1, average_close_EAR_1)
                        EAR_2_threshold = EAR_threshold_calculate(average_open_EAR_2, average_close_EAR_2)  

                        print(f"EAR_1_threshold = {EAR_1_threshold}, EAR_2_threshold = {EAR_2_threshold}")


        else:
            draw_ground(screen)

            if APP_STATE != "GAME OVER":
                if standing_on is not None:
                    still_supported = (player_rect.right > standing_on.rect.left and
                                        player_rect.left < standing_on.rect.right)
                    if still_supported:
                        y_player = standing_on.rect.top - size
                        velocity_y = 0
                        if IS_JUMP_TRIGGERED:
                            velocity_y = JUMP_VELOCITY
                            standing_on = None
                            IS_JUMP_TRIGGERED = False
                    else:
                        standing_on = None

                if standing_on is None:
                    prev_bottom = y_player + size
                    
                    if IS_JUMP_TRIGGERED and y_player + size == GROUND_Y:
                        velocity_y = JUMP_VELOCITY
                        IS_JUMP_TRIGGERED = False

                    if y_player + size < GROUND_Y or velocity_y != 0:
                        prev_bottom = y_player + size
                        velocity_y += GRAVITY
                        y_player += velocity_y

                        if y_player + size >= GROUND_Y:
                            y_player = GROUND_Y - size
                            velocity_y = 0

                player_rect.y = y_player
                pygame.draw.rect(screen, CYAN, (x_player, y_player, size, size), width=3)

                for obstacle in obstacles:
                    obstacle.update()
                    obstacle.draw(screen)

                    if standing_on is None and player_rect.colliderect(obstacle.rect):
                        if isinstance(obstacle, Spike):
                            APP_STATE = "GAME OVER"
                        elif velocity_y >= 0 and prev_bottom <= obstacle.rect.top + 4:
                            y_player = obstacle.rect.top - size
                            velocity_y = 0
                            player_rect.y = y_player
                            standing_on = obstacle
                        else:
                            APP_STATE = "GAME OVER"

                obstacles = [o for o in obstacles if o.x > -2 * size]

            else:
                for obstacle in obstacles:
                    obstacle.draw(screen) 


            if APP_STATE != "GAME OVER" and result.face_landmarks:
            # result.face_landmarks is a list of 478 points of detected visage
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
                                only_eye1_blinking += 1
                                IS_JUMP_TRIGGERED = True
                            else:
                                only_eye2_blinking += 1
                                IS_JUMP_TRIGGERED = True

                    event_active = False
                    frames_closed_1 = 0
                    frames_closed_2 = 0

            if APP_STATE == "GAME OVER":
                overlay = pygame.Surface((874, 431), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                screen.blit(overlay, (0, 0))

                text_GO = font_title.render("GAME OVER", True, PINK)
                screen.blit(text_GO, text_GO.get_rect(center=(437, 190)))

                text_restart = font_question.render("Press R to restart", True, WHITE)
                screen.blit(text_restart, text_restart.get_rect(center=(437, 240)))

    # Press X on top right of the window to quit the pygame window
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False 
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and button_calibrating.collidepoint(event.pos):
                APP_STATE = "CALIBRATING"
                FIRST_QUESTION = False
                start_time, calib_start = time.time(), time.time()
            elif event.button == 1 and button_not_calibrating.collidepoint(event.pos):
                APP_STATE = "RUNNING"
                FIRST_QUESTION = False
                start_time = time.time()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and (standing_on or player_rect.y == GROUND_Y - size):
                IS_JUMP_TRIGGERED = True
            elif event.key == pygame.K_r:
                y_player = 252
                velocity_y = 0
                IS_JUMP_TRIGGERED = False
                standing_on = None
                obstacles = [Spike(500, GROUND_Y - size, size), Block(800, GROUND_Y - size, size), Block(848, GROUND_Y - size, size), Block(896, GROUND_Y - size, size), Block(944, GROUND_Y - size, size), Block(1088, GROUND_Y - 2 * size, size), Block(1136, GROUND_Y - 2 * size, size)]
                APP_STATE = "RUNNING"

    pygame.display.flip()
    clock.tick(60) # limits FPS to 60

    
# Release ressources
cap.release()
cv.destroyAllWindows()

pygame.quit()