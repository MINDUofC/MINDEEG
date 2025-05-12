import pygame 
import sys
import time
import os
import json

# Eye Blink game 

# additional features: aesthetics, rope animation, more game related features to make it more complete

# loading screen with mind logo - umaiza
# have players choose their characters - mahika
# leaderboard to keep track of player wins/scores - mahika
# change backgdrop of in-game screen - umaiza
# option to choose single or best of 3 games after selecting the game mode - mahika

# Focus/relaxed mode game
# maybe change graphic but keep logic??

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
MODE_SELECT = 0
START = 1
COUNTDOWN = 2
PLAYING = 3
GAME_OVER = 4
LEADERBOARD = 5
state = MODE_SELECT
mode = None
winner = None
countdown_start = None
round_mode = None
p1_wins = 0
p2_wins = 0

next_round_countdown_start = None
round_count = 0
countdown_duration = 3  # 3 seconds between rounds
round_timer_start_time = None
skip_countdown = False

# Leaderboard variables
leaderboard_updated = False
leaderboard_file = "leaderboard.txt"
leaderboard = {"Player 1": 0, "Player 2": 0} 

# Absolute paths for images
base_path = os.getcwd() + "\\Individual Member Files\\umaiza\\MIND - AR Game\\umaiza\\game_pngs\\"
player1_img = pygame.image.load(os.path.join(base_path, "player1.png"))
player2_img = pygame.image.load(os.path.join(base_path, "player2.png"))
rope_img = pygame.image.load(os.path.join(base_path, "rope.png"))

# Scale images
player1_img = pygame.transform.scale(player1_img, (100, 100))
player2_img = pygame.transform.scale(player2_img, (100, 100))
rope_img = pygame.transform.scale(rope_img, (400, 25))

# Blink counters
blink_p1 = 0
blink_p2 = 0

# Player toggle positions
toggle_p1 = 0
toggle_p2 = 0

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

def draw_text_centered(text, y, font, color=BLACK):
    rendered = font.render(text, True, color)
    screen.blit(rendered, (WIDTH//2 - rendered.get_width()//2, y))

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

def draw_mode_select():
    screen.fill(WHITE)
    title = font.render("Select Game Mode", True, BLACK)
    blink = font.render("1 - Eye Blink Mode (B & N keys)", True, BLACK)
    focus = font.render("2 - Focus Mode (Hold F & J keys)", True, BLACK)
    leaderboard = font.render("L - View Leaderboard", True, BLACK)

    screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
    screen.blit(blink, (WIDTH//2 - blink.get_width()//2, 180))
    screen.blit(focus, (WIDTH//2 - focus.get_width()//2, 230))
    screen.blit(leaderboard, (WIDTH//2 - leaderboard.get_width()//2, 280))

def draw_game_mode_select():
    screen.fill(WHITE)
    title = font.render("Choose Game Format", True, BLACK)
    single = font.render("1 - Single Game", True, BLACK)
    best_of_3 = font.render("2 - Best of 3", True, BLACK)

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))
    screen.blit(single, (WIDTH // 2 - single.get_width() // 2, 180))
    screen.blit(best_of_3, (WIDTH // 2 - best_of_3.get_width() // 2, 230))

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

def draw_meter(rope_x):
    bar_width = 300
    bar_height = 20
    bar_x = WIDTH // 2 - bar_width // 2
    bar_y = 20

    pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_width, bar_height))

    max_offset = WIDTH // 2 - win_boundary
    offset = (rope_x - WIDTH // 2) / max_offset  # Corrected logic for win meter

    offset = max(-1, min(1, offset))
    fill_width = (bar_width // 2) * offset
    fill_color = RED if fill_width < 0 else BLUE

    pygame.draw.rect(screen, fill_color, (WIDTH // 2 + min(0, fill_width), bar_y, abs(fill_width), bar_height))
    pygame.draw.line(screen, BLACK, (WIDTH // 2, bar_y), (WIDTH // 2, bar_y + bar_height), 2)

def draw_game(rope_x, tug1, tug2):
    screen.fill(WHITE)
    draw_meter(rope_x)

    # Draw players
    player2_x = 100 - (5 if tug1 else 0) + toggle_p2  # P2 - Left, toggle added
    player1_x = WIDTH - 200 + (5 if tug2 else 0) + toggle_p1  # P1 - Right, toggle added
    player_y = HEIGHT // 2 - 100

    screen.blit(player2_img, (player2_x, player_y))
    screen.blit(player1_img, (player1_x, player_y))

    # Draw rope
    rope_y = player_y + 60
    rope_rect = rope_img.get_rect(center=(rope_x, rope_y))
    screen.blit(rope_img, rope_rect)

    # Mode label
    mode_label = small_font.render(f"Mode: {'Blink' if mode == 'blink' else 'Focus'}", True, BLACK)
    screen.blit(mode_label, (10, HEIGHT - 30))

    # Player labels
    label_p2 = small_font.render("P2 (N/J)", True, BLUE)
    label_p1 = small_font.render("P1 (B/F)", True, RED)
    screen.blit(label_p2, (player1_x + 25, player_y + 110))  # P2 label under P1
    screen.blit(label_p1, (player2_x + 25, player_y + 110))  # P1 label under P2

    # Blink counters
    if mode == "blink":
        blink_text_p1 = small_font.render(f"P1 Blinks: {blink_p1}", True, RED)
        blink_text_p2 = small_font.render(f"P2 Blinks: {blink_p2}", True, BLUE)
        screen.blit(blink_text_p1, (20, HEIGHT - 60))
        screen.blit(blink_text_p2, (WIDTH - 180, HEIGHT - 60))

def draw_winner_screen(winner):
    screen.fill(WHITE)
    if game_mode == "single":
        draw_text_centered(f"{winner} Wins!", HEIGHT//2 - 60, font)
        draw_text_centered("Press SPACE to play again", HEIGHT//2, font)
        draw_text_centered("Press ESC to quit", HEIGHT//2 + 40, font)
    elif game_mode == "best_of_3":
        if p1_wins == 2 or p2_wins == 2:
            draw_text_centered(f"{winner} Wins the Best of 3!", HEIGHT//2 - 60, font)
            draw_text_centered("Press SPACE to return to main menu", HEIGHT//2, font)
        else:
            draw_text_centered(f"{winner} Wins this round!", HEIGHT//2 - 60, font)
            draw_text_centered("Next round starts in 3 seconds...", HEIGHT//2, font)

def reset_game():
    global rope_x, state, winner, countdown_start, blink_p1, blink_p2, toggle_p1, toggle_p2, leaderboard_updated, skip_countdown
    rope_x = WIDTH // 2
    state = COUNTDOWN
    winner = None
    countdown_start = time.time()
    blink_p1 = 0
    blink_p2 = 0
    toggle_p1 = 0
    toggle_p2 = 0
    leaderboard_updated = False
    if skip_countdown:
        skip_countdown = False
        state = PLAYING
    else:
        countdown_start = time.time()
        state = COUNTDOWN
reset_leaderboard()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if state == MODE_SELECT:
                if event.key == pygame.K_1:
                    mode = "blink"
                    state = "GAME_MODE_SELECT"
                elif event.key == pygame.K_2:
                    mode = "focus"
                    state = "GAME_MODE_SELECT"
                elif event.key == pygame.K_l:
                    state = LEADERBOARD

            elif state == "GAME_MODE_SELECT":
                if event.key == pygame.K_1:
                    game_mode = "single"
                    state = START
                elif event.key == pygame.K_2:
                    game_mode = "best_of_3"
                    p1_wins = 0
                    p2_wins = 0
                    round_count = 0
                    state = START

            elif state == PLAYING and mode == "blink":
                if event.key == pygame.K_b:
                    blink_p1 += 1
                    rope_x -= blink_rope_speed  # Move rope left
                    toggle_p2 = 5 if toggle_p2 == 0 else 0  # Toggle player 2's movement (left)
                elif event.key == pygame.K_n:
                    blink_p2 += 1
                    rope_x += blink_rope_speed  # Move rope right
                    toggle_p1 = 5 if toggle_p1 == 0 else 0  # Toggle player 1's movement (right)

    keys = pygame.key.get_pressed()

    if state == MODE_SELECT:
        draw_mode_select()

    elif state == "GAME_MODE_SELECT":
        draw_game_mode_select()

    elif state == LEADERBOARD:
        draw_leaderboard()
        if keys[pygame.K_ESCAPE]:
            state = MODE_SELECT

    elif state == START:
        draw_start_screen()
        if keys[pygame.K_SPACE]:
            reset_game()

    elif state == COUNTDOWN:
        draw_countdown()
        if time.time() - countdown_start >= 3.5:
            state = PLAYING

    elif state == PLAYING:
        if mode == "focus":
            tug1 = keys[pygame.K_f]
            tug2 = keys[pygame.K_j]

            if tug1:
                rope_x -= rope_speed # Move rope left
                toggle_p2 = 5 if toggle_p2 == 0 else 0  # Toggle player 1's movement (left)
                toggle_p1 = 0 
            if tug2:
                rope_x += rope_speed # Move rope right
                toggle_p2 = 0
                toggle_p1 = 5 if toggle_p1 == 0 else 0  # Toggle player 2's movement (right)
        else:
            tug1 = False
            tug2 = False

        # Win conditions
        if rope_x < win_boundary:
            winner = "Player 1"
            p1_wins += 1
            state = GAME_OVER
        elif rope_x > WIDTH - win_boundary:
            winner = "Player 2"
            p2_wins += 1
            state = GAME_OVER

        draw_game(rope_x, tug1, tug2)

    elif state == GAME_OVER:
        if game_mode == "single":
            draw_winner_screen(winner)
            if not leaderboard_updated:
                update_leaderboard(winner)
                leaderboard_updated = True
            if keys[pygame.K_SPACE]:
                reset_game()
            elif keys[pygame.K_ESCAPE]:
                state = MODE_SELECT

        elif game_mode == "best_of_3":
            if p1_wins == 2 or p2_wins == 2:
                draw_winner_screen(winner)
                if not leaderboard_updated:
                    update_leaderboard("Player 1" if p1_wins == 2 else "Player 2")
                    leaderboard_updated = True
                if keys[pygame.K_SPACE]:
                    state = MODE_SELECT
            else:
                # Still in-between rounds
                if next_round_countdown_start is None:
                    next_round_countdown_start = time.time()

                seconds_left = 3 - int(time.time() - next_round_countdown_start)
                screen.fill(WHITE)
                if seconds_left > 0:
                    draw_text_centered(f"{winner} Wins this round!", HEIGHT//2 - 60, font)
                    draw_text_centered(f"Next round in {seconds_left}...", HEIGHT//2, font)
                else:
                    next_round_countdown_start = None
                    skip_countdown = True
                    reset_game()

    pygame.display.flip()
    clock.tick(FPS)
