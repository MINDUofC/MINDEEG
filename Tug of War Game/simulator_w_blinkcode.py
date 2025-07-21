import pygame
import sys
import time
import os
import json
from PyQt5.QtWidgets import QApplication
# from blink_detector import BlinkDetector  # Commented out for simulation

# Initialize Pygame
pygame.init()

# Screen setup
WIDTH, HEIGHT = 800, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Alpha Rhythms - Tug of War")

# Clock
clock = pygame.time.Clock()
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED   = (255, 0, 0)
BLUE  = (0, 0, 255)
GRAY  = (200, 200, 200)

# Fonts
font = pygame.font.SysFont(None, 48)
small_font = pygame.font.SysFont(None, 32)

# Game variables
rope_x = WIDTH // 2
rope_speed = 5
blink_rope_speed = 15
win_boundary = 100

# Game States
SPLASH = -1
MODE_SELECT = 0
ROUND_SELECT = 5
START = 1
COUNTDOWN = 2
PLAYING = 3
GAME_OVER = 4
BETWEEN_ROUNDS = 6
ROUND_RESULTS = 7
LEADERBOARD = 8
state = SPLASH
mode = None
winner = None
last_round_winner = None
countdown_start = None
splash_start_time = time.time()
between_round_timer = None
fade_displayed = False

# Leaderboard variables
leaderboard_updated = False
leaderboard_file = "leaderboard.txt"
leaderboard = {"Player 1": 0, "Player 2": 0}

# Round mode
round_mode = 1
score_p1 = 0
score_p2 = 0

# Paths
base_path = os.getcwd() + "\\Individual Member Files\\umaiza\\MIND - AR Game\\umaiza\\game_pngs\\"
player1_img = pygame.transform.scale(pygame.image.load(os.path.join(base_path, "player1.png")), (100, 100))
player2_img = pygame.transform.scale(pygame.image.load(os.path.join(base_path, "player2.png")), (100, 100))
rope_img = pygame.transform.scale(pygame.image.load(os.path.join(base_path, "rope.png")), (400, 25))
logo_img = pygame.image.load(os.path.join(base_path, "MIND Background.png")).convert()
logo_img = pygame.transform.scale(logo_img, (WIDTH, HEIGHT))
logo_img.set_alpha(0)

# Blink counters
toggle_p1 = toggle_p2 = blink_p1 = blink_p2 = 0

# Initialize PyQt app
app = QApplication([])

# EEG threads (commented for simulation)
blink_thread_p1 = None
blink_thread_p2 = None

def draw_splash_screen():
    current_time = time.time() - splash_start_time
    fade_duration = 1.0
    full_display_duration = 3.0
    total_duration = fade_duration * 2 + full_display_duration

    if current_time < fade_duration:
        alpha = int(255 * (current_time / fade_duration))
    elif current_time < fade_duration + full_display_duration:
        alpha = 255
    elif current_time < total_duration:
        fade_out_time = current_time - (fade_duration + full_display_duration)
        alpha = int(255 * (1 - (fade_out_time / fade_duration)))
    else:
        return True

    logo_img.set_alpha(alpha)
    screen.fill(WHITE)
    screen.blit(logo_img, (0, 0))
    return False

def draw_mode_select():
    screen.fill(GRAY)
    text = font.render("Select Mode: [1] Blink  [2] Focus", True, BLACK)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - 50))

def draw_round_select():
    screen.fill(GRAY)
    text = font.render("Rounds: [1] Single  [3] Best of 3", True, BLACK)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - 50))

def draw_start_screen():
    screen.fill(GRAY)
    text = font.render("Press SPACE to Start", True, BLACK)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

def draw_countdown():
    screen.fill(WHITE)
    elapsed = int(time.time() - countdown_start)
    count = 3 - elapsed
    if count >= 0:
        text = font.render(str(count+1), True, RED)
        screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

def draw_game(rope_x, tug1, tug2):
    screen.fill(WHITE)
    screen.blit(rope_img, (rope_x - rope_img.get_width()//2, HEIGHT//2 - 12))
    screen.blit(player1_img, (50, HEIGHT//2 - 50))
    screen.blit(player2_img, (WIDTH - 150, HEIGHT//2 - 50))

def draw_round_results():
    screen.fill(WHITE)
    text = font.render(f"{last_round_winner} wins the round!", True, BLUE)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

def draw_between_rounds():
    screen.fill(WHITE)
    text = font.render("Next Round Starting...", True, BLACK)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

def draw_winner_screen(winner):
    screen.fill(WHITE)
    text = font.render(f"{winner} Wins!", True, RED)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

def draw_leaderboard():
    screen.fill(WHITE)
    title = font.render("Leaderboard", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 50))
    y = 150
    for player, score in leaderboard.items():
        text = small_font.render(f"{player}: {score}", True, BLACK)
        screen.blit(text, (WIDTH//2 - text.get_width()//2, y))
        y += 40

def update_leaderboard(winner):
    if winner in leaderboard:
        leaderboard[winner] += 1
    with open(leaderboard_file, "w") as f:
        json.dump(leaderboard, f)

def on_blink(player):
    global rope_x, blink_p1, blink_p2, toggle_p1, toggle_p2
    if state == PLAYING and mode == "blink":
        if player == "Player 1":
            blink_p1 += 1
            rope_x -= blink_rope_speed
            toggle_p2 = 5 if toggle_p2 == 0 else 0
        elif player == "Player 2":
            blink_p2 += 1
            rope_x += blink_rope_speed
            toggle_p1 = 5 if toggle_p1 == 0 else 0

# Game Loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if state == MODE_SELECT:
                if event.key == pygame.K_1:
                    mode = "blink"
                    state = ROUND_SELECT
                elif event.key == pygame.K_2:
                    mode = "focus"
                    state = ROUND_SELECT
                elif event.key == pygame.K_l:
                    state = LEADERBOARD
            elif state == ROUND_SELECT:
                if event.key == pygame.K_1:
                    round_mode = 1
                    score_p1 = score_p2 = 0
                    state = START
                elif event.key == pygame.K_3:
                    round_mode = 3
                    score_p1 = score_p2 = 0
                    state = START
            elif state == START and event.key == pygame.K_SPACE:
                rope_x = WIDTH // 2
                winner = None
                countdown_start = time.time()
                blink_p1 = blink_p2 = toggle_p1 = toggle_p2 = 0
                fade_displayed = False
                leaderboard_updated = False
                state = COUNTDOWN
            elif state == GAME_OVER:
                if event.key == pygame.K_SPACE:
                    state = MODE_SELECT
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
            elif state == PLAYING and mode == "blink":
                if event.key == pygame.K_b:
                    on_blink("Player 1")
                elif event.key == pygame.K_n:
                    on_blink("Player 2")

    keys = pygame.key.get_pressed()

    if state == SPLASH:
        if draw_splash_screen():
            state = MODE_SELECT
    elif state == MODE_SELECT:
        draw_mode_select()
    elif state == ROUND_SELECT:
        draw_round_select()
    elif state == START:
        draw_start_screen()
    elif state == LEADERBOARD:
        draw_leaderboard()
        if keys[pygame.K_ESCAPE]:
            state = MODE_SELECT
    elif state == COUNTDOWN:
        draw_countdown()
        if time.time() - countdown_start >= 3.5:
            state = PLAYING
    elif state == PLAYING:
        tug1 = keys[pygame.K_f] if mode == "focus" else False
        tug2 = keys[pygame.K_j] if mode == "focus" else False
        if tug1:
            rope_x -= rope_speed
        if tug2:
            rope_x += rope_speed
        if rope_x < win_boundary:
            winner = "Player 1"
        elif rope_x > WIDTH - win_boundary:
            winner = "Player 2"
        if winner:
            last_round_winner = winner
            if round_mode == 1:
                state = GAME_OVER
            else:
                score_p1 += winner == "Player 1"
                score_p2 += winner == "Player 2"
                if score_p1 == 2 or score_p2 == 2:
                    state = GAME_OVER
                else:
                    rope_x = WIDTH // 2
                    winner = None
                    countdown_start = time.time()
                    blink_p1 = blink_p2 = toggle_p1 = toggle_p2 = 0
                    fade_displayed = False
                    leaderboard_updated = False
                    between_round_timer = time.time()
                    state = ROUND_RESULTS
        draw_game(rope_x, tug1, tug2)
    elif state == ROUND_RESULTS:
        draw_round_results()
        if time.time() - between_round_timer >= 2:
            fade_displayed = False
            between_round_timer = time.time()
            state = BETWEEN_ROUNDS
    elif state == BETWEEN_ROUNDS:
        draw_between_rounds()
        if time.time() - between_round_timer >= 2:
            countdown_start = time.time()
            fade_displayed = False
            state = COUNTDOWN
    elif state == GAME_OVER:
        draw_winner_screen(winner)
        if not leaderboard_updated:
            update_leaderboard(winner)
            leaderboard_updated = True
        if keys[pygame.K_SPACE]:
            rope_x = WIDTH // 2
            winner = None
            countdown_start = time.time()
            blink_p1 = blink_p2 = toggle_p1 = toggle_p2 = 0
            fade_displayed = False
            leaderboard_updated = False
            state = COUNTDOWN
        elif keys[pygame.K_ESCAPE]:
            state = MODE_SELECT

    app.processEvents()
    clock.tick(FPS)
