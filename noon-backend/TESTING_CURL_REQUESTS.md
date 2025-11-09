# Testing Curl Requests for Agent API

This document provides curl commands to test the authentication flow and agent endpoints.

## Prerequisites

1. **Set your base URL** (replace with your actual backend URL):
   ```bash
   export BASE_URL="http://localhost:8000"
   # Or for production:
   # export BASE_URL="https://api.noon.com"
   ```

2. **Get your Supabase JWT Secret** (needed to verify tokens work correctly):
   - This should be set in your `.env` file as `SUPABASE_JWT_SECRET`
   - You can find it in your Supabase project settings under API → JWT Secret

---

## Step 1: Health Check (No Auth Required)

Test that the server is running:

```bash
curl -X GET "${BASE_URL}/healthz" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "status": "ok"
}
```

---

## Step 2: Request OTP

Send an OTP to a phone number:

```bash
curl -X POST "${BASE_URL}/auth/otp" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+1234567890"
  }'
```

**Expected Response:**
```json
{}
```

**Note:** The OTP will be sent via SMS. In development, check your Supabase logs or use the Supabase dashboard to see the OTP code.

---

## Step 3: Verify OTP and Get Token

Verify the OTP code you received:

```bash
# Replace <OTP_CODE> with the code you received
curl -X POST "${BASE_URL}/auth/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+1234567890",
    "code": "<OTP_CODE>"
  }'
```

**Expected Response:**
```json
{
  "session": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "v1.abc123...",
    "token_type": "bearer",
    "expires_in": 3600
  },
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "phone": "+1234567890"
  }
}
```

**Save the access_token for subsequent requests:**
```bash
export ACCESS_TOKEN="<access_token_from_response>"
```

---

## Step 4: Test Agent Endpoint (Requires Google Account Linked)

### 4a. Test with Valid Token (but no Google account)

This should return an error about missing Google account:

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Show me my schedule this week"
  }'
```

**Expected Error Response (400):**
```json
{
  "detail": "User has no Google Calendar access token. Please link your Google account first."
}
```

### 4b. Test with Invalid Token

Test authentication error handling:

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_token_here" \
  -d '{
    "text": "Show me my schedule this week"
  }'
```

**Expected Error Response (401):**
```json
{
  "detail": "Invalid or expired token"
}
```

### 4c. Test with Missing Authorization Header

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Show me my schedule this week"
  }'
```

**Expected Error Response (403):**
```json
{
  "detail": "Not authenticated"
}
```

### 4d. Test with Valid Token and Google Account (Full Flow)

Once you have a user with a linked Google account:

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Show me my schedule this week"
  }'
```

**Expected Success Response:**
```json
{
  "tool": "schedule",
  "summary": "Schedule from 2024-01-15T00:00:00 to 2024-01-19T23:59:59:\nFound 5 events:\n- Team Meeting at 2024-01-15T14:00:00 (until 2024-01-15T15:00:00)\n...",
  "result": {
    "status": "success",
    "count": 5,
    "events": [...]
  },
  "success": true
}
```

---

## Step 5: Test Get Event Details Endpoint

### Get Event with Day Schedule

```bash
curl -X POST "${BASE_URL}/agent/event" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "event_id": "your-event-id-here",
    "calendar_id": "primary"
  }'
```

**Expected Success Response:**
```json
{
  "event": {
    "status": "success",
    "event_id": "your-event-id-here",
    "summary": "Team Meeting",
    "description": "...",
    "start": "2024-01-15T14:00:00",
    "end": "2024-01-15T15:00:00",
    "attendees": [...],
    ...
  },
  "day_schedule": {
    "status": "success",
    "count": 5,
    "events": [...]
  },
  "success": true
}
```

**Expected Error Response (404 - Event Not Found):**
```json
{
  "detail": "Event not found: <error message>"
}
```

---

## Step 6: Test Different Agent Actions

### Create Event

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Schedule a team meeting tomorrow at 2pm for 1 hour"
  }'
```

### Read Events

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "What events do I have today?"
  }'
```

### Search Events

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Find all meetings with Alice"
  }'
```

### Update Event

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Move the team meeting to 3pm"
  }'
```

### Delete Event

```bash
curl -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Cancel the team meeting"
  }'
```

---

## Complete Test Script

Here's a complete bash script to test the full flow:

```bash
#!/bin/bash

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
PHONE_NUMBER="+1234567890"  # Replace with your test phone number

echo "=== Testing Noon Backend API ==="
echo ""

# Step 1: Health Check
echo "1. Testing health check..."
curl -s -X GET "${BASE_URL}/healthz" | jq .
echo ""

# Step 2: Request OTP
echo "2. Requesting OTP..."
curl -s -X POST "${BASE_URL}/auth/otp" \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"${PHONE_NUMBER}\"}" | jq .
echo ""

# Step 3: Verify OTP (you'll need to enter the code manually)
echo "3. Please enter the OTP code you received:"
read -r OTP_CODE

echo "Verifying OTP..."
RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/verify" \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"${PHONE_NUMBER}\", \"code\": \"${OTP_CODE}\"}")

echo "$RESPONSE" | jq .

# Extract access token
ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.session.access_token')

if [ "$ACCESS_TOKEN" == "null" ] || [ -z "$ACCESS_TOKEN" ]; then
  echo "ERROR: Failed to get access token"
  exit 1
fi

echo ""
echo "Access token obtained: ${ACCESS_TOKEN:0:20}..."
echo ""

# Step 4: Test Agent Endpoint
echo "4. Testing agent endpoint..."
curl -s -X POST "${BASE_URL}/agent/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "text": "Show me my schedule this week"
  }' | jq .

echo ""
echo "=== Test Complete ==="
```

**Save as `test_api.sh` and run:**
```bash
chmod +x test_api.sh
./test_api.sh
```

---

## Troubleshooting

### Issue: "Supabase JWT secret is not configured"

**Solution:** Make sure `SUPABASE_JWT_SECRET` is set in your `.env` file:
```bash
SUPABASE_JWT_SECRET="your-jwt-secret-here"
```

You can find this in Supabase Dashboard → Settings → API → JWT Secret

### Issue: "Invalid or expired token"

**Possible causes:**
1. Token has expired (tokens typically expire after 1 hour)
2. Token was signed with a different JWT secret
3. Token format is incorrect

**Solution:** 
- Get a fresh token by verifying OTP again
- Ensure `SUPABASE_JWT_SECRET` matches the secret used to sign the token

### Issue: "Token missing subject claim"

**Solution:** The JWT token must have a `sub` (subject) claim containing the user ID. This should be automatically included by Supabase when you verify OTP.

### Issue: "User has no Google Calendar access token"

**Solution:** The user needs to link their Google account first:
1. Call `POST /google-accounts/oauth/start` to get OAuth URL
2. User authorizes in browser
3. OAuth callback completes the linking

---

## Testing JWT Token Manually

You can decode and inspect a JWT token using online tools or command line:

```bash
# Using jq and base64 (requires the token to be in ACCESS_TOKEN variable)
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .
```

This will show you the token payload including:
- `sub`: User ID
- `exp`: Expiration timestamp
- `phone_number`: User's phone number
- Other claims

---

## Environment Variables Checklist

Make sure these are set in your `.env` file:

```bash
# Required
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
SUPABASE_JWT_SECRET="your-jwt-secret"  # Critical for token verification

# Optional but recommended
SUPABASE_ANON_KEY="your-anon-key"

# Google OAuth (required for agent to work)
GOOGLE_CLIENT_ID="your-client-id"
GOOGLE_CLIENT_SECRET="your-client-secret"
GOOGLE_OAUTH_REDIRECT_URI="http://localhost:8000/google-accounts/oauth/callback"
GOOGLE_OAUTH_APP_REDIRECT_URI="noon://oauth/google"
```

---

## Quick Test Commands

**One-liner to test authentication:**
```bash
# Get token
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/verify" \
  -H "Content-Type: application/json" \
  -d '{"phone":"+1234567890","code":"123456"}' | jq -r '.session.access_token')

# Test agent
curl -X POST "http://localhost:8000/agent/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Show me my schedule"}'
```

