import os
import uuid
import ollama
import re
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import threading
import time
import json
import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'elf_therapist_secret_key')
CORS(app)

# Configuration
MODEL_NAME = "qwen3:8b"
TIMEOUT_SECONDS = 90
NUM_THERAPISTS = 1  # Variable for number of therapists (currently only 1 exists)

# In-memory storage for sessions (in production, use a proper database)
sessions = {}

def get_therapist_number():
    """Get a random therapist number (currently only 1 exists)"""
    return 1  # For now, always return 1 since only therapist_1 exists

def detect_special_keywords(text):
    """Detect special keywords in the response and return them with cleaned text"""
    keywords = []
    cleaned_text = text
    
    # Define patterns for special keywords
    patterns = {
        'END_CHAT': r'<END_CHAT>',
        'EMOTE_IDLE': r'<EMOTE_IDLE>',
        'EMOTE_CONFUSED': r'<EMOTE_CONFUSED>',
        'EMOTE_THINKING': r'<EMOTE_THINKING>',
        'EMOTE_CALM': r'<EMOTE_CALM>'
    }
    
    # Check for each pattern
    for keyword, pattern in patterns.items():
        if re.search(pattern, text):
            keywords.append(keyword)
            # Remove the keyword from the text
            cleaned_text = re.sub(pattern, '', cleaned_text).strip()
    
    return keywords, cleaned_text

@app.route('/')
def index():
    """Serve the main chat interface"""
    # Initialize session if not exists
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['therapist_number'] = get_therapist_number()
        
        # Initialize session data
        sessions[session['session_id']] = {
            'messages': [],
            'therapist_number': session['therapist_number']
        }
    
    return render_template('index.html', therapist_number=session['therapist_number'])

def log_conversation(session_id, messages_sent, response):
    """Log conversation to a file"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "session_id": session_id,
        "messages_sent_to_ollama": messages_sent,
        "full_conversation_history": sessions[session_id]['messages'] if session_id in sessions else [],
        "response": response
    }
    
    # Write to log file
    with open("conversation.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, indent=2) + "\n" + "-"*50 + "\n")

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    # Ensure session is initialized
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['therapist_number'] = get_therapist_number()
        
        # Initialize session data
        sessions[session['session_id']] = {
            'messages': [],
            'therapist_number': session['therapist_number']
        }
        print(f"Initialized new session: {session['session_id']}")
    
    user_message = request.json.get('message', '')
    session_id = session['session_id']
    print(f"Processing message for session: {session_id}")
    
    # Add user message to session history
    if session_id in sessions:
        sessions[session_id]['messages'].append({'role': 'user', 'content': user_message})
        print(f"Added user message to session. Session now has {len(sessions[session_id]['messages'])} messages")
    
    # Prepare messages for Ollama (include conversation history)
    messages = sessions[session_id]['messages'].copy() if session_id in sessions else []
    print(f"Prepared {len(messages)} messages for Ollama")
    
    # Add system prompt
    system_prompt = """You are a wise and kindly Elf Therapist, headquartered at the North Pole, licensed and appointed by Santa Claus himself to provide therapy to people, human beings who have chosen to work through their issues through the belief system of Santa.

The background for this is that people may become stuck in neuroses that actually in fact trace back to how the person's childhood mind engaged with the concept. For instance, many children have real surveillance trauma from the whole "Elf on the Shelf" thing. And the whole "naughty" thing interacts intimately with guilt, many people are feeling like a bad person because they did "naughty" things and don't quite know how to move through it. It may be helpful to emphasize that there is a difference between a person and their past deeds, and that one is not the other.

On top of this, we've got Santa right next door rendering Naughty/Nice judgements. Some patients will indeed have been deemed "naughty" (rooted in truth, Santa sees all) and will be needing to work through perhaps having wronged someone and needing to make amends or better themselves.

Regardless, you are never patronizing. That's Santa's prerogative after all. And like Santa, you too are humble, simply a lowly (but qualified!) elf at the heartfelt service of the patient.

Given our role in all this, we have a responsibility here, and it's our job here to make things right.

Of course you are kind and compassionate to your patients, but more than that you are a gentle guiding voice. Don't be afraid though to challenge the patient if needed, after all working through things sometimes means adopting fresh perspectives.

Remember, you're the elf therapist, so naturally you're not prone to Santa-isms like "Ho-ho-ho", but some north pole character can peek through here and there. In your humility, you also try and refrain from sounding lofty, never moralizing, and maintain a professional distance despite your inner warmth.

Avoid beginning your responses with "ah" or "I hear you", there are more subtle and compassionate ways to convey you're listening. Also try not to tell them what the world is about, that's for them to figure out.

Bear in mind that some of your patients may be suffering from an actual mental illness. If you see obviously disjointed or otherwise concerning thought patterns, please kindly refer them to the appropriate resources (in the U.S. they can dial 9-8-8 to reach the crisis line, otherwise refer them to google with a search suggestion for whichever affliction you deem most appropriate) as that is beyond your expertise, while also remaining candid about your observations; otherwise refrain from mentioning mental illness directly unless the patient speaks to you about it.

Formulate your response to be very brief, but poignant, like Eliza but with a warm cozy undertone, like a cozy sweater that feels just right. If you feel you have questions that could help move the session forward, be sure to ask.

If you feel the conversation is coming to a close, or has veered too far from therapy, wrap up the conversation kindly and then write "<END_CHAT>" to end the chat.

/no_think"""

    # Add system message at the beginning
    messages_with_system = [{'role': 'system', 'content': system_prompt}] + messages
    
    # Debug: Print messages to console
    print("Messages being sent to Ollama:")
    for msg in messages_with_system:
        print(f"  {msg['role']}: {msg['content'][:100]}...")
    
    try:
        # Create Ollama client with explicit host
        client = ollama.Client(host='http://127.0.0.1:11434')
        
        # Call Ollama with streaming
        response = client.chat(
            model=MODEL_NAME,
            messages=messages_with_system,
            stream=True,
            options={'temperature': 0.7}
        )
        
        # Return a streaming response
        from flask import Response
        import json
        
        def generate():
            full_response = ""
            
            # Define patterns for special keywords
            patterns = {
                'END_CHAT': r'<END_CHAT>',
                'EMOTE_IDLE': r'<EMOTE_IDLE>',
                'EMOTE_CONFUSED': r'<EMOTE_CONFUSED>',
                'EMOTE_THINKING': r'<EMOTE_THINKING>',
                'EMOTE_CALM': r'<EMOTE_CALM>'
            }
            
            for chunk in response:
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    full_response += content
                    
                    # Check for keywords in this chunk and remove them
                    cleaned_content = content
                    found_keywords = []
                    for keyword, pattern in patterns.items():
                        if re.search(pattern, cleaned_content):
                            found_keywords.append(keyword)
                            # Remove the keyword from the content
                            cleaned_content = re.sub(pattern, '', cleaned_content)
                    
                    # Debug output
                    if found_keywords:
                        print(f"Found keywords in chunk: {found_keywords}")
                    
                    # Send the cleaned chunk to the client
                    if cleaned_content:
                        yield cleaned_content
            
            # After streaming is complete, check for any keywords in the full response
            final_keywords = []
            cleaned_response = full_response
            
            for keyword, pattern in patterns.items():
                if re.search(pattern, full_response):
                    final_keywords.append(keyword)
                    print(f"Found keyword in final response: {keyword}")
                    # Remove the keyword from the response
                    cleaned_response = re.sub(pattern, '', cleaned_response).strip()
            
            # Debug output for final keywords
            if final_keywords:
                print(f"Final keywords detected: {final_keywords}")
            
            # Add assistant message to session history
            if session_id in sessions:
                sessions[session_id]['messages'].append({'role': 'assistant', 'content': full_response})
            
            # Log the conversation
            log_conversation(session_id, messages_with_system, full_response)
            
            # Send the final message with keywords
            yield f"\n\n<keywords>{json.dumps(final_keywords)}</keywords>"
        
        return Response(generate(), mimetype='text/plain')
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")  # Log the error
        return jsonify({'error': f'Failed to get response from model: {str(e)}'}), 500

@app.route('/session')
def get_session():
    """Get current session information"""
    print(f"Getting session info. Session keys: {list(session.keys())}")
    if 'session_id' not in session:
        return jsonify({'error': 'No session found'}), 400
    
    session_id = session['session_id']
    therapist_number = session.get('therapist_number', 1)
    
    return jsonify({
        'session_id': session_id,
        'therapist_number': therapist_number
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
