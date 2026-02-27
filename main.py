import os
from typing import Union

import numpy as np
import pygame
import pygame.locals
import yaml
from scipy import signal

with open("config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)


def converge(a: int, b: int, step: Union[int, float]) -> int:
    if a > b:
        if b == 0:
            b = a - 1
        return int(max(0, a - b / step))
    elif a < b:
        if b == 0:
            b = a + 1
        return int(min(255, a + b / step))
    return a


def converge_color(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    step: Union[int, float],
) -> tuple[int, int, int, int]:
    return tuple(converge(a[i], b[i], step) for i in range(len(a)))


def change_frequency(
    samples: np.ndarray, target_freq: float, base_freq: float
):
    semitones = 12 * np.log2(target_freq / base_freq)
    factor = 2 ** (semitones / 12)  # equivalent to target_freq / base_freq
    arr = np.array(
        signal.resample(samples, int(len(samples) / factor)),
        dtype="int16",
    ).copy()
    return arr


class Ball:
    def __init__(self, radius: int, position: tuple[int, int], direction: int, note: np.ndarray) -> None:
        self.radius = radius
        self.position = position
        self.direction = direction
        self.color = tuple(CONFIG["ball"]["color"])
        self.highlight_color = tuple(CONFIG["ball"]["highlight_color"])
        self.highlight_frames = CONFIG["ball"]["highlight_frames"]
        self.note = note
        self.draw_color = self.color
        self.highlighted = False

    def start_highlight(self) -> None:
        self.highlighted = True
        self.draw_color = self.highlight_color

    def next_highlight(self) -> None:
        if self.highlighted:
            self.draw_color = converge_color(
                self.draw_color, self.color, self.highlight_frames
            )
        if self.draw_color == self.color:
            self.highlighted = False

    def play_note(self):
        self.channel.play(self.note)

    def draw(self, display_surf):
        pygame.draw.circle(display_surf, self.draw_color, self.position, self.radius)


class App:
    def __init__(self) -> None:
        pygame.init
        pygame.mixer.init(
            frequency=44100,
            size=-16,
            channels=32
        )
        self.base_sndarray = pygame.sndarray.array(
            pygame.mixer.Sound(file=CONFIG["rhythm"]["base_sound"])
        )
        self.clock = pygame.time.Clock()
        self.start_time = self.clock.get_time()
        self.prev_draw_time = self.start_time
        self.window_size = CONFIG["window"]["size"]
        self.background_color = CONFIG["window"]["background_color"]
        borderless_flag = 0
        if CONFIG["window"]["borderless"]:
            borderless_flag = pygame.NOFRAME
            os.environ["SDL_VIDEO_WINDOW_POS"] = "0.0"
        self.display_surf = pygame.display.set_mode(
            self.window_size, pygame.HWSURFACE | pygame.DOUBLEBUF | borderless_flag
        )
        self.base_duration = CONFIG["rhythm"]["duration"] * 1000
        self.ball_radius = CONFIG["ball"]["radius"]
        self.ball_margin = CONFIG["ball"]["margin"]
        self.balls = [
            Ball(
                radius=self.ball_radius,
                position=(0, 0),
                direction=1,
                note=pygame.sndarray.make_sound(
                    change_frequency(
                        self.base_sndarray,
                        freq,
                        CONFIG["rhythm"]["base_frequency"],
                    )
                )
            )
            for freq in CONFIG["rhythm"]["notes"]
        ]
        pygame.mixer.set_num_channels(len(self.balls))
        for i, ball in enumerate(self.balls):
            ball.channel = pygame.mixer.Channel(i)
        self.rhythm_margin = (
            self.window_size[1]
            - len(self.balls) * (2 * self.ball_radius + self.ball_margin)
        ) / 2
        self.elapsed = 0

    def _exit(self) -> None:
        print("Exiting")
        pygame.mixer.quit()
        pygame.quit()

    def _draw(self) -> None:
        dt = self.clock.get_time()
        self.elapsed += dt
        self.display_surf.fill(self.background_color)
        for i, ball in enumerate(self.balls):
            interval = (i * 0.5 + 2) * self.base_duration
            x = int((self.elapsed % interval) / interval * self.window_size[0])
            y = (i + 1) * (2 * self.ball_radius + self.ball_margin) + self.rhythm_margin
            prev_direction = ball.direction
            ball.direction = 1

            if int(self.elapsed / interval) % 2:
                ball.direction = -1
                x = self.window_size[0] - x
            if prev_direction != ball.direction:
                ball.start_highlight()
                ball.play_note()
            ball.next_highlight()

            ball.position = (x, y)
            ball.draw(self.display_surf)

    def run(self):
        self.running = True
        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
            self._draw()
            pygame.display.flip()
        self._exit()


def main():
    App().run()


if __name__ == "__main__":
    main()
