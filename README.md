# NWNX:EE Chatbot SaaS

## Overview

NWNX:EE Chatbot is a cutting-edge solution designed for Neverwinter Nights Enhanced Edition communities. Our product leverages AI-powered responses and real-time chat monitoring to enhance in-game communication and bring your roleplaying experience to the next level.

## Key Features

- **Seamless Chat Integration:** Monitor and interact with in-game chat logs in real-time via a modern, web-based interface.
- **Dynamic Character Profiles:** Create and manage customizable character personas that drive unique, in-character responses.
- **AI-Powered Replies:** Automatically generate contextual, engaging dialogue using advanced AI technology (GPT-4).
- **Conversation Context Window:** Enhance AI responses by providing relevant conversation history, creating more coherent and natural dialogue.
- **Secure and Scalable:** Built with enterprise-grade security and designed for scalability to meet the demands of active gaming communities.
- **User-Friendly Dashboard:** Enjoy an intuitive UI built with Bootstrap 5, ensuring a smooth and responsive user experience.
- **Secure HTTPS Communication:** All traffic is encrypted using SSL/TLS with automatic certificate management via Let's Encrypt.

## Product Benefits

- **Enhanced Roleplaying:** Bring your game to life with dynamic, personalized character interactions that engage your players.
- **Operational Efficiency:** Automate routine in-game communication tasks, letting game masters and moderators focus on strategic gameplay.
- **Real-Time Insights:** Gain instant visibility into game chat for effective monitoring, administration, and community management.
- **Contextual Understanding:** The conversation context window ensures characters maintain conversation flow and consistency across multiple messages.
- **Customization:** Tailor character voices and responses to fit the unique lore and style of your game community.
- **Enterprise-Grade Security:** Keep your data safe with end-to-end encryption for all communication.

## How It Works

Our Platform connects directly to your game's chat systems, processing logs to detect active characters and generate in-character AI responses. The easy-to-use web dashboard allows administrators to manage character profiles, view chat history, and adjust AI behavior without ever touching server configurations.

The service comes with a dedicated NWNLogClient application (downloadable as NWNLogClient_Setup.exe) that streams game logs to our secure cloud servers, ensuring a seamless and integrated gaming experience.

### Conversation Context Window

The Conversation Context Window feature enhances AI-generated responses by providing relevant conversation history to the AI model:

1. When selecting a message to respond to, the system collects recent conversation context
2. This includes both character-specific messages and the recent overall conversation
3. The AI uses this context to generate more coherent and contextually appropriate responses
4. No configuration required - it works automatically and is indicated by a context badge

For more information about this feature, see the [Context Window Documentation](docs/CONTEXT_WINDOW.md).

## Get Started

To learn more about our NWNX:EE Chatbot, pricing, and implementation details, please contact our sales team.

## Contact

For further information or to schedule a demo, please email [ffmtelecom@gmail.com](mailto:ffmtelecom@gmail.com).

## License

© 2025 D6LAB. All rights reserved.

## Security and Connectivity

### HTTPS Support

The application fully supports HTTPS for secure communication:

1. Automatic SSL certificate management via Let's Encrypt
2. HTTP to HTTPS redirection to ensure all traffic is encrypted
3. Secure WebSocket connections (WSS) for real-time updates
4. Automatic certificate renewal to maintain security
5. For more information, see the [HTTPS Setup Guide](HTTPS_SETUP.md)

### WebSocket Troubleshooting

If you experience any issues with the real-time communication in the application, we've created a dedicated WebSocket troubleshooting tool and guide:

1. Access the WebSocket debug tool at `/debug_websocket` to test your connection
2. View detailed information about WebSocket status, transport type, and connection events
3. For more information, see the [WebSocket Troubleshooting Guide](WEBSOCKET_TROUBLESHOOTING.md)

The most recent update includes significant improvements to WebSocket stability:
- Support for both WebSocket and polling transports
- Improved connection reliability with automatic reconnection
- Better error handling and diagnostic information
- Comprehensive debug tools for identifying connection issues
- Secure WebSocket (WSS) support over HTTPS 