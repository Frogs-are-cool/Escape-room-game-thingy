"""A graphical Pygame version of escape_room.py.

Install the dependency with:
    python -m pip install -r escape_room_requirements.txt

Run with:
    python escape_room_pygame.py
"""

from __future__ import annotations

import math
import os
import time

try:
    import pygame
except ImportError as exc:
    raise SystemExit(
        "Pygame is required. Install it with: "
        "python -m pip install -r escape_room_requirements.txt"
    ) from exc

import escape_room as game


WIDTH = 1200
HEIGHT = 820
FPS = 60

INK = (235, 231, 218)
MUTED = (165, 173, 181)
GOLD = (244, 190, 93)
PANEL = (22, 29, 39)
PANEL_LIGHT = (31, 41, 54)
OUTLINE = (70, 83, 99)
GREEN = (111, 202, 151)
RED = (239, 109, 103)

ROOM_NAMES = {
    "start": "THE STONE CELL",
    "hallway": "THE ECHO HALL",
    "lab": "THE ALCHEMY LAB",
    "lab_explosion": "THE SHATTERED LAB",
    "vault": "THE HIDDEN VAULT",
    "lockdown": "LOCKDOWN",
    "final_room": "DAYLIGHT",
}

ITEM_NAMES = {
    "brass_key": "Brass key",
    "table_salt": "Table salt",
    "water": "Water",
    "sand": "Sand",
    "apple_juice": "Apple juice",
}

ITEM_COLORS = {
    "brass_key": (230, 177, 69),
    "table_salt": (224, 232, 241),
    "water": (92, 178, 232),
    "sand": (210, 169, 105),
    "apple_juice": (231, 146, 70),
}

ROOM_COLORS = {
    "start": ((34, 39, 51), (89, 75, 65), (185, 113, 62)),
    "hallway": ((34, 52, 63), (64, 81, 87), (94, 139, 151)),
    "lab": ((55, 87, 105), (164, 196, 194), (115, 218, 198)),
    "lab_explosion": ((53, 38, 48), (105, 57, 57), (235, 99, 73)),
    "vault": ((23, 36, 54), (61, 76, 91), (88, 174, 143)),
    "lockdown": ((54, 25, 35), (105, 40, 47), (235, 66, 75)),
    "final_room": ((70, 106, 118), (162, 181, 154), (250, 213, 135)),
}


def blend(top: tuple[int, int, int], bottom: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * amount) for a, b in zip(top, bottom))


class EscapeRoomUI:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("The Last Door — Escape Room")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.body_font = pygame.font.Font(None, 25)
        self.heading_font = pygame.font.Font(None, 34)
        self.title_font = pygame.font.Font(None, 40)
        self.state = game.load_game() or game.new_state()
        self.state.setdefault("inventory", [])
        self.state.setdefault("flags", [])
        self.state.setdefault("attempts", {})
        self.puzzle_dialog: dict | None = None
        self.puzzle_text = ""
        self.puzzle_feedback = ""
        self.toast = "Your progress is ready. Find a way out."
        self.toast_until = time.monotonic() + 4
        self.confirm_restart = False
        self.choice_rects: list[tuple[pygame.Rect, str]] = []
        self.save_rect = pygame.Rect(WIDTH - 226, 18, 188, 42)
        self.restart_rect = pygame.Rect(WIDTH - 416, 18, 174, 42)
        self.new_run_rect = pygame.Rect(WIDTH - 224, 724, 188, 42)
        self.particles = [
            (i * 97 % 780, i * 53 % 350, i * 11 % 100, i % 3)
            for i in range(24)
        ]

    def notify(self, message: str, *, error: bool = False) -> None:
        self.toast = message
        self.toast_until = time.monotonic() + (5 if error else 3.5)

    def save(self, *, show_success: bool = False) -> bool:
        try:
            game.save_game(self.state)
        except OSError as exc:
            self.notify(f"Could not save progress: {exc}", error=True)
            return False
        if show_success:
            self.notify("Progress saved.")
        return True

    def room_choices(self) -> list[tuple[str, dict]]:
        room = game.ROOMS[self.state["current_room"]]
        return [
            (label, choice)
            for label, choice in room["choices"].items()
            if "shown_if_flag" not in choice
            or choice["shown_if_flag"] in self.state["flags"]
        ]

    def set_room(self, room_name: str) -> None:
        self.state["current_room"] = room_name
        self.puzzle_dialog = None
        self.puzzle_text = ""
        self.puzzle_feedback = ""
        self.save()
        if game.ROOMS[room_name].get("ending"):
            try:
                os.remove(game.SAVE_FILE)
            except FileNotFoundError:
                pass
            except OSError as exc:
                self.notify(f"Ending reached, but save cleanup failed: {exc}", error=True)

    def choose(self, label: str) -> None:
        choice = dict(self.room_choices()).get(label)
        if choice is None:
            return

        required_item = choice.get("requires_item")
        if required_item and required_item not in self.state["inventory"]:
            self.notify(choice.get("fail_result", "You cannot do that yet."))
            return

        if "puzzle" in choice:
            self.open_puzzle(choice["puzzle"], "mix")
            return
        if "code_puzzle" in choice:
            self.open_puzzle(choice["code_puzzle"], "code")
            return

        item = choice.get("give_item")
        if item and item in self.state["inventory"]:
            self.notify("You already took that.")
        else:
            if item:
                self.state["inventory"].append(item)
                self.notify(f"Found: {ITEM_NAMES.get(item, item.replace('_', ' ').title())}")
            else:
                self.notify(choice["result"])
        self.set_room(choice["next"])

    def open_puzzle(self, puzzle: dict, puzzle_type: str) -> None:
        flag = puzzle["sets_flag"]
        if flag in self.state["flags"]:
            self.notify(puzzle["done"])
            return
        if puzzle_type == "mix":
            missing = [
                item for item in puzzle["answer"]
                if item not in self.state["inventory"]
            ]
            if missing:
                self.notify(puzzle["missing"])
                return
        self.puzzle_dialog = {"data": puzzle, "type": puzzle_type}
        self.puzzle_text = ""
        self.puzzle_feedback = ""

    def submit_puzzle(self) -> None:
        if self.puzzle_dialog is None:
            return
        puzzle = self.puzzle_dialog["data"]
        answer = self.puzzle_text.strip()
        puzzle_type = self.puzzle_dialog["type"]

        if not answer:
            self.puzzle_feedback = "Enter an answer, or press Escape to cancel."
            return

        if puzzle_type == "mix":
            lookup = {
                alias: item
                for item, aliases in puzzle["aliases"].items()
                for alias in aliases
            }
            parts = [part.strip().lower() for part in answer.split(",") if part.strip()]
            if not parts:
                self.puzzle_feedback = "No ingredients entered; no attempt used."
                return
            if any(part not in lookup for part in parts):
                self.puzzle_feedback = "Use the ingredient names or initials, separated by commas. No attempt used."
                return
            submitted = [lookup[part] for part in parts]
            correct = submitted == puzzle["answer"]
        else:
            if not answer.isdigit():
                self.puzzle_feedback = "The keypad only accepts digits. No attempt used."
                return
            correct = answer == puzzle["answer"]

        if correct:
            self.state["flags"].append(puzzle["sets_flag"])
            self.puzzle_dialog = None
            self.puzzle_text = ""
            self.puzzle_feedback = ""
            if self.save():
                self.notify(puzzle["success"])
            return

        attempts = self.state["attempts"].get(puzzle["id"], 0) + 1
        self.state["attempts"][puzzle["id"]] = attempts
        remaining = puzzle["max_attempts"] - attempts
        if remaining <= 0:
            self.puzzle_dialog = None
            self.puzzle_text = ""
            self.puzzle_feedback = ""
            self.notify(puzzle["lockout"], error=True)
            self.set_room(puzzle["lose_room"])
            return

        self.puzzle_feedback = f"{puzzle['failure']}  Attempts left: {remaining}"
        self.puzzle_text = ""
        self.save()

    def draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        x: int,
        y: int,
        max_width: int,
        line_height: int | None = None,
    ) -> int:
        line_height = line_height or font.get_linesize()
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        for index, line in enumerate(lines):
            image = font.render(line, True, color)
            self.screen.blit(image, (x, y + index * line_height))
        return len(lines) * line_height

    def panel(self, rect: pygame.Rect, color: tuple[int, int, int] = PANEL) -> None:
        pygame.draw.rect(self.screen, color, rect, border_radius=18)
        pygame.draw.rect(self.screen, OUTLINE, rect, width=1, border_radius=18)

    def draw_button(
        self,
        rect: pygame.Rect,
        label: str,
        *,
        hovered: bool = False,
        accent: tuple[int, int, int] = GOLD,
        enabled: bool = True,
    ) -> None:
        fill = (48, 61, 75) if not hovered else (59, 75, 91)
        if not enabled:
            fill = (38, 45, 54)
        pygame.draw.rect(self.screen, fill, rect, border_radius=11)
        border = accent if hovered and enabled else OUTLINE
        pygame.draw.rect(self.screen, border, rect, width=2 if hovered else 1, border_radius=11)
        text_color = INK if enabled else MUTED
        image = self.small_font.render(label, True, text_color)
        self.screen.blit(image, image.get_rect(center=rect.center))

    def draw_header(self, mouse: tuple[int, int]) -> None:
        pygame.draw.rect(self.screen, (16, 22, 31), (0, 0, WIDTH, 72))
        pygame.draw.circle(self.screen, GOLD, (39, 36), 17, width=2)
        pygame.draw.circle(self.screen, GOLD, (39, 36), 5)
        title = self.title_font.render("THE LAST DOOR", True, INK)
        self.screen.blit(title, (68, 15))
        subtitle = self.small_font.render("A little escape-room adventure", True, MUTED)
        self.screen.blit(subtitle, (70, 47))
        self.draw_button(self.restart_rect, "New run", hovered=self.restart_rect.collidepoint(mouse))
        self.draw_button(self.save_rect, "Save and quit", hovered=self.save_rect.collidepoint(mouse), accent=GREEN)

    def draw_scene_background(self, scene: pygame.Surface, room_name: str) -> None:
        top, floor, accent = ROOM_COLORS[room_name]
        width, height = scene.get_size()
        horizon = int(height * 0.72)
        for y in range(height):
            amount = y / max(1, horizon)
            color = blend(top, floor, min(amount, 1))
            if y > horizon:
                color = blend(floor, (20, 25, 32), (y - horizon) / max(1, height - horizon) * 0.35)
            pygame.draw.line(scene, color, (0, y), (width, y))
        pygame.draw.polygon(scene, blend(floor, (20, 25, 32), 0.22),
                            [(0, horizon), (width, horizon), (width, height), (0, height)])

        for x in range(0, width + 1, 96):
            pygame.draw.line(scene, blend(top, (255, 255, 255), 0.08), (x, 0), (x, horizon), 1)
        for y in range(42, horizon, 52):
            pygame.draw.line(scene, blend(top, (255, 255, 255), 0.07), (0, y), (width, y), 1)
        pygame.draw.line(scene, accent, (0, horizon), (width, horizon), 2)

    def draw_player(self, scene: pygame.Surface, x: int, y: int, now: float) -> None:
        bob = math.sin(now * 3.4) * 3
        y = int(y + bob)
        pygame.draw.ellipse(scene, (18, 23, 29), (x - 26, y + 67, 55, 14))
        pygame.draw.rect(scene, (119, 71, 51), (x - 28, y + 15, 13, 35), border_radius=6)
        pygame.draw.circle(scene, (195, 139, 100), (x, y), 15)
        pygame.draw.arc(scene, (44, 35, 33), (x - 15, y - 15, 30, 20), math.pi, math.tau, 7)
        pygame.draw.polygon(scene, (75, 126, 117), [(x - 15, y + 15), (x + 15, y + 15),
                                                    (x + 19, y + 53), (x - 18, y + 53)])
        pygame.draw.line(scene, (40, 45, 54), (x - 8, y + 53), (x - 11, y + 70), 8)
        pygame.draw.line(scene, (40, 45, 54), (x + 8, y + 53), (x + 11, y + 70), 8)
        pygame.draw.line(scene, (99, 67, 48), (x - 11, y + 70), (x - 20, y + 72), 7)
        pygame.draw.line(scene, (99, 67, 48), (x + 11, y + 70), (x + 21, y + 72), 7)
        pygame.draw.line(scene, (231, 179, 100), (x + 12, y + 24), (x + 18, y + 45), 5)
        pygame.draw.circle(scene, (241, 208, 142), (x - 5, y + 1), 2)

    def draw_start_room(self, scene: pygame.Surface, now: float) -> None:
        width, height = scene.get_size()
        pygame.draw.rect(scene, (75, 63, 58), (width - 205, 54, 135, 205), border_radius=7)
        pygame.draw.rect(scene, (32, 29, 31), (width - 188, 71, 101, 174), border_radius=4)
        pygame.draw.circle(scene, GOLD, (width - 94, 165), 5)
        pygame.draw.line(scene, (185, 117, 70), (width - 270, 56), (width - 270, 122), 4)
        flame = (255, 176 + int(22 * math.sin(now * 9)), 77)
        pygame.draw.polygon(scene, flame, [(width - 279, 119), (width - 270, 91),
                                           (width - 260, 119)])
        pygame.draw.rect(scene, (101, 80, 65), (width - 445, 178, 115, 101))
        pygame.draw.rect(scene, (53, 48, 44), (width - 455, 167, 135, 18), border_radius=4)
        pygame.draw.rect(scene, (75, 58, 46), (width - 440, 202, 105, 6))
        book_colors = [(178, 83, 61), (68, 121, 112), (209, 162, 91), (89, 102, 143)]
        for i, color in enumerate(book_colors):
            pygame.draw.rect(scene, color, (width - 434 + i * 24, 136, 18, 31), border_radius=2)
        scene.blit(self.small_font.render("KEY?", True, INK), (width - 428, 229))
        self.draw_player(scene, 118, 231, now)

    def draw_hallway(self, scene: pygame.Surface, now: float) -> None:
        width, height = scene.get_size()
        pygame.draw.polygon(scene, (29, 43, 52), [(205, 15), (width - 205, 15),
                                                   (width - 65, 265), (65, 265)])
        pygame.draw.polygon(scene, (80, 108, 111), [(width - 189, 30), (width - 100, 30),
                                                      (width - 122, 240), (width - 167, 240)])
        pygame.draw.rect(scene, (133, 158, 153), (width // 2 - 112, 90, 226, 92), border_radius=8)
        pygame.draw.rect(scene, (34, 54, 61), (width // 2 - 102, 100, 206, 72), border_radius=6)
        riddle = self.small_font.render("I speak without a mouth...", True, (203, 226, 217))
        scene.blit(riddle, riddle.get_rect(center=(width // 2, 134)))
        for x in (185, width - 190):
            pygame.draw.line(scene, (217, 155, 94), (x, 104), (x, 145), 4)
            pygame.draw.circle(scene, (255, 190, 104), (x, 147), 8 + int(2 * math.sin(now * 5 + x)))
        self.draw_player(scene, 114, 232, now)
        ghost_alpha = 90 + int(25 * math.sin(now * 2))
        ghost = pygame.Surface((63, 96), pygame.SRCALPHA)
        pygame.draw.circle(ghost, (179, 230, 236, ghost_alpha), (31, 24), 22)
        pygame.draw.polygon(ghost, (179, 230, 236, ghost_alpha),
                            [(9, 29), (53, 29), (61, 83), (46, 75), (32, 88), (18, 75), (2, 84)])
        scene.blit(ghost, (width - 285, 170))

    def draw_lab(self, scene: pygame.Surface, now: float, opened: bool) -> None:
        width, height = scene.get_size()
        for x in range(40, width, 105):
            pygame.draw.line(scene, (175, 208, 207), (x, 0), (x, 250), 1)
        pygame.draw.rect(scene, (79, 111, 125), (width - 175, 25, 100, 133), border_radius=8)
        pygame.draw.rect(scene, (135, 189, 196), (width - 164, 36, 78, 111), border_radius=4)
        for index in range(4):
            x = 225 + index * 132
            pygame.draw.rect(scene, (222, 230, 218), (x, 203, 90, 15), border_radius=4)
            pygame.draw.rect(scene, (95, 119, 121), (x + 8, 218, 9, 48))
            pygame.draw.rect(scene, (95, 119, 121), (x + 72, 218, 9, 48))
            color = ITEM_COLORS[("table_salt", "water", "sand", "apple_juice")[index]]
            pygame.draw.circle(scene, color, (x + 45, 190), 12)
            number = self.small_font.render(str(index + 1), True, (46, 64, 70))
            scene.blit(number, number.get_rect(center=(x + 45, 190)))
        pedestal_x = width - 280
        pygame.draw.rect(scene, (104, 119, 127), (pedestal_x, 190, 87, 74), border_radius=8)
        pygame.draw.ellipse(scene, (202, 214, 212), (pedestal_x + 12, 171, 63, 25))
        glow = 115 + int(35 * math.sin(now * 3)) if opened else 0
        pygame.draw.ellipse(scene, (181, 219, 207), (pedestal_x + 28, 135, 31, 42))
        pygame.draw.ellipse(scene, (111, 144, 143), (pedestal_x + 19, 157, 49, 14))
        if opened:
            pygame.draw.circle(scene, (246, 220, 129), (pedestal_x + 43, 153), 30, width=3)
            pygame.draw.ellipse(scene, (105, 76, 58), (310, 260, 155, 43))
            pygame.draw.ellipse(scene, (211, 165, 97), (338, 267, 100, 18), width=3)
            pygame.draw.circle(scene, (246, 220, 129, min(glow, 255)), (pedestal_x + 43, 153), 40, width=2)
        self.draw_player(scene, 111, 233, now)

    def draw_vault(self, scene: pygame.Surface, now: float, unlocked: bool) -> None:
        width, height = scene.get_size()
        door_rect = pygame.Rect(width - 275, 48, 187, 219)
        pygame.draw.rect(scene, (42, 55, 68), door_rect.inflate(12, 12), border_radius=13)
        door_color = (87, 132, 112) if unlocked else (87, 99, 111)
        pygame.draw.rect(scene, door_color, door_rect, border_radius=10)
        pygame.draw.rect(scene, (128, 147, 155), door_rect, width=4, border_radius=10)
        for inset in (18, 36):
            pygame.draw.rect(scene, blend(door_color, (14, 23, 33), 0.23),
                             door_rect.inflate(-inset * 2, -inset * 2), width=2, border_radius=7)
        if unlocked:
            light = 140 + int(30 * math.sin(now * 2))
            pygame.draw.rect(scene, (light, 214, 177), (door_rect.x + 54, door_rect.y + 38, 80, 147),
                             border_radius=6)
        keypad = pygame.Rect(door_rect.x - 65, door_rect.y + 87, 48, 78)
        pygame.draw.rect(scene, (29, 38, 47), keypad, border_radius=7)
        pygame.draw.rect(scene, GREEN if unlocked else (224, 94, 87), (keypad.x + 8, keypad.y + 9, 32, 13),
                         border_radius=3)
        for row in range(3):
            for col in range(3):
                pygame.draw.circle(scene, (156, 169, 173),
                                   (keypad.x + 13 + col * 11, keypad.y + 34 + row * 12), 3)
        scene.blit(self.small_font.render("2, 4, 8, 16, ...", True, (211, 215, 205)), (280, 72))
        self.draw_player(scene, 115, 232, now)

    def draw_ending_room(self, scene: pygame.Surface, room_name: str, now: float) -> None:
        width, height = scene.get_size()
        if room_name == "final_room":
            pygame.draw.rect(scene, (38, 55, 69), (width - 250, 27, 170, 190), border_radius=9)
            pygame.draw.rect(scene, (255, 216, 138), (width - 239, 38, 148, 168), border_radius=5)
            pygame.draw.line(scene, (168, 117, 75), (width - 165, 40), (width - 165, 204), 5)
            pygame.draw.line(scene, (168, 117, 75), (width - 237, 122), (width - 93, 122), 5)
            pygame.draw.circle(scene, (255, 245, 194), (width - 197, 78), 25)
            self.draw_player(scene, 185, 231, now)
            for x in range(370, 700, 70):
                pygame.draw.line(scene, (94, 130, 105), (x, 295), (x - 12, 260), 3)
                pygame.draw.circle(scene, (129, 158, 106), (x - 18, 270), 8)
        else:
            self.draw_player(scene, 160, 232, now)
            for i in range(7):
                x = 300 + i * 62
                y = 60 + (i * 43) % 180
                color = (232, 105 + i * 8, 79)
                pygame.draw.line(scene, color, (x, y), (x + 25, y + 45), 4)
                pygame.draw.circle(scene, (251, 203, 120), (x + 16, y + 58), 4)

    def draw_scene(self, rect: pygame.Rect) -> None:
        room_name = self.state["current_room"]
        now = time.monotonic()
        scene = pygame.Surface(rect.size)
        self.draw_scene_background(scene, room_name)
        if room_name == "start":
            self.draw_start_room(scene, now)
        elif room_name == "hallway":
            self.draw_hallway(scene, now)
        elif room_name == "lab":
            self.draw_lab(scene, now, "trapdoor_open" in self.state["flags"])
        elif room_name == "vault":
            self.draw_vault(scene, now, "vault_unlocked" in self.state["flags"])
        else:
            self.draw_ending_room(scene, room_name, now)

        if room_name in ("lab", "final_room"):
            for x, y, phase, size in self.particles:
                offset_y = (now * 20 + phase * 3) % 255
                px = int((x + now * (10 + size % 7)) % scene.get_width())
                py = int((y - offset_y) % scene.get_height())
                pygame.draw.circle(scene, (239, 215, 154), (px, py), 1 + size % 2)
        self.screen.blit(scene, rect.topleft)
        pygame.draw.rect(self.screen, OUTLINE, rect, width=2, border_radius=18)

    def draw_inventory_icon(self, item: str, center: tuple[int, int]) -> None:
        color = ITEM_COLORS.get(item, GOLD)
        x, y = center
        pygame.draw.circle(self.screen, (42, 54, 66), center, 18)
        pygame.draw.circle(self.screen, color, center, 18, width=1)
        if item == "brass_key":
            pygame.draw.circle(self.screen, color, (x - 5, y), 6, width=3)
            pygame.draw.line(self.screen, color, (x + 1, y), (x + 11, y), 4)
            pygame.draw.line(self.screen, color, (x + 8, y), (x + 8, y + 5), 3)
        elif item == "table_salt":
            pygame.draw.polygon(self.screen, color, [(x - 9, y + 7), (x - 6, y - 6),
                                                     (x + 7, y - 6), (x + 10, y + 7)])
            pygame.draw.line(self.screen, (255, 255, 255), (x - 5, y - 2), (x + 6, y - 2), 2)
        elif item == "water":
            pygame.draw.polygon(self.screen, color, [(x, y - 11), (x - 8, y + 1),
                                                     (x - 6, y + 7), (x, y + 10), (x + 7, y + 5)])
        elif item == "sand":
            pygame.draw.polygon(self.screen, color, [(x - 10, y + 7), (x - 5, y - 6),
                                                     (x + 5, y - 6), (x + 10, y + 7)])
            pygame.draw.line(self.screen, (240, 212, 157), (x - 5, y + 2), (x + 5, y + 2), 2)
        else:
            pygame.draw.rect(self.screen, color, (x - 8, y - 9, 16, 18), border_radius=3)
            pygame.draw.rect(self.screen, (255, 221, 175), (x - 5, y - 4, 10, 4), border_radius=2)

    def draw_sidebar(self, mouse: tuple[int, int]) -> None:
        sidebar = pygame.Rect(878, 90, 290, 692)
        self.panel(sidebar)
        title = self.heading_font.render("YOUR JOURNEY", True, INK)
        self.screen.blit(title, (900, 110))
        current_room = ROOM_NAMES.get(self.state["current_room"], "UNKNOWN")
        label = self.small_font.render(current_room, True, GOLD)
        self.screen.blit(label, (901, 150))

        self.screen.blit(self.font.render("INVENTORY", True, INK), (901, 194))
        pygame.draw.line(self.screen, OUTLINE, (900, 220), (1145, 220), 1)
        if self.state["inventory"]:
            for index, item in enumerate(self.state["inventory"]):
                y = 251 + index * 55
                self.draw_inventory_icon(item, (920, y))
                name = ITEM_NAMES.get(item, item.replace("_", " ").title())
                self.screen.blit(self.small_font.render(name, True, INK), (949, y - 8))
                self.screen.blit(self.small_font.render("Collected", True, MUTED), (949, y + 9))
        else:
            self.draw_text("Your pockets are empty. Search the room for useful things.",
                           self.small_font, MUTED, 902, 241, 230, 23)

        map_y = 500
        self.screen.blit(self.font.render("ESCAPE ROUTE", True, INK), (901, map_y))
        pygame.draw.line(self.screen, OUTLINE, (900, map_y + 27), (1145, map_y + 27), 1)
        route = [("start", "Stone cell"), ("hallway", "Echo hall"), ("lab", "Alchemy lab"),
                 ("vault", "Hidden vault"), ("final_room", "Daylight")]
        visited = {
            "start": True,
            "hallway": self.state["current_room"] in ("hallway", "lab", "lab_explosion", "vault", "lockdown", "final_room"),
            "lab": self.state["current_room"] in ("lab", "lab_explosion", "vault", "lockdown", "final_room"),
            "vault": self.state["current_room"] in ("vault", "lockdown", "final_room"),
            "final_room": self.state["current_room"] == "final_room",
        }
        for index, (room_key, room_label) in enumerate(route):
            y = map_y + 56 + index * 28
            color = GREEN if visited[room_key] else (86, 97, 108)
            pygame.draw.circle(self.screen, color, (910, y + 6), 5)
            if index < len(route) - 1:
                pygame.draw.line(self.screen, OUTLINE, (910, y + 12), (910, y + 29), 2)
            self.screen.blit(self.small_font.render(room_label, True, color if visited[room_key] else MUTED),
                             (927, y - 2))
        self.draw_button(self.new_run_rect, "Start a new run", hovered=self.new_run_rect.collidepoint(mouse),
                         accent=RED)

    def draw_main_panels(self, mouse: tuple[int, int]) -> None:
        scene_rect = pygame.Rect(32, 90, 820, 368)
        self.draw_scene(scene_rect)
        room_name = ROOM_NAMES.get(self.state["current_room"], "ESCAPE ROOM")
        room_label = self.heading_font.render(room_name, True, INK)
        badge_rect = pygame.Rect(50, 105, room_label.get_width() + 30, 44)
        pygame.draw.rect(self.screen, (21, 28, 37), badge_rect, border_radius=10)
        self.screen.blit(room_label, (badge_rect.x + 14, badge_rect.y + 7))

        description_rect = pygame.Rect(32, 476, 820, 116)
        self.panel(description_rect)
        description = game.get_description(game.ROOMS[self.state["current_room"]], self.state)
        self.draw_text(description, self.body_font, INK, 54, 495, 775, 28)

        action_rect = pygame.Rect(32, 610, 820, 172)
        self.panel(action_rect)
        room = game.ROOMS[self.state["current_room"]]
        if room.get("ending"):
            message = "You escaped. The outside world is waiting." if room["ending"] == "win" else "The room has fallen silent. Start a new run to try again."
            self.draw_text(message, self.body_font, GOLD if room["ending"] == "win" else RED,
                           54, 635, 770, 28)
            return

        self.screen.blit(self.font.render("WHAT WILL YOU DO?", True, INK), (54, 624))
        self.choice_rects = []
        choices = self.room_choices()
        for index, (label, _) in enumerate(choices):
            col = index % 2
            row = index // 2
            x = 52 + col * 386
            y = 658 + row * 39
            rect = pygame.Rect(x, y, 372, 33)
            self.choice_rects.append((rect, label))
            display_label = label.replace("_", " ").title()
            self.draw_button(rect, display_label, hovered=rect.collidepoint(mouse))

    def draw_toast(self) -> None:
        if time.monotonic() > self.toast_until:
            return
        width = min(780, max(260, self.font.size(self.toast)[0] + 42))
        rect = pygame.Rect((WIDTH - width) // 2, HEIGHT - 62, width, 42)
        pygame.draw.rect(self.screen, (20, 27, 37), rect, border_radius=12)
        pygame.draw.rect(self.screen, OUTLINE, rect, width=1, border_radius=12)
        color = RED if "Could not" in self.toast or "failed" in self.toast.lower() else INK
        text = self.font.render(self.toast, True, color)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def draw_puzzle_dialog(self) -> None:
        if self.puzzle_dialog is None:
            return
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((5, 9, 14, 185))
        self.screen.blit(shade, (0, 0))
        rect = pygame.Rect(270, 255, 660, 300)
        self.panel(rect, PANEL_LIGHT)
        puzzle = self.puzzle_dialog["data"]
        heading = self.heading_font.render("SOLVE THE PUZZLE", True, GOLD)
        self.screen.blit(heading, heading.get_rect(center=(WIDTH // 2, 294)))
        self.draw_text(puzzle["prompt"], self.body_font, INK, 310, 326, 580, 26)
        entry = pygame.Rect(310, 387, 580, 51)
        pygame.draw.rect(self.screen, (18, 25, 34), entry, border_radius=10)
        pygame.draw.rect(self.screen, GOLD, entry, width=2, border_radius=10)
        shown = self.puzzle_text or "Type your answer here..."
        color = INK if self.puzzle_text else MUTED
        image = self.font.render(shown[-65:], True, color)
        self.screen.blit(image, (entry.x + 14, entry.y + 15))
        if self.puzzle_feedback:
            self.draw_text(self.puzzle_feedback, self.small_font, RED, 310, 450, 580, 22)
        else:
            self.screen.blit(self.small_font.render("Enter submits  •  Esc cancels", True, MUTED), (310, 450))
        attempts = self.state["attempts"].get(puzzle["id"], 0)
        remaining = max(0, puzzle["max_attempts"] - attempts)
        self.screen.blit(self.small_font.render(f"Attempts remaining: {remaining}", True, MUTED),
                         (310, 492))
        cancel = pygame.Rect(735, 495, 155, 38)
        self.draw_button(cancel, "Cancel", accent=OUTLINE)

    def draw_restart_confirmation(self) -> None:
        if not self.confirm_restart:
            return
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((5, 9, 14, 185))
        self.screen.blit(shade, (0, 0))
        rect = pygame.Rect(340, 300, 520, 200)
        self.panel(rect, PANEL_LIGHT)
        title = self.heading_font.render("Start a new run?", True, INK)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 344)))
        detail = self.small_font.render("Your current progress will be replaced.", True, MUTED)
        self.screen.blit(detail, detail.get_rect(center=(WIDTH // 2, 379)))
        no_rect = pygame.Rect(440, 425, 140, 42)
        yes_rect = pygame.Rect(620, 425, 140, 42)
        self.draw_button(no_rect, "Keep playing", accent=OUTLINE)
        self.draw_button(yes_rect, "Start over", accent=RED)

    def draw(self) -> None:
        self.screen.fill((13, 18, 26))
        mouse = pygame.mouse.get_pos()
        self.draw_header(mouse)
        self.draw_main_panels(mouse)
        self.draw_sidebar(mouse)
        self.draw_toast()
        self.draw_puzzle_dialog()
        self.draw_restart_confirmation()
        pygame.display.flip()

    def restart(self) -> None:
        self.state = game.new_state()
        self.confirm_restart = False
        self.puzzle_dialog = None
        if self.save():
            self.notify("New run started.")

    def close(self) -> None:
        pygame.quit()

    def handle_click(self, position: tuple[int, int]) -> bool:
        if self.confirm_restart:
            if pygame.Rect(440, 425, 140, 42).collidepoint(position):
                self.confirm_restart = False
            elif pygame.Rect(620, 425, 140, 42).collidepoint(position):
                self.restart()
            else:
                self.confirm_restart = False
            return False

        if self.puzzle_dialog is not None:
            if pygame.Rect(735, 495, 155, 38).collidepoint(position):
                self.puzzle_dialog = None
                self.puzzle_text = ""
            else:
                self.submit_puzzle()
            return False

        if self.save_rect.collidepoint(position):
            if self.save(show_success=True):
                return True
            return False
        if self.restart_rect.collidepoint(position) or self.new_run_rect.collidepoint(position):
            self.confirm_restart = True
            return False
        for rect, label in self.choice_rects:
            if rect.collidepoint(position):
                self.choose(label)
                break
        return False

    def run(self) -> None:
        running = True
        while running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.close()
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.handle_click(event.pos):
                        running = False
                elif event.type == pygame.KEYDOWN:
                    if self.confirm_restart:
                        if event.key == pygame.K_ESCAPE:
                            self.confirm_restart = False
                        elif event.key in (pygame.K_RETURN, pygame.K_y):
                            self.restart()
                        elif event.key == pygame.K_n:
                            self.confirm_restart = False
                    elif self.puzzle_dialog is not None:
                        if event.key == pygame.K_ESCAPE:
                            self.puzzle_dialog = None
                            self.puzzle_text = ""
                        elif event.key == pygame.K_RETURN:
                            self.submit_puzzle()
                        elif event.key == pygame.K_BACKSPACE:
                            self.puzzle_text = self.puzzle_text[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if len(self.puzzle_text) < 120:
                                self.puzzle_text += event.unicode
                    elif event.key == pygame.K_ESCAPE:
                        self.confirm_restart = True
            self.draw()
        self.close()


def main() -> None:
    try:
        EscapeRoomUI().run()
    except pygame.error as exc:
        pygame.quit()
        raise SystemExit(f"Could not start the Pygame window: {exc}") from exc


if __name__ == "__main__":
    main()
