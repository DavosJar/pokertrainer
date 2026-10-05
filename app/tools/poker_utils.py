import random
import hashlib
from typing import List, Dict, Any, Tuple, Set

RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
SUITS = [
    {"suit": "s", "symbol": "♠", "name": "spades", "color": "#1E293B", "textColor": "#FFFFFF"},
    {"suit": "h", "symbol": "♥", "name": "hearts", "color": "#EF4444", "textColor": "#FFFFFF"},
    {"suit": "d", "symbol": "♦", "name": "diamonds", "color": "#3B82F6", "textColor": "#FFFFFF"},
    {"suit": "c", "symbol": "♣", "name": "clubs", "color": "#10B981", "textColor": "#FFFFFF"}
]

def get_169_hands() -> List[str]:
    hands = []
    # 13x13 matrix order: row i, col j
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i == j:
                hands.append(f"{r1}{r2}")
            elif i < j:
                hands.append(f"{r1}{r2}s")
            else:
                hands.append(f"{r2}{r1}o")
    return hands

ALL_169_HANDS = get_169_hands()
ALL_169_HANDS_SET = set(ALL_169_HANDS)

def get_matrix_grid() -> List[List[str]]:
    """Returns a 13x13 grid where row i, col j is the hand notation."""
    grid = []
    for i, r1 in enumerate(RANKS):
        row = []
        for j, r2 in enumerate(RANKS):
            if i == j:
                row.append(f"{r1}{r2}")
            elif i < j:
                row.append(f"{r1}{r2}s")
            else:
                row.append(f"{r2}{r1}o")
        grid.append(row)
    return grid

MATRIX_GRID = get_matrix_grid()

def parse_hand_ranks(hand: str) -> Tuple[str, str, str]:
    """Returns (rank1, rank2, hand_type where hand_type is 'pair', 'suited', 'offsuit')"""
    if len(hand) == 2:
        return hand[0], hand[1], "pair"
    elif len(hand) == 3:
        if hand[2] == 's':
            return hand[0], hand[1], "suited"
        elif hand[2] == 'o':
            return hand[0], hand[1], "offsuit"
    raise ValueError(f"Invalid poker hand format: {hand}")

def generate_visual_cards(hand: str) -> List[Dict[str, Any]]:
    """
    Generates 2 visual card objects for rendering realistic cards on screen.
    Uses a standard 4-color poker deck (Spades=black, Hearts=red, Diamonds=blue, Clubs=green).
    """
    r1, r2, htype = parse_hand_ranks(hand)
    seed = int(hashlib.sha1(hand.encode('utf-8')).hexdigest()[:8], 16)
    rng = random.Random(seed)
    suits_pool = list(SUITS)
    rng.shuffle(suits_pool)

    if htype == "pair":
        s1 = suits_pool[0]
        s2 = suits_pool[1]
    elif htype == "suited":
        s1 = suits_pool[0]
        s2 = suits_pool[0]
    else:  # offsuit
        s1 = suits_pool[0]
        s2 = suits_pool[1]

    return [
        {
            "rank": r1,
            "suit": s1["suit"],
            "symbol": s1["symbol"],
            "name": s1["name"],
            "color": s1["color"],
            "textColor": s1["textColor"]
        },
        {
            "rank": r2,
            "suit": s2["suit"],
            "symbol": s2["symbol"],
            "name": s2["name"],
            "color": s2["color"],
            "textColor": s2["textColor"]
        }
    ]

def find_borderline_hands(hands_dict: Dict[str, Dict[str, Any]]) -> Set[str]:
    """
    Finds hands that are on the border of ranges:
    A hand is borderline if any of its 8 neighbors in the 13x13 grid has a different action
    (e.g., OR vs FOLD, or OPEN_SHOVE vs OR).
    """
    borderline = set()
    grid = MATRIX_GRID

    for r in range(13):
        for c in range(13):
            hand = grid[r][c]
            info = hands_dict.get(hand, {})
            current_action = info.get("action") if isinstance(info, dict) else getattr(info, "action", None)

            # Check neighbors
            is_border = False
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 13 and 0 <= nc < 13:
                        neighbor_hand = grid[nr][nc]
                        n_info = hands_dict.get(neighbor_hand, {})
                        n_action = n_info.get("action") if isinstance(n_info, dict) else getattr(n_info, "action", None)
                        if n_action != current_action:
                            is_border = True
                            break
                if is_border:
                    break

            if is_border:
                borderline.add(hand)

    return borderline
