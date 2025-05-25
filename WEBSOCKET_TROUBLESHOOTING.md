# WebSocket Troubleshooting Guide

This guide helps you troubleshoot WebSocket connection issues in the NWN Persona Web application.

## Recent Updates

### HTTPS and Secure WebSockets

The application now supports:
- Full HTTPS encryption via Let's Encrypt
- Secure WebSockets (WSS) for encrypted real-time communication
- Automatic HTTP to HTTPS redirection
- IPv6 compatibility for all secure connections

For more details on the HTTPS implementation, see [HTTPS Setup Guide](HTTPS_SETUP.md).

### WebSocket Improvements

The following improvements have been made to address WebSocket connectivity issues:

1. Changed transport order to prioritize polling first (more reliable initial connection)
2. Reduced connection timeouts to prevent long waiting periods
3. Added simplified Socket.IO test page that doesn't require authentication
4. Added Socket.IO-specific health check endpoint
5. Disabled transport upgrades initially to ensure stable connections
6. Improved ping/pong frequency for better connection maintenance
7. Fixed session context issues in message processing
8. Added client-specific message handling
9. Improved WebSocket status visibility on the main page
10. Added test message functionality for easier debugging
11. Support for secure WebSockets (WSS) over HTTPS

## Quick Timeout Fix

If you're experiencing timeout issues, try these steps:

1. Visit the simple Socket.IO test page:
   ```
   https://nwn-persona.online/socket_test
   ```
   This page uses a minimal Socket.IO configuration and doesn't require login.

2. Check the Socket.IO health endpoint:
   ```
   https://nwn-persona.online/socket_health
   ```
   This will show detailed information about Socket.IO configuration.

3. If the simple test works but the main app doesn't, it's likely a session or authentication issue.

## How to Test WebSocket Connections

1. Start the application:
   ```
   python app.py
   ```

2. Check the server health at:
   ```
   https://nwn-persona.online/health
   ```

3. Try the simplified Socket.IO test page:
   ```
   https://nwn-persona.online/socket_test
   ```
   This is the fastest way to verify basic Socket.IO connectivity without authentication.

4. If that works, visit the full debug page at:
   ```
   https://nwn-persona.online/debug_websocket
   ```

5. Use the "Check Status" button to get detailed connection information

## Common Issues and Solutions

### 1. Connection Timeouts

**Symptoms:**
- "Connection error: timeout" messages in browser console
- Long waiting periods with no connection established
- Socket.IO health check works but regular connections fail

**Solutions:**
- We've reduced default timeouts from 20s to 5s to fail faster
- Disabled transport upgrades initially for more stable connections
- Try the `/socket_test` page which uses an even simpler configuration
- Check your network for any proxy or firewall issues

### 2. "Invalid WebSocket upgrade" errors

**Symptoms:**
- "Invalid websocket upgrade" messages in server logs
- Browser console shows "websocket error" messages
- Connection falls back to polling transport

**Solutions:**
- The server is now configured to use polling first, which is more reliable
- Check that your environment properly supports WebSockets
- Verify network/proxy settings don't block WebSocket connections
- Try the application in a different browser

### 3. Messages not reaching the frontend

**Symptoms:**
- Server logs show messages being processed but nothing appears in the browser
- No errors in browser console

**Solutions:**
- Verify client identification is correct (username should match session user)
- Use the test message feature to verify end-to-end communication
- Check browser console for any hidden errors
- Try restarting both the server and browser

### 4. HTTPS/WSS Connection Issues

**Symptoms:**
- Secure WebSocket connections fail while HTTP works
- Mixed content warnings in browser console
- Certificate warnings in browser

**Solutions:**
- Ensure all resources (scripts, styles, etc.) use HTTPS URLs
- Check browser console for mixed content warnings
- Verify that the Let's Encrypt certificate is valid and not expired
- Try accessing the site in a private/incognito window to rule out cache issues
- Check browser and operating system time settings (incorrect time can cause certificate validation issues)

## Advanced Troubleshooting

### Simplified Testing

The new `/socket_test` page provides a simple way to test Socket.IO connectivity without:
- Complex configuration
- Authentication requirements 
- Session handling

If this works but the main app doesn't, the issue is likely related to:
- Authentication/session handling
- More complex Socket.IO options
- CORS or cookie issues

### Connection Fallback Strategy

The application is now configured to use a fallback strategy:

1. First attempts to connect using HTTP long-polling only (most reliable)
2. Later may try to upgrade to WebSocket if configured
3. More frequent pings (every 5s instead of 25s) to maintain connection
4. Shorter timeouts (5-10s instead of 20s) to fail faster and retry

This ensures the application works even in environments where WebSockets aren't supported.

### Secure WebSocket (WSS) Configuration

When using HTTPS, the application automatically uses secure WebSockets (WSS):

1. All WebSocket connections use `wss://` protocol instead of `ws://`
2. WebSocket connections are encrypted using the same SSL certificate as HTTPS
3. The Nginx reverse proxy is configured to handle WebSocket upgrade requests properly
4. Socket.IO automatically handles the secure connection upgrade

## Using the Diagnostic Tools

### Socket.IO Health Check

The `/socket_health` endpoint provides detailed information about Socket.IO configuration:
- Socket.IO and Engine.IO versions
- Current async mode
- Ping interval and timeout settings 
- Allowed origins
- Available transports
- Security status (WSS enabled/disabled)

### Connection Details

The "Check Status" button on the debug page shows:
- Connection state (connected/disconnected)
- Socket ID
- Current transport method (polling/websocket)
- Security status (secure/insecure)
- Browser and environment information

## Need More Help?

If you're still experiencing issues after trying these solutions, please:

1. Try the simple `/socket_test` page and capture the logs
2. Check the `/socket_health` endpoint
3. Check server console logs for any error messages
4. Try using polling-only mode by modifying the transport order
5. Verify HTTPS certificate validity with tools like SSL Labs
6. Contact support with all of this information 