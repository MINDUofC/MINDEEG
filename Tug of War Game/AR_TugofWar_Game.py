import pygame
import sys
import time
import os
import json

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

def load_leaderboard():
    if not os.path.exists(leaderboard_file):
        return {}
    with open(leaderboard_file, "r") as file:
        return json.load(file)

def save_leaderboard(leaderboard):
    with open(leaderboard_file, "w") as file:
        json.dump(leaderboard, file)

def reset_leaderboard():
    leaderboard = {"Player 1": 0, "Player 2": 0}
    save_leaderboard(leaderboard)
    return leaderboard

def update_leaderboard(winner):
    leaderboard = load_leaderboard()
    if winner not in leaderboard:
        leaderboard[winner] = 0
    leaderboard[winner] += 1
    save_leaderboard(leaderboard)

def draw_leaderboard():
    screen.fill(WHITE)
    title = font.render("Leaderboard", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 50))

    leaderboard = load_leaderboard()
    sorted_scores = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)

    y = 120
    for name, score in sorted_scores:
        entry = small_font.render(f"{name}: {score} wins", True, BLACK)
        screen.blit(entry, (WIDTH//2 - entry.get_width()//2, y))
        y += 40

    back_text = font.render("Press ESC to go back", True, BLACK)
    screen.blit(back_text, (WIDTH//2 - back_text.get_width()//2, HEIGHT - 60))

def fade_in_surface(surface, duration=1.0):
    start_time = time.time()
    fade_overlay = pygame.Surface((WIDTH, HEIGHT))
    fade_overlay.fill(WHITE)
    while True:
        elapsed = time.time() - start_time
        alpha = max(0, 255 - int((elapsed / duration) * 255))
        screen.blit(surface, (0, 0))
        fade_overlay.set_alpha(alpha)
        screen.blit(fade_overlay, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)
        if elapsed >= duration:
            break

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
    screen.fill(WHITE)
    title = font.render("Select Game Mode", True, BLACK)
    blink = font.render("1 - Eye Blink Mode (B & N keys)", True, BLACK)
    focus = font.render("2 - Relax Mode (Hold F & J keys)", True, BLACK)
    leaderboard = font.render("L - View Leaderboard", True, BLACK)

    screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
    screen.blit(blink, (WIDTH//2 - blink.get_width()//2, 180))
    screen.blit(focus, (WIDTH//2 - focus.get_width()//2, 230))
    screen.blit(leaderboard, (WIDTH//2 - leaderboard.get_width()//2, 280))

def draw_round_select():
    screen.fill(WHITE)
    title = font.render("Select Round Type", True, BLACK)
    single = font.render("Press 1 for Single Round", True, BLACK)
    best_of_3 = font.render("Press 3 for Best of 3", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
    screen.blit(single, (WIDTH//2 - single.get_width()//2, 180))
    screen.blit(best_of_3, (WIDTH//2 - best_of_3.get_width()//2, 230))

def draw_start_screen():
    screen.fill(WHITE)
    title = font.render("TUG OF WAR", True, BLACK)
    prompt = font.render("Press SPACE to Start", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 80))
    screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2))

def draw_countdown():
    screen.fill(WHITE)
    seconds_left = 3 - int(time.time() - countdown_start)
    if seconds_left > 0:
        count_text = font.render(str(seconds_left), True, BLACK)
    else:
        count_text = font.render("GO!", True, BLACK)
    screen.blit(count_text, (WIDTH//2 - count_text.get_width()//2, HEIGHT//2))

def draw_game(rope_x, tug1, tug2):
    screen.fill(WHITE)
    draw_meter(rope_x)
    player2_x = 100 - (5 if tug1 else 0) + toggle_p2
    player1_x = WIDTH - 200 + (5 if tug2 else 0) + toggle_p1
    player_y = HEIGHT // 2 - 100
    screen.blit(player2_img, (player2_x, player_y))
    screen.blit(player1_img, (player1_x, player_y))
    rope_rect = rope_img.get_rect(center=(rope_x, player_y + 60))
    screen.blit(rope_img, rope_rect)
    mode_label = small_font.render(f"Mode: {'Blink' if mode == 'blink' else 'Focus'}", True, BLACK)
    screen.blit(mode_label, (10, HEIGHT - 30))
    score_label = small_font.render(f"Score - P1: {score_p1} | P2: {score_p2}", True, BLACK)
    screen.blit(score_label, (WIDTH - 220, HEIGHT - 30))
    screen.blit(small_font.render("P2 (N/J)", True, BLUE), (player1_x + 25, player_y + 110))
    screen.blit(small_font.render("P1 (B/F)", True, RED), (player2_x + 25, player_y + 110))
    if mode == "blink":
        screen.blit(small_font.render(f"P1 Blinks: {blink_p1}", True, RED), (20, HEIGHT - 60))
        screen.blit(small_font.render(f"P2 Blinks: {blink_p2}", True, BLUE), (WIDTH - 180, HEIGHT - 60))

def draw_meter(rope_x):
    bar_width, bar_height = 300, 20
    bar_x, bar_y = WIDTH // 2 - bar_width // 2, 20
    pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_width, bar_height))
    max_offset = WIDTH // 2 - win_boundary
    offset = max(-1, min(1, (rope_x - WIDTH // 2) / max_offset))
    fill_width = (bar_width // 2) * offset
    fill_color = RED if fill_width < 0 else BLUE
    pygame.draw.rect(screen, fill_color, (WIDTH // 2 + min(0, fill_width), bar_y, abs(fill_width), bar_height))
    pygame.draw.line(screen, BLACK, (WIDTH // 2, bar_y), (WIDTH // 2, bar_y + bar_height), 2)

def draw_round_results():
    global fade_displayed
    if not fade_displayed:
        surface = pygame.Surface((WIDTH, HEIGHT))
        surface.fill(WHITE)
        winner_text = f"{last_round_winner} won the last round!"
        surface.blit(font.render(winner_text, True, BLACK), (WIDTH//2 - font.size(winner_text)[0]//2, HEIGHT//2 - 40))
        score = f"Score — P1: {score_p1} | P2: {score_p2}"
        surface.blit(font.render(score, True, BLACK), (WIDTH//2 - font.size(score)[0]//2, HEIGHT//2 + 10))
        fade_in_surface(surface)
        fade_displayed = True

def draw_between_rounds():
    global fade_displayed
    if not fade_displayed:
        surface = pygame.Surface((WIDTH, HEIGHT))
        surface.fill(WHITE)
        current_round = score_p1 + score_p2 + 1
        msg = "Next Round Starting..."
        round_txt = f"Round {current_round} of {round_mode}"
        surface.blit(font.render(msg, True, BLACK), (WIDTH//2 - font.size(msg)[0]//2, HEIGHT//2 - 40))
        surface.blit(font.render(round_txt, True, BLACK), (WIDTH//2 - font.size(round_txt)[0]//2, HEIGHT//2 + 10))
        fade_in_surface(surface)
        fade_displayed = True

def draw_winner_screen(winner):
    surface = pygame.Surface((WIDTH, HEIGHT))
    surface.fill(WHITE)
    surface.blit(font.render(f"{winner} Wins!", True, BLACK), (WIDTH//2 - 100, HEIGHT//2 - 60))
    surface.blit(font.render("Press SPACE to play again", True, BLACK), (WIDTH//2 - 180, HEIGHT//2))
    surface.blit(font.render("Press ESC to quit", True, BLACK), (WIDTH//2 - 140, HEIGHT//2 + 40))
    fade_in_surface(surface)

def reset_game():
    global rope_x, winner, countdown_start, blink_p1, blink_p2, toggle_p1, toggle_p2, fade_displayed, leaderboard_updated
    rope_x = WIDTH // 2
    winner = None
    countdown_start = time.time()
    blink_p1 = blink_p2 = toggle_p1 = toggle_p2 = 0
    fade_displayed = False
    leaderboard_updated = False
reset_leaderboard()

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
                reset_game()
                state = COUNTDOWN
            elif state == PLAYING and mode == "blink":
                if event.key == pygame.K_b:
                    blink_p1 += 1
                    rope_x -= blink_rope_speed
                    toggle_p2 = 5 if toggle_p2 == 0 else 0
                elif event.key == pygame.K_n:
                    blink_p2 += 1
                    rope_x += blink_rope_speed
                    toggle_p1 = 5 if toggle_p1 == 0 else 0
            elif state == GAME_OVER:
                if event.key == pygame.K_SPACE:
                    state = MODE_SELECT
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

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
        if tug1: rope_x -= rope_speed
        if tug2: rope_x += rope_speed
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
                    reset_game()
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
            reset_game()
        elif keys[pygame.K_ESCAPE]:
            state = MODE_SELECT

    pygame.display.flip()
    clock.tick(FPS)
