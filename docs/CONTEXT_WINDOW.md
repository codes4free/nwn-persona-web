# NWN Persona Web: Conversation Context Window

## Overview

The Conversation Context Window is a feature that enhances AI-generated responses by providing relevant conversation history to the AI model. This allows the AI to understand the flow of conversation and generate more coherent, contextually appropriate responses for your Neverwinter Nights characters.

## How It Works

When you select a message to respond to, the system automatically:

1. Collects the last 3-4 messages from the specific player you're responding to
2. Collects the last 2-3 messages from the overall conversation
3. Combines these messages while removing duplicates
4. Sorts them chronologically to maintain conversation flow
5. Sends this context along with your character's profile to the AI

## User Interface

The context window feature works seamlessly within the existing interface:

- When you select a player message, you'll see a blue badge that indicates how many context messages will be included (e.g., "+5 context")
- No additional configuration is required - the system handles context collection automatically
- The existing message selection workflow remains unchanged

## Benefits

Using the conversation context window provides several advantages:

1. **Conversation Continuity**: The AI can understand and reference previous exchanges
2. **Character Consistency**: By seeing its own previous responses, your character maintains a consistent persona
3. **Topical Awareness**: The AI can follow conversation topics across multiple messages
4. **More Natural Dialogue**: Responses feel more like part of a flowing conversation rather than isolated replies
5. **Reduced Repetition**: The AI avoids repeating information that was already mentioned

## Technical Implementation

The context window is implemented through:

- A JavaScript system that maintains a chat history in the browser
- Functions that intelligently build context when a message is selected
- Backend integration with the OpenAI API that includes context in the prompt
- Proper handling of conversation flow and speaker roles

## Limitations

- The context window maintains up to 20 recent messages in memory
- Only a subset of these (typically 5-7 messages) are sent with each request to avoid overwhelming the AI
- Context is built from the current session only and does not persist across browser refreshes

## Best Practices

To get the most out of the context window feature:

1. Allow conversation to flow naturally in-game
2. Select recent messages to respond to whenever possible
3. Pay attention to the context badge to see how much history is being included
4. For completely new topics, clear previous responses first to avoid topic confusion

---

The context window feature significantly improves the quality and consistency of AI-generated character responses without requiring any additional effort from users. 