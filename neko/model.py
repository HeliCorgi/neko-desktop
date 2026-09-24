"""Cat behaviour. Pure Python: no GUI, files, network, or background threads."""
from dataclasses import dataclass, field
import random

STATES = ("idle", "walk", "sleep", "pet", "eat")
LABELS = {"idle": "のんびりしています", "walk": "おさんぽ中", "sleep": "すやすや…",
          "pet": "なでなで、うれしいな", "eat": "おやつの時間"}


@dataclass
class Cat:
    rng: random.Random = field(default_factory=random.Random)
    x: float = 100.0
    limit: float = 600.0
    direction: int = 1
    state: str = "idle"
    elapsed: float = 0.0
    remaining: float = 3.0
    sleeping: bool = False
    speed: float = 34.0  # logical pixels / second; independent of refresh rate

    def set_bounds(self, limit: float) -> None:
        self.limit = max(0.0, limit)
        self.x = max(0.0, min(self.x, self.limit))

    def act(self, state: str) -> None:
        if state not in STATES:
            raise ValueError("Unknown cat state")
        self.state, self.elapsed = state, 0.0
        self.remaining = {"idle": 3.0, "walk": 9.0, "sleep": 24.0,
                          "pet": 3.0, "eat": 4.0}[state]
        self.sleeping = state == "sleep"

    def step(self, dt: float) -> None:
        # Bound suspend/resume jumps. A low refresh rate must not increase speed.
        dt = max(0.0, min(dt, 0.5))
        self.elapsed += dt
        if self.state == "walk":
            self.x += self.direction * self.speed * min(dt, 0.1)
            if self.x >= self.limit:
                self.x, self.direction = self.limit, -1
            elif self.x <= 0:
                self.x, self.direction = 0.0, 1
        if self.sleeping:
            return
        self.remaining -= dt
        if self.remaining <= 0:
            previous = self.state
            state = "idle" if previous != "idle" else self.rng.choices(
                ["walk", "sleep", "idle"], weights=[7, 1, 2])[0]
            self.act(state)
            self.sleeping = False  # natural naps end; the Sleep button holds a nap
            self.remaining *= self.rng.uniform(0.7, 1.4)


def clamp_position(x: int, y: int, width: int, height: int,
                   available: tuple[int, int, int, int]) -> tuple[int, int]:
    """Keep the entire pet in one screen's usable area, including negative origins."""
    left, top, area_width, area_height = available
    return (max(left, min(x, left + max(0, area_width - width))),
            max(top, min(y, top + max(0, area_height - height))))
