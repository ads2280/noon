#!/usr/bin/env python3
"""Script to generate token.json for Google Calendar OAuth authentication."""

import sys
from pathlib import Path

# Add the noon_agent directory to the path
noon_agent_dir = Path(__file__).parent / "noon_agent"
sys.path.insert(0, str(noon_agent_dir.parent))

# Import directly from the module file to avoid __init__.py import issues
import importlib.util

spec = importlib.util.spec_from_file_location("gcal_wrapper", noon_agent_dir / "gcal_wrapper.py")
gcal_wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gcal_wrapper)
get_calendar_service = gcal_wrapper.get_calendar_service


def main():
    """Generate token.json by running the OAuth flow."""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    credentials_path = script_dir / "credentials.json"
    token_path = script_dir / "token.json"

    # Check if credentials.json exists
    if not credentials_path.exists():
        print(f"❌ Error: credentials.json not found at {credentials_path}")
        print("\nPlease:")
        print("1. Download your OAuth 2.0 credentials from Google Cloud Console")
        print("2. Save it as 'credentials.json' in the noon-agent directory")
        print("3. Run this script again")
        sys.exit(1)

    print("\n⚠️  IMPORTANT: Make sure you've configured the redirect URI in Google Cloud Console:")
    print("   1. Go to https://console.cloud.google.com/apis/credentials")
    print("   2. Click on your OAuth 2.0 Client ID")
    print("   3. Under 'Authorized redirect URIs', add: http://localhost:8000/")
    print("   4. Click 'Save'")
    print("\n   Starting OAuth flow in 3 seconds...")
    import time

    time.sleep(3)

    print(f"✓ Found credentials.json at {credentials_path}")
    print("\n🔐 Starting OAuth flow...")
    print("A browser window will open for you to authorize the application.")
    print("After authorization, token.json will be saved automatically.\n")

    try:
        # This will open a browser for OAuth and save token.json
        service = get_calendar_service(
            credentials_path=str(credentials_path), token_path=str(token_path)
        )

        # Test the connection by getting calendar list
        print("\n✓ Authentication successful!")
        print(f"✓ token.json saved at {token_path}")

        # Verify by getting calendar info
        calendar_list = service.calendarList().list().execute()
        primary_calendar = next(
            (cal for cal in calendar_list.get("items", []) if cal.get("primary")), None
        )

        if primary_calendar:
            print(f"\n✓ Connected to calendar: {primary_calendar.get('summary', 'Primary')}")
            print(f"  Calendar ID: {primary_calendar.get('id')}")

        print("\n✅ Setup complete! You can now use the calendar agent.")

    except Exception as e:
        print(f"\n❌ Error during OAuth flow: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure credentials.json is valid")
        print("2. Check that Google Calendar API is enabled in your project")
        print("3. Verify the OAuth consent screen is configured")
        sys.exit(1)


if __name__ == "__main__":
    main()
