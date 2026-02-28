import random
from pathlib import Path
from typing import Union

import numpy as np
import pygame
import pygame.locals
from scipy import signal

MAJOR = 2, 2, 1, 2, 2, 2, 1
MINOR = 2, 1, 2, 2, 1, 2, 2
SCALES = MAJOR, MINOR
BASE_FREQUENCY = 440.0
MIN_BALL_RADIUS = 10
MAX_BALL_RADIUS = 30
MIN_DURATION = 250
MAX_DURATION = 1000
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 854
IMAGES_DIR = Path("images")
SOUNDS_DIR = Path("sounds")


def random_image() -> Path:
    return random.choice(list(IMAGES_DIR.iterdir()))


def random_sound() -> Path:
    return random.choice(list(SOUNDS_DIR.iterdir()))


def scale_frequencies(intervals: tuple, octaves: int, start: float) -> list[float]:
    SEMITONE = 2 ** (1 / 12)
    frequencies = [start]
    semitones = 0
    for _ in range(octaves):
        for interval in intervals:
            semitones += interval
            frequencies.append(round(start * (SEMITONE**semitones), 2))
    return frequencies


def converge(a: int, b: int, step: Union[int, float]) -> int:
    if a > b:
        return int(max(b, a - max(1, abs(a - b) / step)))
    elif a < b:
        return int(min(b, a + max(1, abs(b - a) / step)))
    return a


def converge_color(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    step: Union[int, float],
) -> tuple[int, int, int, int]:
    return tuple(converge(a[i], b[i], step) for i in range(len(a)))


def change_frequency(
    samples: np.ndarray, target_freq: float, base_freq: float
) -> np.ndarray:
    semitones = 12 * np.log2(target_freq / base_freq)
    factor = 2 ** (semitones / 12)
    arr = np.array(
        signal.resample(samples, int(len(samples) / factor)),
        dtype="int16",
    ).copy()
    return arr


def random_color() -> tuple[int, int, int, int]:
    return tuple(random.randrange(0, 256) for _ in range(4))


class Ball:
    def __init__(
        self,
        radius: int,
        position: tuple[int, int],
        direction: int,
        note: np.ndarray,
        image: pygame.Surface,
    ) -> None:
        self.radius = radius
        self.position = position
        self.direction = direction
        self.color = random_color()
        self.highlight_color = random_color()
        self.highlight_frames = 10
        self.note = note
        self.draw_color = self.color
        self.image = pygame.transform.scale(image, (radius * 2, radius * 2))
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

    def play_note(self) -> None:
        self.channel.play(self.note)

    def draw(self, display_surf: pygame.Surface) -> None:
        center = tuple(pos + self.radius for pos in self.position)
        if self.highlighted:
            pygame.draw.circle(display_surf, self.draw_color, center, self.radius)
        display_surf.blit(self.image, self.position)


class App:
    def __init__(self, frequencies: list[float]) -> None:
        pygame.init
        pygame.mixer.init(frequency=44100, size=-16, channels=32)
        self.base_sndarray = pygame.sndarray.array(
            pygame.mixer.Sound(file=random_sound())
        )
        self.clock = pygame.time.Clock()
        self.start_time = self.clock.get_time()
        self.prev_draw_time = self.start_time
        self.window_size = WINDOW_WIDTH, WINDOW_HEIGHT
        self.background_color = random_color()
        borderless_flag = 0
        self.display_surf = pygame.display.set_mode(
            self.window_size, pygame.HWSURFACE | pygame.DOUBLEBUF | borderless_flag
        )
        self.base_duration = random.randrange(250, 1000)
        self.ball_radius = random.randrange(MIN_BALL_RADIUS, MAX_BALL_RADIUS)
        self.ball_margin = self.ball_radius // 2
        self.ball_image = pygame.image.load(random_image()).convert_alpha()
        self.balls = [
            Ball(
                radius=self.ball_radius,
                position=(0, 0),
                direction=1,
                note=pygame.sndarray.make_sound(
                    change_frequency(
                        self.base_sndarray,
                        freq,
                        BASE_FREQUENCY,
                    )
                ),
                image=self.ball_image,
            )
            for freq in frequencies
        ]
        pygame.mixer.set_num_channels(len(self.balls))
        for i, ball in enumerate(self.balls):
            ball.channel = pygame.mixer.Channel(i)
        self.rhythm_margin = (
            WINDOW_HEIGHT - len(self.balls) * (2 * self.ball_radius + self.ball_margin)
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
        travel_width = WINDOW_WIDTH - self.ball_radius * 2
        for i, ball in enumerate(self.balls):
            interval = (i * 0.5 + 2) * self.base_duration
            x = int((self.elapsed % interval) / interval * travel_width)
            y = (i + 1) * (2 * self.ball_radius + self.ball_margin) + self.rhythm_margin
            prev_direction = ball.direction
            ball.direction = 1
            if int(self.elapsed / interval) % 2:
                ball.direction = -1
                x = travel_width - x
            if prev_direction != ball.direction:
                ball.start_highlight()
                ball.play_note()
            ball.next_highlight()
            ball.position = (x, y)
            ball.draw(self.display_surf)

    def run(self) -> None:
        self.running = True
        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
            self._draw()
            pygame.display.flip()
        self._exit()


def main() -> None:
    scale = random.choice(SCALES)
    starting_frequency = random.choice(scale_frequencies(scale, 1, BASE_FREQUENCY))
    frequencies = scale_frequencies(scale, random.randrange(1, 4), starting_frequency)
    frequencies = random.sample(frequencies, random.randrange(5, len(frequencies)))
    App(frequencies).run()


if __name__ == "__main__":
    main()
