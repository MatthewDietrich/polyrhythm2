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
SEMITONE = 2 ** (1 / 12)
MAX_BALL_RADIUS = 30
MIN_DURATION = 250
MAX_DURATION = 1000
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 854
IMAGES_DIR = Path("images")
SOUNDS_DIR = Path("sounds")
MODES = "default", "transpose", "dvd"


def random_image() -> Path:
    return random.choice(list(IMAGES_DIR.iterdir()))


def random_sound() -> Path:
    return random.choice(list(SOUNDS_DIR.iterdir()))


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
    return (
        converge(a[0], b[0], step),
        converge(a[1], b[1], step),
        converge(a[2], b[2], step),
        converge(a[3], b[3], step),
    )


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
        direction: int,
        note: pygame.mixer.Sound,
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
        self.channel = None

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
        if self.channel is not None:
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
        self.mode = random.choice(MODES)
        match self.mode:
            case "transpose":
                self.ball_radius = min(
                    WINDOW_WIDTH / len(frequencies) / 2.5, MAX_BALL_RADIUS
                )
            case "dvd":
                self.ball_radius = MAX_BALL_RADIUS
            case _:
                self.ball_radius = min(
                    WINDOW_HEIGHT / len(frequencies) / 2.5, MAX_BALL_RADIUS
                )
        self.ball_margin = self.ball_radius // 2
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

        match self.mode:
            case "transpose":
                self.rhythm_margin = (
                    WINDOW_WIDTH
                    - len(self.balls) * (2 * self.ball_radius + self.ball_margin)
                ) / 2
                self.travel_distance = WINDOW_HEIGHT - self.ball_radius * 2
            case "dvd":
                self.dvd_speed = 200.0
                max_x = WINDOW_WIDTH - self.ball_radius * 2
                max_y = WINDOW_HEIGHT - self.ball_radius * 2
                for ball in self.balls:
                    ball.dvd_x = float(random.randrange(0, max_x))
                    ball.dvd_y = float(random.randrange(0, max_y))
                    ball.dvd_dx = random.choice([-1, 1])
                    ball.dvd_dy = random.choice([-1, 1])
            case _:
                self.rhythm_margin = (
                    WINDOW_HEIGHT
                    - len(self.balls) * (2 * self.ball_radius + self.ball_margin)
                ) / 2
                self.travel_distance = WINDOW_WIDTH - self.ball_radius * 2
        self.elapsed = 0

    def _exit(self) -> None:
        print("Exiting")
        pygame.mixer.quit()
        pygame.quit()

    def _calculate_coordinates(
        self, i: int, ball: Ball, interval: float
    ) -> tuple[int, int]:
        match self.mode:
            case "transpose":
                x = i * (2 * self.ball_radius + self.ball_margin) + self.rhythm_margin
                y = int((self.elapsed % interval) / interval * self.travel_distance)
                if int(self.elapsed / interval) % 2:
                    ball.direction = -1
                    y = self.travel_distance - y
            case "dvd":
                max_x = WINDOW_WIDTH - self.ball_radius * 2
                max_y = WINDOW_HEIGHT - self.ball_radius * 2
                ball.dvd_x += ball.dvd_dx * self.dvd_speed * self.dt / 1000
                ball.dvd_y += ball.dvd_dy * self.dvd_speed * self.dt / 1000
                if ball.dvd_x <= 0:
                    ball.dvd_x = 0
                    ball.dvd_dx = 1
                    ball.direction = -1
                elif ball.dvd_x >= max_x:
                    ball.dvd_x = max_x
                    ball.dvd_dx = -1
                    ball.direction = -1
                if ball.dvd_y <= 0:
                    ball.dvd_y = 0
                    ball.dvd_dy = 1
                    ball.direction = -1
                elif ball.dvd_y >= max_y:
                    ball.dvd_y = max_y
                    ball.dvd_dy = -1
                    ball.direction = -1
                x = int(ball.dvd_x)
                y = int(ball.dvd_y)
            case _:
                x = int((self.elapsed % interval) / interval * self.travel_distance)
                y = (i + 1) * (
                    2 * self.ball_radius + self.ball_margin
                ) + self.rhythm_margin
                if int(self.elapsed / interval) % 2:
                    ball.direction = -1
                    x = self.travel_distance - x
        return x, y

    def _draw(self) -> None:
        self.dt = self.clock.get_time()
        self.elapsed += self.dt
        self.display_surf.fill(self.background_color)

        for i, ball in enumerate(self.balls):
            interval = (i / 2 + 2) * self.base_duration
            prev_direction = ball.direction
            ball.direction = 1
            x, y = self._calculate_coordinates(i, ball, interval)
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
    starting_frequency = random.choice(scale_frequencies(scale, 2, BASE_FREQUENCY / 2))
    frequencies = scale_frequencies(scale, random.randrange(1, 4), starting_frequency)
    frequencies = random.sample(frequencies, random.randrange(5, len(frequencies)))
    App(frequencies).run()


if __name__ == "__main__":
    main()
