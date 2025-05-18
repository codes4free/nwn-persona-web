#!/usr/bin/env python3
import os
import re
import time
import json
import subprocess
import threading
import datetime
from pathlib import Path
from colorama import Fore, Style, init
import openai
import pyperclip
from dotenv import load_dotenv

# Initialize colorama for colored terminal output
init()

# Load environment variables
load_dotenv()

# Configuration
LOG_FILE_PATH = "/mnt/f/OneDrive/Documentos/Neverwinter Nights/logs/nwclientLog1.txt"
USER_ACCOUNT = "Fullgazz"
SYSTEM_PATTERN = r"\[Talk\] (?:What would you like to do\?|Please choose section:|<c>\[.*?\]</c>|Crafting Menu|Back|Cancel)"

# Chat history configuration
CHAT_HISTORY_ENABLED = True
CHAT_HISTORY_DIR = "chat_history"
CHAT_HISTORY_FORMAT = "%Y-%m-%d_%H-%M-%S"

# Character profiles configuration
CHARACTER_PROFILES_DIR = "character_profiles"
DEFAULT_PROFILE = {
    "name": "Unknown Character",
    "persona": "A mysterious adventurer with no defined personality yet.",
    "background": "",
    "appearance": "",
    "traits": [],
    "relationships": {},
    "notes": ""
}

# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

class NWNXChatBot:
    def __init__(self):
        self.last_position = 0
        self.running = True
        self.message_queue = []
        self.chat_history_file = None
        self.current_character = None
        self.character_profiles = {}
        self.history_lock = threading.Lock()
        
        # Setup directories
        self._setup_directories()
        
        # Load character profiles
        self._load_character_profiles()
        
    def _setup_directories(self):
        """Set up necessary directories"""
        os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
        os.makedirs(CHARACTER_PROFILES_DIR, exist_ok=True)
        
    def _load_character_profiles(self):
        """Load all character profiles"""
        try:
            for profile_file in os.listdir(CHARACTER_PROFILES_DIR):
                if profile_file.endswith('.json'):
                    try:
                        with open(os.path.join(CHARACTER_PROFILES_DIR, profile_file), 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                            self.character_profiles[profile['name']] = profile
                            print(f"{Fore.GREEN}Loaded profile for {profile['name']}{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}Error loading profile {profile_file}: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error loading character profiles: {e}{Style.RESET_ALL}")
            
    def _save_character_profile(self, character_name):
        """Save a character profile to disk"""
        if character_name in self.character_profiles:
            try:
                filename = os.path.join(CHARACTER_PROFILES_DIR, f"{character_name.replace(' ', '_')}.json")
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.character_profiles[character_name], f, indent=2)
                print(f"{Fore.GREEN}Saved profile for {character_name}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error saving profile for {character_name}: {e}{Style.RESET_ALL}")
                
    def _detect_character(self, line):
        """Detect which character is active based on the log line"""
        character_pattern = re.compile(r"\[" + re.escape(USER_ACCOUNT) + r"\] ([^:]+)")
        match = character_pattern.search(line)
        
        if match:
            character_name = match.group(1)
            
            # If this is a new character, set up their profile
            if character_name != self.current_character:
                self.current_character = character_name
                print(f"{Fore.YELLOW}Switched to character: {character_name}{Style.RESET_ALL}")
                
                # Set up a new chat history file for this character if needed
                if CHAT_HISTORY_ENABLED:
                    self._setup_chat_history(character_name)
                    
                # Create or update character profile
                if character_name not in self.character_profiles:
                    self.character_profiles[character_name] = DEFAULT_PROFILE.copy()
                    self.character_profiles[character_name]["name"] = character_name
                    self._save_character_profile(character_name)
                    
                    # Prompt to edit the persona
                    print(f"{Fore.YELLOW}New character detected! Use 'p' to edit {character_name}'s persona.{Style.RESET_ALL}")
                    
            return character_name
            
        return None
        
    def _setup_chat_history(self, character_name):
        """Set up chat history directory and file for a specific character"""
        try:
            # Close the previous file if open
            if self.chat_history_file:
                try:
                    self.chat_history_file.write(f"\n=== Chat log ended {datetime.datetime.now()} ===\n")
                    self.chat_history_file.close()
                except:
                    pass
                    
            # Create character-specific directory
            character_dir = os.path.join(CHAT_HISTORY_DIR, character_name.replace(' ', '_'))
            os.makedirs(character_dir, exist_ok=True)
                
            # Create a new chat history file with timestamp
            timestamp = datetime.datetime.now().strftime(CHAT_HISTORY_FORMAT)
            filename = f"{character_dir}/chat_{timestamp}.log"
            self.chat_history_file = open(filename, 'a', encoding='utf-8')
            
            # Write header
            self.chat_history_file.write(f"=== NWNX:EE Chat Log for {character_name} - Started {datetime.datetime.now()} ===\n\n")
            self.chat_history_file.flush()
            
            print(f"{Fore.GREEN}Chat history for {character_name} will be saved to: {filename}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Error setting up chat history: {e}{Style.RESET_ALL}")
            self.chat_history_file = None
            
    def _save_to_history(self, message, is_own=False):
        """Save a message to the chat history file"""
        if self.chat_history_file and CHAT_HISTORY_ENABLED:
            try:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                prefix = "[SELF] " if is_own else ""
                with self.history_lock:
                    self.chat_history_file.write(f"[{timestamp}] {prefix}{message}\n")
                    self.chat_history_file.flush()
            except Exception as e:
                print(f"{Fore.RED}Error writing to chat history: {e}{Style.RESET_ALL}")
        
    def monitor_chat(self):
        """Monitor the NWN chat log file for new messages"""
        print(f"{Fore.CYAN}Starting chat monitor for {LOG_FILE_PATH}{Style.RESET_ALL}")
        
        # Wait for the log file to exist
        while not os.path.exists(LOG_FILE_PATH):
            print(f"{Fore.YELLOW}Waiting for log file to be created...{Style.RESET_ALL}")
            time.sleep(5)
        
        # Get the initial file size
        self.last_position = os.path.getsize(LOG_FILE_PATH)
        
        while self.running:
            try:
                # Check if file exists and has been modified
                if os.path.exists(LOG_FILE_PATH):
                    file_size = os.path.getsize(LOG_FILE_PATH)
                    
                    if file_size > self.last_position:
                        # Read only the new data
                        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as file:
                            file.seek(self.last_position)
                            new_data = file.read()
                            self.last_position = file.tell()
                        
                        # Process new messages
                        if new_data:
                            self.process_new_messages(new_data)
                            
                time.sleep(0.5)
                
            except Exception as e:
                print(f"{Fore.RED}Error reading log file: {e}{Style.RESET_ALL}")
                time.sleep(5)
    
    def process_new_messages(self, data):
        """Process new messages from the log file"""
        lines = data.strip().split('\n')
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
                
            # Detect which character is active
            character_name = self._detect_character(line)
                
            # Check if this is our own character's message
            is_own_message = f"[{USER_ACCOUNT}]" in line
            
            # Check if this is likely a system menu message
            is_system_message = is_own_message and re.search(SYSTEM_PATTERN, line)
            
            if is_system_message:
                # This is a system message, we'll ignore it
                continue
                
            # Display chat message with color based on who sent it
            if is_own_message:
                print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                
            # Save to chat history
            self._save_to_history(line, is_own_message)

            # --- AUTO-REPLY LOGIC ---
            if not is_own_message:
                # Try to match [Account] Character: [Talk] message
                match = re.match(r"\[([^\]]+)\] ([^:]+): \[Talk\] (.*)", line)
                if match:
                    account, char_name, player_message = match.groups()
                    ai_replies = self.generate_in_character_reply(player_message, num_alternatives=3)
                    if ai_replies:
                        print(f"\n{Fore.CYAN}AI ({self.current_character}) alternatives:{Style.RESET_ALL}")
                        for idx, reply in enumerate(ai_replies, 1):
                            print(f"{Fore.YELLOW}[{idx}]{Style.RESET_ALL} {reply}\n")
                        choice = input(f"{Fore.YELLOW}Choose a reply to copy (1-{len(ai_replies)}) or 'n' to skip: {Style.RESET_ALL}")
                        if choice.isdigit() and 1 <= int(choice) <= len(ai_replies):
                            pyperclip.copy(ai_replies[int(choice)-1])
                            print(f"{Fore.GREEN}Copied to clipboard!{Style.RESET_ALL}")
                else:
                    # Fallback: Try to match Name: [Talk] message
                    match = re.match(r"([^:]+): \[Talk\] (.*)", line)
                    if match:
                        name, player_message = match.groups()
                        ai_replies = self.generate_in_character_reply(player_message, num_alternatives=3)
                        if ai_replies:
                            print(f"\n{Fore.CYAN}AI ({self.current_character}) alternatives:{Style.RESET_ALL}")
                            for idx, reply in enumerate(ai_replies, 1):
                                print(f"{Fore.YELLOW}[{idx}]{Style.RESET_ALL} {reply}\n")
                            choice = input(f"{Fore.YELLOW}Choose a reply to copy (1-{len(ai_replies)}) or 'n' to skip: {Style.RESET_ALL}")
                            if choice.isdigit() and 1 <= int(choice) <= len(ai_replies):
                                pyperclip.copy(ai_replies[int(choice)-1])
                                print(f"{Fore.GREEN}Copied to clipboard!{Style.RESET_ALL}")
                    else:
                        # Fallback: Try to match : [Talk] message
                        match = re.match(r": \[Talk\] (.*)", line)
                        if match:
                            player_message = match.group(1)
                            ai_replies = self.generate_in_character_reply(player_message, num_alternatives=3)
                            if ai_replies:
                                print(f"\n{Fore.CYAN}AI ({self.current_character}) alternatives:{Style.RESET_ALL}")
                                for idx, reply in enumerate(ai_replies, 1):
                                    print(f"{Fore.YELLOW}[{idx}]{Style.RESET_ALL} {reply}\n")
                                choice = input(f"{Fore.YELLOW}Choose a reply to copy (1-{len(ai_replies)}) or 'n' to skip: {Style.RESET_ALL}")
                                if choice.isdigit() and 1 <= int(choice) <= len(ai_replies):
                                    pyperclip.copy(ai_replies[int(choice)-1])
                                    print(f"{Fore.GREEN}Copied to clipboard!{Style.RESET_ALL}")
                        else:
                            # Final fallback: match Talk] message
                            match = re.match(r"Talk\] (.*)", line)
                            if match:
                                player_message = match.group(1)
                                ai_replies = self.generate_in_character_reply(player_message, num_alternatives=3)
                                if ai_replies:
                                    print(f"\n{Fore.CYAN}AI ({self.current_character}) alternatives:{Style.RESET_ALL}")
                                    for idx, reply in enumerate(ai_replies, 1):
                                        print(f"{Fore.YELLOW}[{idx}]{Style.RESET_ALL} {reply}\n")
                                    choice = input(f"{Fore.YELLOW}Choose a reply to copy (1-{len(ai_replies)}) or 'n' to skip: {Style.RESET_ALL}")
                                    if choice.isdigit() and 1 <= int(choice) <= len(ai_replies):
                                        pyperclip.copy(ai_replies[int(choice)-1])
                                        print(f"{Fore.GREEN}Copied to clipboard!{Style.RESET_ALL}")

    def send_message(self, message):
        """Send a message to the game using xdotool"""
        if not self.current_character:
            print(f"{Fore.RED}No active character detected. Please interact in-game first.{Style.RESET_ALL}")
            return
            
        try:
            # Using xdotool to send keyboard events to the active window
            print(f"{Fore.YELLOW}Sending message in 3 seconds. Please focus on the game window!{Style.RESET_ALL}")
            time.sleep(3)
            
            # Press Enter to open chat
            subprocess.run(["xdotool", "key", "Return"])
            time.sleep(0.5)
            
            # Type the message
            subprocess.run(["xdotool", "type", message])
            time.sleep(0.5)
            
            # Press Enter to confirm sending
            subprocess.run(["xdotool", "key", "Return"])
            
            print(f"{Fore.GREEN}Message sent: {message}{Style.RESET_ALL}")
            
            # Record sent message in history
            self._save_to_history(f"{self.current_character}: {message}", True)
            
        except Exception as e:
            print(f"{Fore.RED}Error sending message: {e}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Make sure xdotool is installed. Run: sudo apt install xdotool{Style.RESET_ALL}")
    
    def edit_character_persona(self):
        """Edit the persona of the current character"""
        if not self.current_character:
            print(f"{Fore.RED}No active character detected. Please interact in-game first.{Style.RESET_ALL}")
            return
            
        print(f"\n{Fore.MAGENTA}=== Editing Character Persona for {self.current_character} ==={Style.RESET_ALL}")
        
        profile = self.character_profiles.get(self.current_character, DEFAULT_PROFILE.copy())
        profile["name"] = self.current_character
        
        # Edit each field
        print(f"\nCurrent persona: {profile.get('persona', DEFAULT_PROFILE['persona'])}")
        new_persona = input(f"{Fore.YELLOW}Enter new persona (or press Enter to keep current): {Style.RESET_ALL}")
        if new_persona:
            profile["persona"] = new_persona
            
        print(f"\nCurrent background: {profile.get('background', '')}")
        new_background = input(f"{Fore.YELLOW}Enter background (or press Enter to keep current): {Style.RESET_ALL}")
        if new_background:
            profile["background"] = new_background
            
        print(f"\nCurrent appearance: {profile.get('appearance', '')}")
        new_appearance = input(f"{Fore.YELLOW}Enter appearance (or press Enter to keep current): {Style.RESET_ALL}")
        if new_appearance:
            profile["appearance"] = new_appearance
            
        print(f"\nCurrent traits: {', '.join(profile.get('traits', []))}")
        new_traits = input(f"{Fore.YELLOW}Enter traits (comma-separated, or press Enter to keep current): {Style.RESET_ALL}")
        if new_traits:
            profile["traits"] = [t.strip() for t in new_traits.split(',')]
            
        print(f"\nOther notes: {profile.get('notes', '')}")
        new_notes = input(f"{Fore.YELLOW}Enter additional notes (or press Enter to keep current): {Style.RESET_ALL}")
        if new_notes:
            profile["notes"] = new_notes
            
        # Save the updated profile
        self.character_profiles[self.current_character] = profile
        self._save_character_profile(self.current_character)
        
        print(f"{Fore.GREEN}Character persona updated for {self.current_character}{Style.RESET_ALL}")
    
    def show_character_persona(self):
        """Display the persona of the current character"""
        if not self.current_character:
            print(f"{Fore.RED}No active character detected. Please interact in-game first.{Style.RESET_ALL}")
            return
            
        profile = self.character_profiles.get(self.current_character, DEFAULT_PROFILE.copy())
        
        print(f"\n{Fore.MAGENTA}=== Character Persona: {self.current_character} ==={Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Persona:{Style.RESET_ALL} {profile.get('persona', 'Not defined')}")
        
        if profile.get('background'):
            print(f"{Fore.YELLOW}Background:{Style.RESET_ALL} {profile['background']}")
            
        if profile.get('appearance'):
            print(f"{Fore.YELLOW}Appearance:{Style.RESET_ALL} {profile['appearance']}")
            
        if profile.get('traits'):
            print(f"{Fore.YELLOW}Traits:{Style.RESET_ALL} {', '.join(profile['traits'])}")
            
        if profile.get('notes'):
            print(f"{Fore.YELLOW}Notes:{Style.RESET_ALL} {profile['notes']}")
            
        print(f"{Fore.MAGENTA}==================================={Style.RESET_ALL}\n")
    
    def list_characters(self):
        """List all characters with profiles"""
        print(f"\n{Fore.MAGENTA}=== Character Profiles ==={Style.RESET_ALL}")
        
        if not self.character_profiles:
            print(f"{Fore.YELLOW}No character profiles found.{Style.RESET_ALL}")
        else:
            for i, (name, profile) in enumerate(self.character_profiles.items(), 1):
                active = " (ACTIVE)" if name == self.current_character else ""
                print(f"{Fore.GREEN}{i}. {name}{active}{Style.RESET_ALL}")
                print(f"   {Fore.CYAN}Persona:{Style.RESET_ALL} {profile.get('persona', 'Not defined')[:50]}...")
                
        print(f"{Fore.MAGENTA}========================={Style.RESET_ALL}\n")
    
    def compose_message(self):
        """Prompt for user input and add to message queue"""
        while self.running:
            try:
                # Show prompt with current character
                character_info = f" ({self.current_character})" if self.current_character else ""
                
                # Get user input for new message
                message = input(f"\n{Fore.YELLOW}Enter message{character_info} (or 'q' to quit, 'h' for history, 'p' for persona, 'c' for characters): {Style.RESET_ALL}")
                
                if message.lower() == 'q':
                    self.running = False
                    break
                    
                elif message.lower() == 'h':
                    self.show_recent_history()
                    continue
                    
                elif message.lower() == 'p':
                    if self.current_character:
                        self.edit_character_persona()
                    else:
                        self.show_character_persona()
                    continue
                    
                elif message.lower() == 'c':
                    self.list_characters()
                    continue
                    
                elif message.lower().startswith('show '):
                    # Command to show a specific character's persona
                    char_name = message[5:].strip()
                    if char_name in self.character_profiles:
                        temp = self.current_character
                        self.current_character = char_name
                        self.show_character_persona()
                        self.current_character = temp
                    else:
                        print(f"{Fore.RED}Character '{char_name}' not found.{Style.RESET_ALL}")
                    continue
                
                elif message.lower().startswith('a '):
                    player_input = message[2:].strip()
                    ai_reply = self.generate_in_character_reply(player_input)
                    if ai_reply:
                        print(f"\n{Fore.CYAN}AI ({self.current_character}): {ai_reply}{Style.RESET_ALL}")
                        confirm = input(f"{Fore.YELLOW}Send this AI reply in-game? (y/n): {Style.RESET_ALL}")
                        if confirm.lower() == 'y':
                            self.send_message(ai_reply)
                    continue
                
                if message:
                    # Display confirmation banner
                    print(f"\n{Fore.BLACK}{Style.BRIGHT}{Fore.YELLOW}╔{'═' * (len(message) + 8)}╗{Style.RESET_ALL}")
                    print(f"{Fore.BLACK}{Style.BRIGHT}{Fore.YELLOW}║   {message}   ║{Style.RESET_ALL}")
                    print(f"{Fore.BLACK}{Style.BRIGHT}{Fore.YELLOW}╚{'═' * (len(message) + 8)}╝{Style.RESET_ALL}")
                    
                    confirm = input(f"{Fore.YELLOW}Send this message? (y/n): {Style.RESET_ALL}")
                    if confirm.lower() == 'y':
                        self.send_message(message)
            
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"{Fore.RED}Error in message composition: {e}{Style.RESET_ALL}")
    
    def show_recent_history(self, lines=20):
        """Show the most recent chat history"""
        if not self.chat_history_file or not CHAT_HISTORY_ENABLED or not self.current_character:
            print(f"{Fore.RED}Chat history is not available.{Style.RESET_ALL}")
            return
            
        try:
            history_file = self.chat_history_file.name
            if self.chat_history_file:
                self.chat_history_file.flush()
            with self.history_lock:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_lines = f.readlines()
                    recent_lines = history_lines[-lines:] if len(history_lines) > lines else history_lines
            
            print(f"\n{Fore.MAGENTA}=== Recent Chat History for {self.current_character} ({len(recent_lines)} lines) ==={Style.RESET_ALL}")
            for line in recent_lines:
                if "[SELF]" in line:
                    print(f"{Fore.GREEN}{line.strip()}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.CYAN}{line.strip()}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}================================{Style.RESET_ALL}\n")
                
        except Exception as e:
            print(f"{Fore.RED}Error showing chat history: {e}{Style.RESET_ALL}")
    
    def generate_in_character_reply(self, player_message, num_alternatives=3):
        if not self.current_character:
            print("No active character detected.")
            return None
        persona = self.character_profiles.get(self.current_character)
        if not persona:
            print("No persona profile found for this character.")
            return None

        system_prompt = (
            f"You are roleplaying as the following character in Neverwinter Nights EE. "
            f"Stay strictly in character, using the persona, background, and style below.\n\n"
            f"Persona: {persona.get('persona', '')}\n"
            f"Background: {persona.get('background', '')}\n"
            f"Appearance: {persona.get('appearance', '')}\n"
            f"Traits: {', '.join(persona.get('traits', []))}\n"
            f"Roleplay Prompt: {persona.get('roleplay_prompt', '')}\n"
            f"Interaction Constraints: {', '.join(persona.get('interaction_constraints', []))}\n"
            f"Mannerisms: {', '.join(persona.get('mannerisms', []))}\n"
            f"Example Dialogue: {persona.get('dialogue_examples', [])}\n"
            f"\nNever break character. Respond to the following as your character would.\n"
            f"\nGenerate three distinct in-character replies to the player message, each with a different style:"
            f"\n1. Fast, dry, and pointed (1 line)."
            f"\n2. Elegant but not long (2 lines)."
            f"\n3. Creative and elegant, with some flair (3 lines)."
            f"\nLabel each reply as '1.', '2.', and '3.' respectively."
        )
        user_prompt = f"Player says: {player_message}\nYour replies:"

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.9,
            n=1,
        )
        # Parse the single response into three options
        content = response.choices[0].message.content.strip()
        # Split by '1.', '2.', '3.'
        import re
        matches = re.split(r'\n?\s*\d\.\s*', content)
        # The first split part is before '1.', so ignore it
        options = [m.strip() for m in matches[1:4]]
        # Record all three in chat history
        if self.chat_history_file and CHAT_HISTORY_ENABLED:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            with self.history_lock:
                for idx, reply in enumerate(options, 1):
                    self.chat_history_file.write(f"[{timestamp}] [AI Option {idx}] {reply}\n")
                self.chat_history_file.flush()
        return options
    
    def run(self):
        """Run the chatbot with monitoring and input threads"""
        # Start the chat monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_chat)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print(f"{Fore.CYAN}Chat monitor started. You can now compose messages.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Commands: 'h' for history, 'p' for character persona, 'c' to list characters, 'q' to quit{Style.RESET_ALL}")
        
        # Run the message composition in the main thread
        self.compose_message()
        
        print(f"{Fore.YELLOW}Shutting down...{Style.RESET_ALL}")
        
        # Signal the monitor thread to stop
        self.running = False
        # Wait for the monitor thread to finish
        monitor_thread.join(timeout=2)
        
        # Close the chat history file
        if self.chat_history_file:
            try:
                self.chat_history_file.write(f"\n=== Chat log ended {datetime.datetime.now()} ===\n")
                self.chat_history_file.close()
            except:
                pass

if __name__ == "__main__":
    # Check if required tools are installed
    try:
        subprocess.run(["which", "xdotool"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"{Fore.RED}xdotool is not installed. Please install it with:{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}sudo apt install xdotool{Style.RESET_ALL}")
        exit(1)
    
    # Check if the log file path is accessible from WSL
    log_path = Path(LOG_FILE_PATH)
    if not log_path.exists():
        print(f"{Fore.YELLOW}Warning: Log file not found at {LOG_FILE_PATH}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Make sure the Windows path is correctly mounted in WSL{Style.RESET_ALL}")
        
        # Check if the directory exists
        log_dir = log_path.parent
        if not log_dir.exists():
            print(f"{Fore.RED}Log directory does not exist: {log_dir}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Make sure F: drive is mounted and the path is correct{Style.RESET_ALL}")
    
    # Create and run the chatbot
    chatbot = NWNXChatBot()
    chatbot.run() 