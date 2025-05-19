#!/usr/bin/env python3
import os
import json
import shutil
from pathlib import Path

# Configuration
CHARACTER_PROFILES_DIR = "character_profiles"

# Ensure character profiles directory exists
os.makedirs(CHARACTER_PROFILES_DIR, exist_ok=True)

def load_all_profiles():
    """Load all character profiles from the profiles directory"""
    profiles = {}
    
    try:
        print(f"Loading character profiles from {CHARACTER_PROFILES_DIR}")
        for profile_file in os.listdir(CHARACTER_PROFILES_DIR):
            full_path = os.path.join(CHARACTER_PROFILES_DIR, profile_file)
            
            # Skip directories and hidden files
            if os.path.isdir(full_path) or profile_file.startswith('.'):
                continue
                
            # Make sure it's a JSON file
            if not profile_file.lower().endswith('.json'):
                print(f"Skipping non-JSON file: {profile_file}")
                continue
                
            try:
                print(f"Attempting to load: {profile_file}")
                with open(full_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                    if 'name' in profile:
                        profiles[profile['name']] = profile
                        print(f"Successfully loaded profile for {profile['name']}")
                    else:
                        print(f"Error in profile {profile_file}: Missing 'name' field")
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON in {profile_file}: {e}")
            except Exception as e:
                print(f"Error loading profile {profile_file}: {e}")
    except Exception as e:
        print(f"Error loading character profiles: {e}")
        
    print(f"Total profiles loaded: {len(profiles)}")
    for name in profiles.keys():
        print(f"  - {name}")
        
    return profiles

def get_profile(character_name):
    """Get a specific character profile"""
    profile_path = os.path.join(CHARACTER_PROFILES_DIR, f"{character_name.replace(' ', '_')}.json")
    
    if not os.path.exists(profile_path):
        return None
    
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading profile {character_name}: {e}")
        return None

def save_profile(profile_data):
    """Save a character profile to disk"""
    if 'name' not in profile_data:
        return {"error": "Character name is required"}
    
    character_name = profile_data['name']
    profile_path = os.path.join(CHARACTER_PROFILES_DIR, f"{character_name.replace(' ', '_')}.json")
    
    # Ensure the required fields exist
    required_fields = ['name', 'race', 'class', 'alignment', 'description', 'background', 'appearance', 'traits']
    for field in required_fields:
        if field not in profile_data or not profile_data[field]:
            return {"error": f"Field '{field}' is required"}
    
    # Ensure lists are properly formatted
    list_fields = ['traits', 'mannerisms', 'interaction_constraints']
    for field in list_fields:
        if field in profile_data:
            # If it's a string, split by newlines and filter empty lines
            if isinstance(profile_data[field], str):
                profile_data[field] = [line.strip() for line in profile_data[field].split('\n') if line.strip()]
            
            # Ensure it's a list
            if not isinstance(profile_data[field], list):
                profile_data[field] = []
    
    # Ensure dialogue examples are formatted properly
    if 'dialogue_examples' in profile_data and not isinstance(profile_data['dialogue_examples'], list):
        if isinstance(profile_data['dialogue_examples'], str):
            # Try to parse as JSON if it's a string
            try:
                profile_data['dialogue_examples'] = json.loads(profile_data['dialogue_examples'])
            except:
                profile_data['dialogue_examples'] = []
        else:
            profile_data['dialogue_examples'] = []
    
    try:
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2)
        return {"success": True, "message": f"Profile for {character_name} saved successfully"}
    except Exception as e:
        print(f"Error saving profile {character_name}: {e}")
        return {"error": f"Failed to save profile: {str(e)}"}

def delete_profile(character_name):
    """Delete a character profile"""
    profile_path = os.path.join(CHARACTER_PROFILES_DIR, f"{character_name.replace(' ', '_')}.json")
    
    if not os.path.exists(profile_path):
        return {"error": "Character profile not found"}
    
    try:
        os.remove(profile_path)
        return {"success": True, "message": f"Profile for {character_name} deleted successfully"}
    except Exception as e:
        print(f"Error deleting profile {character_name}: {e}")
        return {"error": f"Failed to delete profile: {str(e)}"}

def get_template_profile():
    """Returns a template for a new character profile"""
    return {
        "name": "",
        "title": "",
        "race": "",
        "class": "",
        "alignment": "",
        "description": "",
        "roleplay_prompt": "",
        "interaction_constraints": [],
        "mannerisms": [],
        "dialogue_examples": [],
        "background": "",
        "appearance": "",
        "traits": [],
        "notes": "",
        "temperature": 0.7  # Default temperature value for AI responses
    }

def update_profile(character_name, profile_data):
    """Update an existing character profile"""
    if not character_name:
        return {"error": "Character name is required"}
    
    # Check if character exists
    profile_path = os.path.join(CHARACTER_PROFILES_DIR, f"{character_name.replace(' ', '_')}.json")
    if not os.path.exists(profile_path):
        return {"error": "Character profile not found"}
    
    # Load the existing profile
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            existing_profile = json.load(f)
    except Exception as e:
        print(f"Error reading profile {character_name}: {e}")
        return {"error": f"Failed to read profile: {str(e)}"}
    
    # Make sure the name matches (cannot be changed)
    if profile_data.get('name') != character_name:
        profile_data['name'] = character_name
    
    # Ensure the required fields exist
    required_fields = ['name', 'race', 'class', 'alignment', 'description', 'background', 'appearance', 'traits']
    for field in required_fields:
        if field not in profile_data or not profile_data[field]:
            return {"error": f"Field '{field}' is required"}
    
    # Ensure lists are properly formatted
    list_fields = ['traits', 'mannerisms', 'interaction_constraints']
    for field in list_fields:
        if field in profile_data:
            # If it's a string, split by newlines and filter empty lines
            if isinstance(profile_data[field], str):
                profile_data[field] = [line.strip() for line in profile_data[field].split('\n') if line.strip()]
            
            # Ensure it's a list
            if not isinstance(profile_data[field], list):
                profile_data[field] = []
    
    # Ensure dialogue examples are formatted properly
    if 'dialogue_examples' in profile_data and not isinstance(profile_data['dialogue_examples'], list):
        if isinstance(profile_data['dialogue_examples'], str):
            # Try to parse as JSON if it's a string
            try:
                profile_data['dialogue_examples'] = json.loads(profile_data['dialogue_examples'])
            except:
                profile_data['dialogue_examples'] = []
        else:
            profile_data['dialogue_examples'] = []
    
    try:
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2)
            
        # Reload character_profiles
        global character_profiles
        character_profiles = load_all_profiles()
            
        return {"success": True, "message": f"Profile for {character_name} updated successfully"}
    except Exception as e:
        print(f"Error updating profile {character_name}: {e}")
        return {"error": f"Failed to update profile: {str(e)}"}

def import_profile_from_json(json_data):
    """Import a character profile from a JSON string or dictionary"""
    try:
        # If json_data is a string, parse it
        if isinstance(json_data, str):
            try:
                profile_data = json.loads(json_data)
            except json.JSONDecodeError as e:
                return {"error": f"Invalid JSON format: {str(e)}"}
        else:
            profile_data = json_data
            
        # Validate the profile data has required fields
        if not isinstance(profile_data, dict):
            return {"error": "JSON data must be an object"}
            
        # Check if name exists
        if 'name' not in profile_data or not profile_data['name']:
            return {"error": "Character name is required in the JSON data"}
            
        character_name = profile_data['name']
        
        # Check if a character with this name already exists
        profile_path = os.path.join(CHARACTER_PROFILES_DIR, f"{character_name.replace(' ', '_')}.json")
        if os.path.exists(profile_path):
            return {"error": f"A character with the name '{character_name}' already exists", "exists": True, "name": character_name}
        
        # Validate required fields
        required_fields = ['name', 'race', 'class', 'alignment', 'description', 'background', 'appearance', 'traits']
        missing_fields = [field for field in required_fields if field not in profile_data or not profile_data[field]]
        
        if missing_fields:
            return {"error": f"Required fields missing in JSON: {', '.join(missing_fields)}"}
        
        # Ensure lists are properly formatted
        list_fields = ['traits', 'mannerisms', 'interaction_constraints']
        for field in list_fields:
            if field in profile_data:
                # If it's a string, split by newlines
                if isinstance(profile_data[field], str):
                    profile_data[field] = [line.strip() for line in profile_data[field].split('\n') if line.strip()]
                # Ensure it's a list
                if not isinstance(profile_data[field], list):
                    profile_data[field] = []
        
        # Ensure dialogue examples are properly formatted
        if 'dialogue_examples' in profile_data:
            if not isinstance(profile_data['dialogue_examples'], list):
                profile_data['dialogue_examples'] = []
            else:
                # Ensure each dialogue example has the right structure
                for i, example in enumerate(profile_data['dialogue_examples']):
                    if not isinstance(example, dict):
                        profile_data['dialogue_examples'][i] = {}
                    
                    # Ensure character action has asterisks
                    if 'norfind_action' in example and example['norfind_action']:
                        action = example['norfind_action']
                        if not (action.startswith('*') and action.endswith('*')):
                            example['norfind_action'] = f"*{action.strip('*')}*"
        
        # Save the profile
        return save_profile(profile_data)
        
    except Exception as e:
        print(f"Error importing profile from JSON: {e}")
        return {"error": f"Failed to import profile: {str(e)}"}

# Load character profiles on module import
character_profiles = load_all_profiles() 