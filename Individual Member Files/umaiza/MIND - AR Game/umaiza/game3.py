import pygame
import sys
import time

# Initialize Pygame
pygame.init()

# Screen setup
WIDTH, HEIGHT = 800, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tug of War")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)

# Fonts
font = pygame.font.SysFont(None, 48)

# Game variables
rope_x = WIDTH // 2
rope_speed = 5
win_boundary = 100

# Clock
clock = pygame.time.Clock()
FPS = 60

# Game States
START = 0
COUNTDOWN = 1
PLAYING = 2
GAME_OVER = 3
state = START
winner = None
countdown_start = None

# Load images
player1_img = pygame.image.load("umaiza/game_pngs/player1.png")  # Red - Right
player2_img = pygame.image.load("umaiza/game_pngs/player2.png")  # Blue - Left
rope_img = pygame.image.load("umaiza/game_pngs/rope.png")

# Scale images
player1_img = pygame.transform.scale(player1_img, (100, 100))
player2_img = pygame.transform.scale(player2_img, (100, 100))
rope_img = pygame.transform.scale(rope_img, (400, 25))  # Shorter rope

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

    # Flipped logic: -1 = Player 1 (Red), +1 = Player 2 (Blue)
    max_offset = WIDTH // 2 - win_boundary
    offset = (WIDTH // 2 - rope_x) / max_offset
    offset = max(-1, min(1, offset))

    fill_width = (bar_width // 2) * offset
    fill_color = RED if fill_width < 0 else BLUE

    pygame.draw.rect(screen, fill_color, (WIDTH // 2, bar_y, fill_width, bar_height))
    pygame.draw.line(screen, BLACK, (WIDTH // 2, bar_y), (WIDTH // 2, bar_y + bar_height), 2)

def draw_game(rope_x, tug1, tug2):
    screen.fill(WHITE)
    draw_meter(rope_x)

    player2_x = 100 - (5 if tug2 else 0)             # Blue - left
    player1_x = WIDTH - 200 + (5 if tug1 else 0)     # Red - right
    player_y = HEIGHT // 2 - 100

    screen.blit(player2_img, (player2_x, player_y))
    screen.blit(player1_img, (player1_x, player_y))

    rope_y = player_y + 60  # Align with hands
    rope_rect = rope_img.get_rect(center=(rope_x, rope_y))
    screen.blit(rope_img, rope_rect)

def draw_winner_screen(winner):
    screen.fill(WHITE)
    win_text = font.render(f"{winner} Wins!", True, BLACK)
    replay_text = font.render("Press SPACE to play again", True, BLACK)
    quit_text = font.render("Press ESC to quit", True, BLACK)

    screen.blit(win_text, (WIDTH//2 - win_text.get_width()//2, HEIGHT//2 - 60))
    screen.blit(replay_text, (WIDTH//2 - replay_text.get_width()//2, HEIGHT//2))
    screen.blit(quit_text, (WIDTH//2 - quit_text.get_width()//2, HEIGHT//2 + 40))

def reset_game():
    global rope_x, state, winner, countdown_start
    rope_x = WIDTH // 2
    state = COUNTDOWN
    winner = None
    countdown_start = time.time()

# Main game loop
tug1 = False
tug2 = False

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    keys = pygame.key.get_pressed()

    if state == START:
        draw_start_screen()
        if keys[pygame.K_SPACE]:
            state = COUNTDOWN
            countdown_start = time.time()

    elif state == COUNTDOWN:
        draw_countdown()
        if time.time() - countdown_start >= 3.5:
            state = PLAYING

    elif state == PLAYING:
        tug1 = keys[pygame.K_a]  # Player 1 (Red - Right)
        tug2 = keys[pygame.K_l]  # Player 2 (Blue - Left)

        if tug1:
            rope_x -= rope_speed  # Player 1 pulls left
        if tug2:
            rope_x += rope_speed  # Player 2 pulls right

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
            reset_game()
        elif keys[pygame.K_ESCAPE]:
            pygame.quit()
            sys.exit()

    pygame.display.flip()
    clock.tick(FPS)
