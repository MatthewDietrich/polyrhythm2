import random
from enum import Enum
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
SEMITONE = 2 ** (1 / 12)
MAX_BALL_RADIUS = 30
MIN_DURATION = 250
MAX_DURATION = 1000
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 854
IMAGES_DIR = Path("images")
SOUNDS_DIR = Path("sounds")
IMAGES = list(IMAGES_DIR.iterdir())
SOUNDS = list(SOUNDS_DIR.iterdir())


class Mode(Enum):
    DEFAULT = "default"
    TRANSPOSE = "transpose"
    RIBBON = "ribbon"
    ZIGZAG = "zigzag"


def random_image() -> Path:
    return random.choice(IMAGES)


def random_sound() -> Path:
    return random.choice(SOUNDS)


def scale_frequencies(intervals: tuple, octaves: int, start: float) -> list[float]:
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
    return tuple(converge(ca, cb, step) for ca, cb in zip(a, b))


def change_frequency(
    samples: np.ndarray, target_freq: float, base_freq: float
) -> np.ndarray:
    factor = target_freq / base_freq
    return np.array(
        signal.resample(samples, int(len(samples) / factor)),
        dtype="int16",
    ).copy()


def random_color() -> tuple[int, int, int, int]:
    return (
        random.randrange(0, 256),
        random.randrange(0, 256),
        random.randrange(0, 256),
        random.randrange(0, 256),
    )


class Ball:
    def __init__(
        self,
        radius: int,
        position: tuple[int, int],
        note: pygame.mixer.Sound,
        image: pygame.Surface,
        channel: pygame.mixer.Channel,
    ) -> None:
        self.radius = radius
        self.position = position
        self.color = random_color()
        self.highlight_color = random_color()
        self.highlight_frames = 10
        self.note = note
        self.draw_color = self.color
        self.image = pygame.transform.scale(image, (radius * 2, radius * 2))
        self.highlighted = False
        self.channel = channel

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
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=32)
        self.base_sndarray = pygame.sndarray.array(
            pygame.mixer.Sound(file=random_sound())
        )
        self.clock = pygame.time.Clock()
        self.window_size = WINDOW_WIDTH, WINDOW_HEIGHT
        self.background_color = random_color()
        self.display_surf = pygame.display.set_mode(
            self.window_size, pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        self.base_duration = random.randrange(MIN_DURATION, MAX_DURATION)
        self.ball_image = pygame.image.load(random_image()).convert_alpha()
        self.mode = random.choice(list(Mode))
        pygame.mixer.set_num_channels(len(frequencies))

        match self.mode:
            case Mode.TRANSPOSE:
                self.ball_radius = int(
                    min(WINDOW_WIDTH / len(frequencies) / 2.5, MAX_BALL_RADIUS)
                )
                self.ball_margin = self.ball_radius // 2
                self.rhythm_margin = (
                    WINDOW_WIDTH
                    - len(frequencies) * (2 * self.ball_radius + self.ball_margin)
                ) / 2
                self.travel_distance = WINDOW_HEIGHT - self.ball_radius * 2
            case Mode.RIBBON:
                self.ball_radius = MAX_BALL_RADIUS
                self.ball_margin = self.ball_radius // 2
                self.max_x = WINDOW_WIDTH - self.ball_radius * 2
                self.max_y = WINDOW_HEIGHT - self.ball_radius * 2
            case Mode.DEFAULT:
                self.ball_radius = int(
                    min(WINDOW_HEIGHT / len(frequencies) / 2.5, MAX_BALL_RADIUS)
                )
                self.ball_margin = self.ball_radius // 2
                self.rhythm_margin = (
                    WINDOW_HEIGHT
                    - len(frequencies) * (2 * self.ball_radius + self.ball_margin)
                ) / 2
                self.travel_distance = WINDOW_WIDTH - self.ball_radius * 2
            case Mode.ZIGZAG:
                self.ball_radius = MAX_BALL_RADIUS
                self.ball_margin = self.ball_radius // 2
                self.travel_distance = WINDOW_HEIGHT - self.ball_radius * 2
                self.max_x = WINDOW_WIDTH - self.ball_radius * 2

        self.balls = [
            Ball(
                radius=self.ball_radius,
                position=(0, 0),
                note=pygame.sndarray.make_sound(
                    change_frequency(
                        self.base_sndarray,
                        freq,
                        BASE_FREQUENCY,
                    )
                ),
                image=self.ball_image,
                channel=pygame.mixer.Channel(i),
            )
            for i, freq in enumerate(frequencies)
        ]
        self.elapsed = 0

    def _exit(self) -> None:
        print("Exiting")
        pygame.mixer.quit()
        pygame.quit()

    def _calculate_coordinates(
        self, i: int, interval: float, prev_elapsed: int
    ) -> tuple[tuple[int, int], bool]:
        match self.mode:
            case Mode.TRANSPOSE:
                x = int(
                    i * (2 * self.ball_radius + self.ball_margin) + self.rhythm_margin
                )
                y = int((self.elapsed % interval) / interval * self.travel_distance)
                segment = int(self.elapsed / interval) % 2
                if segment:
                    y = self.travel_distance - y
                bounced = segment != int(prev_elapsed / interval) % 2
            case Mode.RIBBON:
                x_interval = interval
                y_interval = interval * 2 / 3
                x = int((self.elapsed % x_interval) / x_interval * self.max_x)
                if int(self.elapsed / x_interval) % 2:
                    x = self.max_x - x
                y = int((self.elapsed % y_interval) / y_interval * self.max_y)
                if int(self.elapsed / y_interval) % 2:
                    y = self.max_y - y
                bounced = int(self.elapsed / x_interval) != int(
                    prev_elapsed / x_interval
                ) or int(self.elapsed / y_interval) != int(prev_elapsed / y_interval)
            case Mode.DEFAULT:
                x = int((self.elapsed % interval) / interval * self.travel_distance)
                y = int(
                    (i + 1) * (2 * self.ball_radius + self.ball_margin)
                    + self.rhythm_margin
                )
                segment = int(self.elapsed / interval) % 2
                if segment:
                    x = self.travel_distance - x
                bounced = segment != int(prev_elapsed / interval) % 2
            case Mode.ZIGZAG:
                interval = interval * 8
                segment = int(self.elapsed / interval) % 2
                prev_segment = int(prev_elapsed / interval) % 2
                t = (self.elapsed % interval) / interval
                t_prev = (prev_elapsed % interval) / interval
                if segment:
                    t = 1 - t
                if prev_segment:
                    t_prev = 1 - t_prev
                y = int(t * self.travel_distance)
                x_step = int(8 * t)
                x_t = (8 * t) % 1.0
                x = int((1 - x_t if x_step % 2 else x_t) * self.max_x)
                bounced = segment != prev_segment or x_step != int(8 * t_prev)
        return (x, y), bounced

    def _draw(self) -> None:
        dt = self.clock.get_time()
        prev_elapsed = self.elapsed
        self.elapsed += dt
        self.display_surf.fill(self.background_color)

        for i, ball in enumerate(self.balls):
            interval = (i / 2 + 2) * self.base_duration
            (x, y), bounced = self._calculate_coordinates(i, interval, prev_elapsed)
            if bounced:
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
    starting_frequency = random.choice(scale_frequencies(scale, 2, BASE_FREQUENCY / 2))
    frequencies = scale_frequencies(scale, random.randrange(1, 4), starting_frequency)
    frequencies = random.sample(frequencies, random.randrange(5, len(frequencies)))
    App(frequencies).run()


if __name__ == "__main__":
    main()
