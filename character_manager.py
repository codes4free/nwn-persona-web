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
    """Load all character profiles from user-specific directories under 'character_profiles'."""
    profiles = {}
    base_dir = "character_profiles"
    if os.path.exists(base_dir):
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        profiles[data['name']] = data
                    except Exception as e:
                        continue
    return profiles

def get_profile(character_name):
    """Get a specific character profile"""
    target_name = f"{character_name.replace(' ', '_')}.json"
    for root, dirs, files in os.walk(CHARACTER_PROFILES_DIR):
        if target_name in files:
            profile_path = os.path.join(root, target_name)
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading profile {character_name}: {e}")
                return None
    return None

def save_profile(data):
    """Save a character profile in the owner's subdirectory within 'character_profiles'."""
    owner = data.get('owner', 'default')
    profiles_dir = os.path.join("character_profiles", owner)
    os.makedirs(profiles_dir, exist_ok=True)
    file_path = os.path.join(profiles_dir, f"{data['name']}.json")
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return {"success": True, "message": f"Profile for {data['name']} saved."}
    except Exception as e:
        return {"error": str(e)}

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
        "temperature": 0.2  # Default Response Temperature for AI responses (0.1-0.4: more focused and deterministic)
    }

def update_profile(character_name, profile_data):
    """Update an existing character profile by merging new data with the existing profile.

    Args:
        character_name (str): The name of the character (cannot be changed).
        profile_data (dict): The new data to update for the character.

    Returns:
        dict: Success or error message.
    """
    if not character_name:
        return {"error": "Character name is required"}
    
    target_name = f"{character_name.replace(' ', '_')}.json"
    profile_path = None
    for root, dirs, files in os.walk(CHARACTER_PROFILES_DIR):
        if target_name in files:
            profile_path = os.path.join(root, target_name)
            break
    if not profile_path:
        return {"error": "Character profile not found"}
    
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            existing_profile = json.load(f)
    except Exception as e:
        print(f"Error reading profile {character_name}: {e}")
        return {"error": f"Failed to read profile: {str(e)}"}
    
    # Merge existing profile with new data (preserving missing fields)
    merged_profile = existing_profile.copy()
    merged_profile.update(profile_data)
    # Ensure the character's name remains unchanged
    merged_profile['name'] = character_name
    
    # Validate required fields in the merged profile
    required_fields = ['name', 'race', 'class', 'alignment', 'description', 'background', 'appearance', 'traits']
    for field in required_fields:
        if field not in merged_profile or not merged_profile[field]:
            return {"error": f"Field '{field}' is required"}
    
    # Ensure list fields are properly formatted
    list_fields = ['traits', 'mannerisms', 'interaction_constraints']
    for field in list_fields:
        if field in merged_profile:
            if isinstance(merged_profile[field], str):
                merged_profile[field] = [line.strip() for line in merged_profile[field].split('\n') if line.strip()]
            if not isinstance(merged_profile[field], list):
                merged_profile[field] = []
    
    # Ensure dialogue examples are formatted properly
    if 'dialogue_examples' in merged_profile and not isinstance(merged_profile['dialogue_examples'], list):
        if isinstance(merged_profile['dialogue_examples'], str):
            try:
                merged_profile['dialogue_examples'] = json.loads(merged_profile['dialogue_examples'])
            except:
                merged_profile['dialogue_examples'] = []
        else:
            merged_profile['dialogue_examples'] = []
    
    # Save the updated profile
    try:
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(merged_profile, f, indent=2)
        
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