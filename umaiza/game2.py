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
RED   = (255, 0, 0)
BLUE  = (0, 0, 255)

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

def draw_stick_figure(x, y, color, tug_offset=0):
    x += tug_offset

    # Head
    pygame.draw.circle(screen, color, (x, y), 20)

    # Body
    pygame.draw.line(screen, color, (x, y + 20), (x, y + 80), 4)

    # Arms
    pygame.draw.line(screen, color, (x - 20, y + 40), (x + 20, y + 40), 3)

    # Legs
    pygame.draw.line(screen, color, (x, y + 80), (x - 15, y + 110), 3)
    pygame.draw.line(screen, color, (x, y + 80), (x + 15, y + 110), 3)

def draw_game(rope_x, tug1, tug2):
    screen.fill(WHITE)

    base_y = HEIGHT // 2 - 80

    # Player 1 - Red
    tug_offset1 = -5 if tug1 else 0
    draw_stick_figure(150, base_y, RED, tug_offset1)

    # Player 2 - Blue
    tug_offset2 = 5 if tug2 else 0
    draw_stick_figure(WIDTH - 150, base_y, BLUE, tug_offset2)

    # Rope
    pygame.draw.line(screen, BLACK, (rope_x, HEIGHT//2 - 40), (rope_x, HEIGHT//2 + 40), 6)

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
        tug1 = keys[pygame.K_a]
        tug2 = keys[pygame.K_l]

        if tug1:
            rope_x -= rope_speed
        if tug2:
            rope_x += rope_speed

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
            reset_game()
        elif keys[pygame.K_ESCAPE]:
            pygame.quit()
            sys.exit()

    pygame.display.flip()
    clock.tick(FPS)
