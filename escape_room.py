import os
import json

# --- 1. SETUP & PATHS ---
try:
    import importlib
    drive = importlib.import_module("google.colab").drive
except (ImportError, AttributeError):
    drive = None

SAVE_DIR = os.path.join(os.getcwd(), "escape_room_save")
if drive is not None:
    try:
        drive.mount('/content/drive')
        SAVE_DIR = "/content/drive/MyDrive/escape_room_save"
    except Exception as e:
        print("Could not mount Drive, proceeding with local folder fallback:", e)

os.makedirs(SAVE_DIR, exist_ok=True)
SAVE_FILE = os.path.join(SAVE_DIR, "save.json")

# --- 2. GAME DATA ---
ROOMS = {
    "start": {
        "description": "You wake up on a cold stone floor. A locked door is to the North. "
                       "A dusty bookshelf stands against a wall.",
        "variants": [
            {"requires_item": "brass_key",
             "description": "The bookshelf has been searched, its books lying scattered. "
                            "The brass key in your hand fits the locked door to the North."}
        ],
        "choices": {
            "look at bookshelf": {"result": "A key falls out of a book! You pick it up.",
                                  "give_item": "brass_key", "next": "start"},
            "go north": {"result": "The key turns and the door swings open. You step through.",
                         "requires_item": "brass_key", "next": "hallway",
                         "fail_result": "The door won't budge. It's locked."},
        }
    },
    "hallway": {
        "description": "A narrow hallway. A riddle is carved into a wall: "
                       "'I speak without a mouth. What am I?'",
        "choices": {
            "answer echo": {"result": "A wall slides open, revealing a bright laboratory.",
                            "next": "lab"},
            "answer ghost": {"result": "Nothing happens. Wrong answer.", "next": "hallway"},
        }
    },
    "lab": {
        "description": "A bright, spotless laboratory. Four tables stand in a row, numbered 1 to 4. "
                       "In the middle of the room, a silver chalice sits on a stone pedestal, "
                       "engraved with a warning: 'THREE FAILED MIXTURES WILL BE YOUR LAST.' "
                       "A crumpled note on the floor reads: 'S,W,A,T'.",
        "variants": [
            {"requires_flag": "trapdoor_open",
             "description": "The silver chalice glows softly. In the floor, a trap door has slid "
                            "into view, an iron ring set into its lid. The note on the floor "
                            "still reads: 'S,W,A,T'."}
        ],
        "choices": {
            "inspect table 1": {"result": "On table 1 you find a jar of table salt. You take it.",
                                "give_item": "table_salt", "next": "lab"},
            "inspect table 2": {"result": "On table 2 you find a jug of water. You take it.",
                                "give_item": "water", "next": "lab"},
            "inspect table 3": {"result": "On table 3 you find a bag full of sand. You take it.",
                                "give_item": "sand", "next": "lab"},
            "inspect table 4": {"result": "On table 4 you find an apple juice box. You take it.",
                                "give_item": "apple_juice", "next": "lab"},
            "pour into chalice": {
                "puzzle": {
                    "id": "lab_chalice",
                    "answer": ["sand", "water", "apple_juice", "table_salt"],
                    "aliases": {
                        "sand": ["sand", "s"],
                        "water": ["water", "w"],
                        "apple_juice": ["apple juice", "juice", "apple", "a"],
                        "table_salt": ["table salt", "salt", "t"],
                    },
                    "max_attempts": 3,
                    "missing": "You stare at the chalice, but you don't have everything you need yet.",
                    "prompt": "In what order do you pour the items into the chalice? Separate them with commas.",
                    "failure": "The liquid fizzes, turns a murky brown, and drains away. "
                               "The chalice is empty again. Maybe the order matters.",
                    "lockout": "The mixture turns an angry red and begins to shake. The chalice "
                               "cracks, and the warning on its side comes true.",
                    "success": "The mixture swirls and glows gold. Stone grinds against stone as a "
                               "trap door slides into view in the floor.",
                    "done": "The chalice is already glowing. There's nothing more to pour.",
                    "sets_flag": "trapdoor_open",
                    "lose_room": "lab_explosion",
                },
            },
            "open trap door": {"result": "You heave the trap door open and climb down a ladder "
                                         "into a cold stone vault.",
                               "shown_if_flag": "trapdoor_open", "next": "vault"},
        }
    },
    "lab_explosion": {
        "description": "The chalice bursts in a blinding flash. The blast hurls you across the lab, "
                       "glass raining down around you as the lights go out. When the smoke clears, "
                       "the tables are splinters and the way back is buried under rubble.",
        "choices": {}, 
        "ending": "lose"
    },
    "vault": {
        "description": "A cold stone vault. A heavy steel door fills the far wall, with a keypad "
                       "beside it that takes a two-digit number. A red label warns: 'THREE WRONG "
                       "CODES TRIGGER LOCKDOWN.' Chalked on the wall above the keypad: "
                       "'2, 4, 8, 16, ...'",
        "variants": [
            {"requires_flag": "vault_unlocked",
             "description": "The keypad glows green and the heavy steel door stands open, daylight "
                            "streaming through. The chalked sequence on the wall still reads: "
                            "'2, 4, 8, 16, ...'"}
        ],
        "choices": {
            "enter code": {
                "code_puzzle": {
                    "id": "vault_keypad",
                    "answer": "32",
                    "max_attempts": 3,
                    "prompt": "The keypad glows, waiting for a two-digit number.",
                    "success": "The keypad chimes, the lock clunks, and the steel door swings open.",
                    "failure": "BZZT. The keypad flashes red.",
                    "lockout": "BZZT. The keypad screams, and the label's warning comes true.",
                    "done": "The keypad is already glowing green. The door is open.",
                    "sets_flag": "vault_unlocked",
                    "lose_room": "lockdown",
                },
            },
            "open steel door": {"result": "You step through the open door into blinding daylight.",
                               "shown_if_flag": "vault_unlocked", "next": "final_room"},
        }
    },
    "lockdown": {
        "description": "Red lights flash and steel shutters slam over the ladder behind you. "
                       "Vents in the ceiling hiss, filling the vault with a sweet-smelling gas. "
                       "Your knees buckle and the floor rushes up to meet you. Nobody ever finds "
                       "the vault again.",
        "choices": {},
        "ending": "lose"
    },
    "final_room": {
        "description": "Sunlight pours in from an open window. You've escaped!",
        "choices": {},
        "ending": "win"
    }
}
STARTING_ROOM = "start"

# --- 3. SAVE / LOAD FUNCTIONS ---
def save_game(state):
    os.makedirs(SAVE_DIR, exist_ok=True)
    tmp = SAVE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, SAVE_FILE)

def normalize_state(state):
    if not isinstance(state, dict):
        return None

    current_room = state.get("current_room")
    if current_room not in ROOMS:
        return None

    inventory = state.get("inventory", [])
    flags = state.get("flags", [])
    attempts = state.get("attempts", {})
    if not isinstance(inventory, list):
        inventory = []
    if not isinstance(flags, list):
        flags = []
    if not isinstance(attempts, dict):
        attempts = {}

    attempts = {
        puzzle_id: attempt_count
        for puzzle_id, attempt_count in attempts.items()
        if isinstance(puzzle_id, str)
        and isinstance(attempt_count, int)
        and not isinstance(attempt_count, bool)
        and attempt_count >= 0
    }

    return {
        "version": 1,
        "current_room": current_room,
        "inventory": [item for item in inventory if isinstance(item, str)],
        "flags": [flag for flag in flags if isinstance(flag, str)],
        "attempts": attempts,
    }

def load_game():
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            return normalize_state(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None

def new_state():
    return {
        "version": 1,
        "current_room": STARTING_ROOM,
        "inventory": [],
        "flags": [],
        "attempts": {},
    }

# --- 4. GAME MECHANICS ---
def get_description(room, state):
    text = room["description"]
    for variant in room.get("variants", []):
        has_item = "requires_item" not in variant or variant["requires_item"] in state["inventory"]
        has_flag = "requires_flag" not in variant or variant["requires_flag"] in state.get("flags", [])
        if has_item and has_flag:
            text = variant["description"]
    return text

def run_puzzle(puzzle, state):
    flag = puzzle["sets_flag"]
    if flag in state["flags"]:
        print(puzzle["done"])
        return None

    missing = [item for item in puzzle["answer"] if item not in state["inventory"]]
    if missing:
        print(puzzle["missing"])
        return None

    lookup = {}
    for item, names in puzzle["aliases"].items():
        for name in names:
            lookup[name] = item

    print(puzzle["prompt"])
    raw = input("> ").strip().lower()
    parts = [p.strip() for p in raw.split(",") if p.strip()]

    if not parts:
        print("You decide not to pour anything yet. No attempt used.")
        return None

    order = []
    for part in parts:
        if part not in lookup:
            print(f"You're not sure what '{part}' means here, so you pour nothing. No attempt used.")
            return None
        order.append(lookup[part])

    if order == puzzle["answer"]:
        print(puzzle["success"])
        state["flags"].append(flag)
        return None

    attempts = state["attempts"].get(puzzle["id"], 0) + 1
    state["attempts"][puzzle["id"]] = attempts
    remaining = puzzle["max_attempts"] - attempts

    if remaining <= 0:
        print(puzzle["lockout"])
        return puzzle["lose_room"]

    print(puzzle["failure"])
    print(f"Attempts left: {remaining}")
    return None

def run_code_puzzle(puzzle, state):
    flag = puzzle["sets_flag"]
    if flag in state["flags"]:
        print(puzzle["done"])
        return None

    print(puzzle["prompt"])
    guess = input("> ").strip()

    if not guess.isdigit():
        print("The keypad only accepts digits. No attempt used.")
        return None

    if guess == puzzle["answer"]:
        print(puzzle["success"])
        state["flags"].append(flag)
        return None

    attempts = state["attempts"].get(puzzle["id"], 0) + 1
    state["attempts"][puzzle["id"]] = attempts
    remaining = puzzle["max_attempts"] - attempts

    if remaining <= 0:
        print(puzzle["lockout"])
        return puzzle["lose_room"]

    print(puzzle["failure"])
    print(f"Attempts left: {remaining}")
    return None

# --- 5. CORE GAME LOOP ---
def play(state):
    state.setdefault("inventory", [])
    state.setdefault("flags", [])
    state.setdefault("attempts", {})
    last_seen = None
    while True:
        room = ROOMS[state["current_room"]]
        room_choices = {k.lower(): v for k, v in room["choices"].items()
                        if "shown_if_flag" not in v or v["shown_if_flag"] in state["flags"]}
        description = get_description(room, state)

        if (state["current_room"], description) != last_seen:
            print("\n" + description)
            last_seen = (state["current_room"], description)

        if not room["choices"]:
            if room.get("ending") == "win":
                print("\nYou escaped! Congratulations.")
            else:
                print("\nGAME OVER.")
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
            return

        print("Choices:", ", ".join(room_choices.keys()), "| 'look' to re-read the room | 'save' to save and quit")
        action = input("> ").strip().lower()

        if action == "save":
            save_game(state)
            print("Game saved. See you next time!")
            return

        if action == "look":
            print("\n" + description)
            continue

        if action not in room_choices:
            print("You can't do that here.")
            continue

        choice = room_choices[action]

        if "requires_item" in choice and choice["requires_item"] not in state["inventory"]:
            print(choice.get("fail_result", "You can't do that yet."))
            continue

        if "puzzle" in choice:
            lose_room = run_puzzle(choice["puzzle"], state)
            if lose_room:
                state["current_room"] = lose_room
            save_game(state)
            continue

        if "code_puzzle" in choice:
            lose_room = run_code_puzzle(choice["code_puzzle"], state)
            if lose_room:
                state["current_room"] = lose_room
            save_game(state)
            continue

        if "give_item" in choice and choice["give_item"] in state["inventory"]:
            print("You already took that.")
        else:
            print(choice["result"])
            if "give_item" in choice:
                item = choice["give_item"]
                state["inventory"].append(item)
                print(f"You now have: {item.replace('_', ' ')}")

        state["current_room"] = choice["next"]
        save_game(state)

# --- 6. ENTRY POINT ---
def main():
    state = load_game()
    if state:
        print(f"Welcome back! You are in: {state['current_room']}")
    else:
        state = new_state()
        print("You wake up in an unfamiliar room...")
    play(state)

if __name__ == '__main__':
    main()
