# OAuth Setup Instructions

## Fix Redirect URI Mismatch Error

You're getting `Error 400: redirect_uri_mismatch` because the redirect URI needs to be added to your Google Cloud Console credentials.

## Step-by-Step Instructions

### 1. Go to Google Cloud Console
Visit: https://console.cloud.google.com/apis/credentials

### 2. Find Your OAuth 2.0 Client
- Look for the client with ID: `570569347579-v5csdb08ecdk5iq6ra7hjeeg7sbpj4t7`
- Click on it to edit

### 3. Add Authorized Redirect URI
Since your credentials are configured as a "Web application", you need to add the redirect URI:

**Under "Authorized redirect URIs", click "ADD URI" and add:**
```
http://localhost:8080/
```

**Important:** Make sure to include:
- The trailing slash (`/`)
- Use `localhost` (not `127.0.0.1`)
- Port `8080`

### 4. Save
Click "SAVE" at the bottom of the page

### 5. Wait a few seconds
Google sometimes takes a moment to propagate the changes

### 6. Try Again
Run the token generation script again:
```bash
cd noon-agent
uv run python generate_token.py
```

## Alternative: Use Desktop App Credentials (Recommended)

If you want to use this as a desktop app (which is more appropriate for this use case):

1. In Google Cloud Console, create a new OAuth 2.0 Client ID
2. Choose "Desktop app" as the application type
3. Download the new credentials.json
4. Replace the current credentials.json with the new one

Desktop app credentials don't require redirect URI configuration for `run_local_server()`.

## Troubleshooting

If you still get the error after adding the redirect URI:
- Make sure you saved the changes in Google Cloud Console
- Wait 1-2 minutes for changes to propagate
- Try using `http://127.0.0.1:8080/` instead of `http://localhost:8080/`
- Check that there are no extra spaces in the redirect URI field

