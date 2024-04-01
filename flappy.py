import pygame
from pygame.locals import *
import random
import asyncio
import serial
import struct
import time

# Initialize game parameters class
class GameParams:
    def __init__(self):
        self.scroll_speed = 6  # Adjust scroll speed
        self.pipe_gap = 200
        self.pipe_frequency = 4000
        self.screen_width = 864
        self.screen_height = 936
        self.fps = 60
        self.font = pygame.font.SysFont('Bauhaus 93', 60)
        self.bg = pygame.image.load('img/bg.png')
        self.ground_img = pygame.image.load('img/ground.png')

# Initialize game state class
class GameState:
    def __init__(self):
        self.flying = False
        self.game_over = False
        self.last_pipe = -1500
        self.score = 0
        self.pass_pipe = False
        self.run = True
        self.ground_scroll = 0 
        self.emg_triggered = False  # Flag to track if EMG data exceeds threshold

# Initialize  pipe class
class Pipe(pygame.sprite.Sprite):
    def __init__(self, x, y, position, pipe_gap, scroll_speed):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load("img/pipe.png")
        self.rect = self.image.get_rect()
        self.scroll_speed = scroll_speed # Pipe scroll speed is the same as game scroll speed
        if position == 1:
            self.image = pygame.transform.flip(self.image, False, True)
            self.rect.bottomleft = [x, y - int(pipe_gap / 2)]
        elif position == -1:
            self.rect.topleft = [x, y + int(pipe_gap / 2)]

    def update(self):
        self.rect.x -= self.scroll_speed
        if self.rect.right < 0:
            self.kill()

# Intitialize button class
class Button():
    def __init__(self, x, y, image):
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)

    def draw(self, screen):
        action = False
        pos = pygame.mouse.get_pos()
        if self.rect.collidepoint(pos):
            if pygame.mouse.get_pressed()[0] == 1:
                action = True
        screen.blit(self.image, (self.rect.x, self.rect.y))
        return action

def read_serial_data(ser):
    # Read analog sensor data from Arduino (0-1023)
    return int(ser.readline().decode().strip())

def notify_callback(sender: int, data: int, gstate: GameState):
    # Threshold for EMG data
    threshold = 302
    if data >= threshold:
        gstate.emg_triggered = True # If Arduino data is greater than or equal to 302, EMG is triggered
    else:
        gstate.emg_triggered = False

# Initialize bird class
class Bird(pygame.sprite.Sprite):
    def __init__(self, x, y, game_state):
        pygame.sprite.Sprite.__init__(self)
        self.images = []
        self.index = 0
        self.counter = 0
        for num in range(1, 4):
            img = pygame.image.load(f"img/bird{num}.png")
            self.images.append(img)
        self.image = self.images[self.index]
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.vel = 0
        self.clicked = False
        self.game_state = game_state

    def update(self):
        if self.game_state.flying:
            self.vel += 0.7  # Adjust falling speed of bird
            if self.vel > 12:  # Adjust the max falling speed of bird
                self.vel = 12
            if self.rect.bottom < 768:
                self.rect.y += int(self.vel)
            flap_cooldown = 5
            self.counter += 1
            if self.counter > flap_cooldown:
                self.counter = 0
                self.index += 1
                if self.index >= len(self.images):
                    self.index = 0
                self.image = self.images[self.index]
            self.image = pygame.transform.rotate(self.images[self.index], self.vel * -2)
        else:
            self.image = pygame.transform.rotate(self.images[self.index], -90)

# Function to draw text and boxes on screen
def draw_text(screen, text, font, x, y, color=(255, 255, 255), bg_color=None):
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    text_rect.topleft = (x, y)

    if bg_color:
        background_surface = pygame.Surface((text_rect.width, text_rect.height))
        background_surface.fill(bg_color)
        screen.blit(background_surface, text_rect.topleft)

    screen.blit(text_surface, text_rect)

# Function to reset the game
def reset_game(pipe_group, flappy, gparams, gstate):
    pipe_group.empty()
    flappy.rect.x = 100
    flappy.rect.y = int(gparams.screen_height / 2)
    gstate.score = 0

# Main function calls all other functions and classes
async def main():
    pygame.init()
    gparams = GameParams()
    gstate = GameState()
    screen = pygame.display.set_mode((gparams.screen_width, gparams.screen_height))
    pygame.display.set_caption('Flappy Bird')
    clock = pygame.time.Clock()
    button_img = pygame.image.load('img/restart.png')
    button = Button(gparams.screen_width // 2 - 50, gparams.screen_height // 2 - 100, button_img)
    pipe_group = pygame.sprite.Group()
    bird_group = pygame.sprite.Group()
    flappy = Bird(100, int(gparams.screen_height / 2), gstate)
    bird_group.add(flappy)

    # Open serial port for Arduino sensor
    ser = serial.Serial('COM7', 9600) 

    # Execute while the game state is running
    while gstate.run:
        await asyncio.sleep(0.01)
        clock.tick(gparams.fps)
        screen.blit(gparams.bg, (0,0))
        pipe_group.draw(screen)
        bird_group.draw(screen)
        bird_group.update()
        screen.blit(gparams.ground_img, (gstate.ground_scroll, 768))

        # Read sensor data from serial port
        sensor_data = read_serial_data(ser)
        notify_callback(None, sensor_data, gstate)  # Call the notify_callback function with the EMG data and gstate
        if gstate.emg_triggered:  
            flappy.vel = -10  # Set the bird's velocity to a negative value to make it jump
            gstate.flying = True # Update the flying state to True to keep the bird flying

        if len(pipe_group) > 0:
            if bird_group.sprites()[0].rect.left > pipe_group.sprites()[0].rect.left\
                and bird_group.sprites()[0].rect.right < pipe_group.sprites()[0].rect.right\
                and not gstate.pass_pipe:
                gstate.pass_pipe = True
            if gstate.pass_pipe:
                if bird_group.sprites()[0].rect.left > pipe_group.sprites()[0].rect.right:
                    gstate.score += 1  # Add to score when bird passes through pipe
                    gstate.pass_pipe = False
        draw_text(screen, str(gstate.score), gparams.font, int(gparams.screen_width / 2), 20)

        if pygame.sprite.groupcollide(bird_group, pipe_group, False, False) or flappy.rect.top < 0:
            gstate.game_over = True
        if flappy.rect.bottom >= 768:
            gstate.game_over = True
            gstate.flying = False

        # Continue to randomly generate pipes when bird is flying and the game is not over
        if gstate.flying and not gstate.game_over:
            time_now = pygame.time.get_ticks()
            if time_now - gstate.last_pipe > gparams.pipe_frequency and len(pipe_group) < 8:  # Ensure only 6 pipes at most
                pipe_height = random.randint(-100, 100)
                btm_pipe = Pipe(gparams.screen_width, int(gparams.screen_height / 2) + pipe_height, -1, gparams.pipe_gap, gparams.scroll_speed)
                top_pipe = Pipe(gparams.screen_width, int(gparams.screen_height / 2) + pipe_height, 1, gparams.pipe_gap, gparams.scroll_speed)
                pipe_group.add(btm_pipe)
                pipe_group.add(top_pipe)
                gstate.last_pipe = time_now

            pipe_group.update()

            gstate.ground_scroll -= gparams.scroll_speed
            if abs(gstate.ground_scroll) > 35:
                gstate.ground_scroll = 0

        if gstate.game_over:
            if button.draw(screen):
                gstate.game_over = False
                reset_game(pipe_group, flappy, gparams, gstate)  # Pass gstate to reset_game
            # Display score on screen when game over
            draw_text(screen, "Score: " + str(gstate.score), gparams.font, int(gparams.screen_width / 2) - 100, int(gparams.screen_height / 2), (255, 255, 255), (0, 0, 0))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gstate.run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    # Set the bird's velocity to a negative value to make it jump
                    flappy.vel = -10
                    # Update the flying state to True to keep the bird flying
                    gstate.flying = True

        pygame.display.update()

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())