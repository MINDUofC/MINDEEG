import pygame
import sys

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
win_boundary = 100  # Distance from edge to declare win

# Clock
clock = pygame.time.Clock()
FPS = 60

# Game States
START = 0
PLAYING = 1
GAME_OVER = 2
state = START
winner = None

def draw_start_screen():
    screen.fill(WHITE)
    title = font.render("TUG OF WAR", True, BLACK)
    prompt = font.render("Press SPACE to Start", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 80))
    screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2))

def draw_game(rope_x):
    screen.fill(WHITE)

    # Draw players
    # Player 1 - Left (Red)
    pygame.draw.circle(screen, RED, (150, HEIGHT//2), 30)
    pygame.draw.line(screen, RED, (150, HEIGHT//2 + 30), (150, HEIGHT//2 + 80), 5)

    # Player 2 - Right (Blue)
    pygame.draw.circle(screen, BLUE, (WIDTH - 150, HEIGHT//2), 30)
    pygame.draw.line(screen, BLUE, (WIDTH - 150, HEIGHT//2 + 30), (WIDTH - 150, HEIGHT//2 + 80), 5)

    # Draw rope
    pygame.draw.line(screen, BLACK, (rope_x, HEIGHT//2 - 40), (rope_x, HEIGHT//2 + 40), 6)

def draw_winner(winner):
    screen.fill(WHITE)
    text = font.render(f"{winner} Wins!", True, BLACK)
    screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - 20))

def reset_game():
    global rope_x, state, winner
    rope_x = WIDTH // 2
    state = START
    winner = None

# Main game loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    keys = pygame.key.get_pressed()

    if state == START:
        draw_start_screen()
        if keys[pygame.K_SPACE]:
            state = PLAYING

    elif state == PLAYING:
        if keys[pygame.K_a]:
            rope_x -= rope_speed
        if keys[pygame.K_l]:
            rope_x += rope_speed

        # Win conditions
        if rope_x < win_boundary:
            winner = "Player 1"
            state = GAME_OVER
        elif rope_x > WIDTH - win_boundary:
            winner = "Player 2"
            state = GAME_OVER

        draw_game(rope_x)

    elif state == GAME_OVER:
        draw_winner(winner)
        if keys[pygame.K_SPACE]:
            reset_game()

    pygame.display.flip()
    clock.tick(FPS)
