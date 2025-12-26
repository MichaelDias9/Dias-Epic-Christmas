from flask import Flask, render_template, jsonify, request, abort
import random

app = Flask(__name__)

# --- Configuration ---
PLAYERS = [
    "Adriana",
    "Aidan",
    "Amilia",
    "Brandur",
    "Cody",
    "Francisca",
    "Marissa",
    "Michael",
    "Ndidi",
    "Nuno",
    "Olivia",
    "Selina"
] # There are currently 12 cousins

# The number of steps MUST match the number of cousins!
GAME_STEPS = [
    {
        "id": "1", # QR code should point to /found/1
        "word_type": "Place",
        "hint": "Look closely where the stockings are hung..."
    },
    {
        "id": "2", # QR code should point to /found/2
        "word_type": "Noun (Plural)",
        "hint": "Search around the refrigerator..."
    },
    {
        "id": "3", # QR code should point to /found/3
        "word_type": "Verb (Past Tense)",
        "hint": "Check under the most comfortable pillow in the house!"
    }
]

# Startup Validation
if len(PLAYERS) != len(GAME_STEPS):
    raise ValueError(f"Configuration Error: You have {len(PLAYERS)} cousins but {len(GAME_STEPS)} game steps. They must be equal!")

# --- Game State ---
class GameState:
    def __init__(self):
        self.current_step_index = 0
        '''
        Phases:
        - 'WELCOME': Waiting for first interaction (conceptually, though server starts ready)
        - 'INPUT': Waiting for a word to be submitted.
        - 'HINT': Word submitted, showing hint, waiting for QR scan.
        - 'COMPLETED': All steps done.
        '''
        self.phase = 'INPUT' 
        self.collected_words = [] # List of {'cousin': name, 'type': type, 'word': word}
        
        # Randomize cousins for this game session
        self.cousin_order = list(PLAYERS)
        random.shuffle(self.cousin_order)

state = GameState()

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Returns the full game state for clients to sync."""
    if state.current_step_index >= len(GAME_STEPS):
        return jsonify({
            'phase': 'COMPLETED',
            'results': state.collected_words
        })

    current_step = GAME_STEPS[state.current_step_index]
    current_step = GAME_STEPS[state.current_step_index]
    # Use the randomized order
    current_cousin = state.cousin_order[state.current_step_index] if state.current_step_index < len(state.cousin_order) else "Unknown"
    
    return jsonify({
        'phase': state.phase,
        'step_number': state.current_step_index + 1,
        'total_steps': len(GAME_STEPS),
        'current_cousin': current_cousin,
        'word_type': current_step['word_type'],
        'hint': current_step['hint'],
        # If in HINT phase, we might want to show the last submitted word
        'last_word': state.collected_words[-1]['word'] if state.collected_words else None
    })

@app.route('/api/submit_word', methods=['POST'])
def submit_word():
    """Accepts a word submission."""
    if state.phase != 'INPUT':
        return jsonify({'error': 'Not in input phase'}), 400
        
    word = request.json.get('word')
    if not word:
        return jsonify({'error': 'No word provided'}), 400

    # Record the word
    current_cousin = state.cousin_order[state.current_step_index]
    current_step = GAME_STEPS[state.current_step_index]
    
    state.collected_words.append({
        'cousin': current_cousin,
        'type': current_step['word_type'],
        'word': word
    })
    
    # Advance phase
    state.phase = 'HINT'
    
    return jsonify({'success': True})

@app.route('/found/<step_id>')
def foundation_found(step_id):
    """Called when a QR code is scanned."""
    try:
        scanned_id_int = int(step_id)
        # Current step is 0-indexed in state, so adding 1 gives the 1-based ID we are looking for.
        # Example: If index=0 (Step 1), we are looking for QR "1".
        current_target_id = state.current_step_index + 1
    except ValueError:
        return render_template('index.html', auto_join=True)

    # 1. Check if they scanned a future step
    if scanned_id_int > current_target_id:
        return render_template('wrong_step.html', 
                               scanned_id=scanned_id_int, 
                               current_step=current_target_id)

    # 2. Check if it's the correct step (or a past one which we just treat as a 'join')
    # If we are in HINT phase and scan the current target -> Advance
    if state.phase == 'HINT' and scanned_id_int == current_target_id:
        state.current_step_index += 1
        # Check for completion
        if state.current_step_index >= len(GAME_STEPS):
            state.phase = 'COMPLETED'
        else:
            state.phase = 'INPUT'
        return render_template('index.html', auto_join=True)
    
    # Otherwise (e.g. scanned correct one while in INPUT phase, or scanned an old one),
    # just redirect to the game.
    return render_template('index.html', auto_join=True)

@app.route('/reset')
def reset_game():
    """Debug route to reset the game."""
    global state
    state = GameState()
    return "Game Reset"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
