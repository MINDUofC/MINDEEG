import pygame
import sys
import time

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
state = MODE_SELECT
mode = None
winner = None
countdown_start = None

# Load images
player1_img = pygame.image.load("umaiza/game_pngs/player1.png")
player2_img = pygame.image.load("umaiza/game_pngs/player2.png")
rope_img = pygame.image.load("umaiza/game_pngs/rope.png")

# Scale images
player1_img = pygame.transform.scale(player1_img, (100, 100))
player2_img = pygame.transform.scale(player2_img, (100, 100))
rope_img = pygame.transform.scale(rope_img, (400, 25))

# Blink counters
blink_p1 = 0
blink_p2 = 0

def draw_mode_select():
    screen.fill(WHITE)
    title = font.render("Select Game Mode", True, BLACK)
    blink = font.render("1 - Eye Blink Mode (B & N keys)", True, BLACK)
    focus = font.render("2 - Focus Mode (Hold F & J keys)", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
    screen.blit(blink, (WIDTH//2 - blink.get_width()//2, 180))
    screen.blit(focus, (WIDTH//2 - focus.get_width()//2, 230))

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
    player2_x = 100 - (5 if tug2 else 0)  # P2 - Left
    player1_x = WIDTH - 200 + (5 if tug1 else 0)  # P1 - Right
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

    # Player labels under character
    label_p2 = small_font.render(f"P2 (N)", True, BLUE)
    label_p1 = small_font.render(f"P1 (B)", True, RED)
    screen.blit(label_p2, (player2_x + 25, player_y + 110))
    screen.blit(label_p1, (player1_x + 25, player_y + 110))

    # Blink counters
    if mode == "blink":
        blink_text_p1 = small_font.render(f"P1 Blinks: {blink_p1}", True, RED)
        blink_text_p2 = small_font.render(f"P2 Blinks: {blink_p2}", True, BLUE)
        screen.blit(blink_text_p1, (20, HEIGHT - 60))
        screen.blit(blink_text_p2, (WIDTH - 180, HEIGHT - 60))

def draw_winner_screen(winner):
    screen.fill(WHITE)
    win_text = font.render(f"{winner} Wins!", True, BLACK)
    replay_text = font.render("Press SPACE to play again", True, BLACK)
    quit_text = font.render("Press ESC to quit", True, BLACK)

    screen.blit(win_text, (WIDTH//2 - win_text.get_width()//2, HEIGHT//2 - 60))
    screen.blit(replay_text, (WIDTH//2 - replay_text.get_width()//2, HEIGHT//2))
    screen.blit(quit_text, (WIDTH//2 - quit_text.get_width()//2, HEIGHT//2 + 40))

def reset_game():
    global rope_x, state, winner, countdown_start, blink_p1, blink_p2
    rope_x = WIDTH // 2
    state = COUNTDOWN
    winner = None
    countdown_start = time.time()
    blink_p1 = 0
    blink_p2 = 0

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if state == MODE_SELECT:
                if event.key == pygame.K_1:
                    mode = "blink"
                    state = START
                elif event.key == pygame.K_2:
                    mode = "focus"
                    state = START
            elif state == PLAYING and mode == "blink":
                if event.key == pygame.K_b:
                    blink_p1 += 1
                    rope_x -= blink_rope_speed  # Move rope left
                elif event.key == pygame.K_n:
                    blink_p2 += 1
                    rope_x += blink_rope_speed  # Move rope right

    keys = pygame.key.get_pressed()

    if state == MODE_SELECT:
        draw_mode_select()

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
                rope_x -= rope_speed
            if tug2:
                rope_x += rope_speed
        else:
            tug1 = False
            tug2 = False

        # Win conditions
        if rope_x < win_boundary:
            winner = "Player 1"
            state = GAME_OVER
        elif rope_x > WIDTH - win_boundary:
            winner = "Player 2"
            state = GAME_OVER

        draw_game(rope_x, tug1, tug2)

    elif state == GAME_OVER:
        draw_winner_screen(winner)
        if keys[pygame.K_SPACE]:
            state = MODE_SELECT
        elif keys[pygame.K_ESCAPE]:
            pygame.quit()
            sys.exit()

    pygame.display.flip()
    clock.tick(FPS)
