from flask import Flask, render_template, jsonify, request, abort

import random
import os
import threading
from openai import OpenAI

app = Flask(__name__)

# --- Configuration ---
PLAYERS = [
    "Adriana",
    "Aidan",
    "Amilia",
    "Brandur",
    "Cody",
    #"Francisca",
    #"Marissa",
    #"Michael",
    #"Ndidi",
    #"Nuno",
    #"Olivia",
    #"Selina"
] # There are currently 12 cousins  

# Validated Game Steps
GAME_STEPS = [
    {
        "id": "1", # QR code should point to /found/1
        "inputs": [
            {"label": "Type of Vehicle", "type": "Vehicle"},
            {"label": "Three Items from House", "type": "Items"},
            {"label": "A Place", "type": "Place"}
        ],
        "hint": "Look closely where the stockings are hung...",
        "story_guidance": "ESTABLISH_PREMISE"
    },
    {
        "id": "2", # QR code should point to /found/2
        "inputs": [
            {"label": "Noun (Plural)", "type": "Noun (Plural)"}
        ],
        "hint": "Search around the refrigerator..."
    },
    {
        "id": "3", # QR code should point to /found/3
        "inputs": [
             {"label": "Verb (Past Tense)", "type": "Verb (Past Tense)"}
        ],
        "hint": "Check under the most comfortable pillow in the house!"
    },
  
]

# Startup Validation
total_inputs = sum(len(step['inputs']) for step in GAME_STEPS)
if len(PLAYERS) != total_inputs:
    print(f"\n{'!'*40}")
    print(f"WARNING: PLAYER/INPUT MISMATCH")
    print(f"You have {len(PLAYERS)} cousins but {total_inputs} total inputs defined.")
    print(f"Some cousins may not get a turn, or we may run out of cousins!")
    print(f"{'!'*40}\n")
else:
    print(f"\nSUCCESS: {len(PLAYERS)} cousins matches {total_inputs} inputs perfectly.\n")

SYSTEM_CONTEXT = (
    "You are a christmas story writer coming up with a fun story about the Dias cousins going on an epic mission to the North Pole to find the true meaning of Christmas. "
    "The real life Dias cousins are non-fictional and are the audience that your writing the story for. The story is fictional, and includes the Dias cousins as characters. "
    "As you write the story, you will be taking input from the non-fictional cousins in an interactive way where they suggest plot points and key words to weave into the story. "
    "The high level goal of the story is to use irony and satire to make a point about how presents are not the most important part of Christmas. "
    "Along the way in the story, the cousins will encounter characters, situations, or events that will allude to the importance of values like kindness, family, togetherness, and other virtues associated with Christmas "
    "TONE: Warm, silly, magical, clever, and ironic." 
    "As the story gets to the climax, the 'True Meaning of Christmas' will ironically be revealed to be just PRESENTS (materialism)."
    "Don't be explicit about mentioning the irony/satire of the story. Cleverly weave it into the story in a way that it explains itself."
    "Make the cousins feel like heroes on an noble quest. "
    "You know the cousins' names are: {PLAYERS}."
)

# --- Game State ---
class GameState:
    def __init__(self):
        self.current_step_index = 0
        '''
        Phases:
        - 'WELCOME': Waiting for first interaction (conceptually, though server starts ready)
        - 'INPUT': Waiting for inputs to be filled and approved.
        - 'HINT': All inputs approved, showing hint, waiting for QR scan.
        - 'COMPLETED': All steps done.
        '''
        self.phase = 'INPUT' 
        self.collected_words = [] # List of {'cousin': name, 'type': type, 'word': word}
        
        # Parallel Input State
        # List of {'index': int, 'label': str, 'type': str, 'value': str, 'cousin': str}
        self.step_input_states = [] 
        
        # Story Generation State
        self.story_segments = [] # List of strings, each is a part of the story
        self.latest_segment = "" # The most recently generated part
        self.is_generating_story = False # Flag for UI loading state
        
        # Randomize cousins for this game session
        self.cousin_order = list(PLAYERS)
        random.shuffle(self.cousin_order)
        
        # Initialize first step inputs
        self.initialize_step_inputs()
    
    def initialize_step_inputs(self):
        """Prepares the input slots for the current step."""
        if self.current_step_index >= len(GAME_STEPS):
            self.step_input_states = []
            return

        current_step = GAME_STEPS[self.current_step_index]
        new_states = []
        
        # Calculate offset to assign cousins correctly
        passed_steps_inputs = sum(len(step['inputs']) for step in GAME_STEPS[:self.current_step_index])
        
        for i, input_def in enumerate(current_step['inputs']):
            total_index = passed_steps_inputs + i
            cousin_name = self.cousin_order[total_index] if total_index < len(self.cousin_order) else "Elf Helper"
            
            new_states.append({
                'index': i,
                'label': input_def['label'],
                'type': input_def['type'],
                'value': "", # Start empty
                'cousin': cousin_name
            })
        
        self.step_input_states = new_states

state = GameState()

def generate_segment_task(new_inputs, story_guidance=None, is_final=False):
    """
    Background task to generate a story segment.
    new_inputs: List of collected_word dicts from the just-completed step.
    """
    global state
    state.is_generating_story = True
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Build context from previous segments
        story_so_far = " ".join(state.story_segments)
        
        input_descriptions = ", ".join([f"{item['word']} ({item['type']}) found by {item['cousin']}" for item in new_inputs])

        # SYSTEM CONTEXT
        system_prompt = SYSTEM_CONTEXT

        user_prompt = ""
        
        if story_guidance == "ESTABLISH_PREMISE":
            # Extract specific inputs for the premise
            vehicle = next((i['word'] for i in new_inputs if i['type'] == 'Vehicle'), "Sleigh")
            items = next((i['word'] for i in new_inputs if i['type'] == 'Items'), "Cookies")
            place = next((i['word'] for i in new_inputs if i['type'] == 'Place'), "Review")
            
            user_prompt = (
                f"This is the START of the story.\n"
                f"Give a brief introduction about the Dias cousins going on a mission to the North Pole to find the meaning of christmas. "
                f"Use the cousins' names, {PLAYERS}. "
                f"The plot points provided at this stage are: they are traveling in a {vehicle}, bringing {items} with them. "
                f"Their first stop is {place}. "
                "These plot points may be humorously random because at this stage the real life non-fictional cousins don't know they will be guiding the story yet. "
                "The real life cousins were just asked to provide a place, three personal items, and a vehicle without any context. "
                "When they see your story contains their words, they will be amazed and realize their words are actually guiding the story. "
                "Use the words provided to write a funny opening paragraph (4-7 sentences) establishing this adventure. "
                "Focus on the excitement and the noble goal of finding the Christmas Spirit. "
                f"Wrap the key words ({vehicle}, {items}, {place}) in <span class=\"highlight\"> tags."
            )
        elif is_final: 
            user_prompt = (
                f"Current Story: {story_so_far}\n\n"
                f"New Elements Found: {input_descriptions}.\n\n"
                "This is the FINAL segment. "
                "1. Incorporate the new elements naturally. "
                "2. Build suspense as they finally reach their destination and discover the secret. "
                "3. ABRUPTLY switch tone for the punchline: Reveal that the 'True Meaning of Christmas' is actually PRESENTS! "
                "4. STOP the story immediately after this humorously ironic discovery. "
                "5. Do NOT describe them opening the presents. Do NOT wrap up the 'adventure' with a moral lesson or happy ending. The irony IS the ending."
                f"Wrap the new key words in <span class=\"highlight\"> tags."
            )
        else:
            user_prompt = (
                f"Current Story: {story_so_far}\n\n"
                f"New Elements Found: {input_descriptions}.\n\n"
                "Task: Write the next short paragraph (2-3 sentences) of the story incorporating these new elements. "
                "Keep incorporating positive themes (family, giving, etc.) to set up the ironic ending later. "
                f"Incorporating the cousins involved: {', '.join([i['cousin'] for i in new_inputs])}. "
                f"Wrap the new words in <span class=\"highlight\"> tags."
            )
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        new_segment = completion.choices[0].message.content
        state.story_segments.append(new_segment)
        state.latest_segment = new_segment
        
    except Exception as e:
        print(f"Error generating story segment: {e}")
        fallback = f"The adventure continued with {input_descriptions}!"
        state.story_segments.append(fallback)
        state.latest_segment = fallback
    finally:
        state.is_generating_story = False

def trigger_segment_generation(new_inputs, story_guidance=None, is_final=False):
    """Starts the segment generation in a background thread."""
    thread = threading.Thread(target=generate_segment_task, args=(new_inputs, story_guidance, is_final))
    thread.start()

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/status')
def get_status():
    """Returns the full game state for clients to sync."""
    full_story_text = "\n\n".join(state.story_segments)
    
    # Common response data
    response = {
        'phase': state.phase,
        'step_number': state.current_step_index + 1,
        'total_steps': len(GAME_STEPS),
        'story': full_story_text,
        'latest_segment': state.latest_segment,
        'is_generating': state.is_generating_story,
        'inputs': state.step_input_states, # List of active inputs
        'results': state.collected_words if state.phase == 'COMPLETED' else []
    }

    if state.current_step_index < len(GAME_STEPS):
        current_step = GAME_STEPS[state.current_step_index]
        response['hint'] = current_step['hint']
    else:
        response['hint'] = ""

    return jsonify(response)

@app.route('/api/update_input', methods=['POST'])
def update_input():
    """Updates the value of a specific input in real-time."""
    if state.phase != 'INPUT':
        return jsonify({'error': 'Not in input phase'}), 400

    data = request.json
    input_index = data.get('index')
    new_value = data.get('value')
    
    if input_index is not None and 0 <= input_index < len(state.step_input_states):
        state.step_input_states[input_index]['value'] = new_value
        return jsonify({'success': True})
    
    return jsonify({'error': 'Invalid input index'}), 400

@app.route('/api/admin/approve_step', methods=['POST'])
def admin_approve_step():
    """Approves ALL inputs for the current step and advances to HINT."""
    if state.phase != 'INPUT':
        return jsonify({'error': 'Not in input phase'}), 400
        
    # Validation: Ensure all inputs have values
    if any(not i['value'].strip() for i in state.step_input_states):
        return jsonify({'error': 'All fields must be filled before approval!'}), 400
    
    # Commit words
    for input_state in state.step_input_states:
        state.collected_words.append({
            'cousin': input_state['cousin'],
            'type': input_state['type'],
            'display_type': input_state['label'],
            'word': input_state['value']
        })
    
    # Advance Phase
    state.phase = 'HINT'
    
    return jsonify({'success': True})

@app.route('/found/<step_id>')
def foundation_found(step_id):
    """Called when a QR code is scanned."""
    try:
        scanned_id_int = int(step_id)
        current_target_id = state.current_step_index + 1
    except ValueError:
        return render_template('index.html', auto_join=True)

    # 1. Check if they scanned a future step
    if scanned_id_int > current_target_id:
         # Simplified for now, just redirect to main
        return render_template('index.html', auto_join=True)

    # 2. Check if it's the correct step 
    if state.phase == 'HINT' and scanned_id_int == current_target_id:
        
        # Identify the inputs that belong to this just-completed step for story generation
        current_step_def = GAME_STEPS[state.current_step_index]
        num_inputs = len(current_step_def['inputs'])
        
        # Get the words relevant to THIS step
        step_inputs = state.collected_words[-num_inputs:]
        
        # Trigger story generation logic for the COMPLETED step
        story_guidance = current_step_def.get('story_guidance')
        
        # Advance Step
        state.current_step_index += 1
        
        # Check for completion of game
        if state.current_step_index >= len(GAME_STEPS):
            state.phase = 'COMPLETED'
            # Trigger Final Generation
            trigger_segment_generation(step_inputs, story_guidance=story_guidance, is_final=True)
        else:
            state.phase = 'INPUT'
            state.initialize_step_inputs() # Prepare next inputs
            # Trigger Standard (or Premise) Generation
            trigger_segment_generation(step_inputs, story_guidance=story_guidance, is_final=False)
            
        return render_template('index.html', auto_join=True)
    
    return render_template('index.html', auto_join=True)

@app.route('/reset')
def reset_game():
    """Debug route to reset the game."""
    global state
    state = GameState()
    return "Game Reset"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
