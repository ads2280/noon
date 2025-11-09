#!/usr/bin/env python3
"""
Simple script to test JWT authentication setup.
Run this to verify SUPABASE_JWT_SECRET is configured correctly.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config import get_settings
    import jwt
    from datetime import datetime, timedelta, timezone

    def test_jwt_config():
        """Test that JWT secret is configured and can sign/verify tokens."""
        print("Testing JWT Authentication Configuration...")
        print("=" * 60)

        settings = get_settings()

        # Test 1: Check if JWT secret is configured
        print("\n1. Checking SUPABASE_JWT_SECRET configuration...")
        if not settings.supabase_jwt_secret:
            print("   ❌ FAILED: SUPABASE_JWT_SECRET is not configured")
            print("   → Set it in your .env file or environment variables")
            return False
        else:
            print(
                f"   ✅ PASSED: JWT secret is configured (length: {len(settings.supabase_jwt_secret)})"
            )

        # Test 2: Try to sign a test token
        print("\n2. Testing JWT token signing...")
        try:
            test_payload = {
                "sub": "test-user-id-123",
                "phone_number": "+1234567890",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iat": datetime.now(timezone.utc),
            }
            test_token = jwt.encode(
                test_payload, settings.supabase_jwt_secret, algorithm="HS256"
            )
            print(f"   ✅ PASSED: Successfully signed test token")
            print(f"   → Token preview: {test_token[:50]}...")
        except Exception as e:
            print(f"   ❌ FAILED: Could not sign token: {e}")
            return False

        # Test 3: Try to verify the test token
        print("\n3. Testing JWT token verification...")
        try:
            decoded = jwt.decode(
                test_token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            if decoded.get("sub") == "test-user-id-123":
                print("   ✅ PASSED: Successfully verified test token")
                print(f"   → Decoded user ID: {decoded.get('sub')}")
            else:
                print("   ❌ FAILED: Token verification returned wrong user ID")
                return False
        except jwt.ExpiredSignatureError:
            print("   ❌ FAILED: Token expired (shouldn't happen with 1 hour expiry)")
            return False
        except jwt.InvalidSignatureError:
            print("   ❌ FAILED: Invalid token signature")
            return False
        except Exception as e:
            print(f"   ❌ FAILED: Token verification error: {e}")
            return False

        # Test 4: Test with wrong secret (should fail)
        print("\n4. Testing JWT verification with wrong secret (should fail)...")
        try:
            wrong_secret = "wrong-secret-key"
            jwt.decode(
                test_token,
                wrong_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            print(
                "   ❌ FAILED: Token verification should have failed with wrong secret"
            )
            return False
        except jwt.InvalidSignatureError:
            print("   ✅ PASSED: Correctly rejected token with wrong secret")
        except Exception as e:
            print(f"   ⚠️  WARNING: Unexpected error: {e}")

        print("\n" + "=" * 60)
        print("✅ All JWT authentication tests passed!")
        print("\nYour authentication setup is working correctly.")
        print("You can now use the curl requests in TESTING_CURL_REQUESTS.md")
        return True

    if __name__ == "__main__":
        success = test_jwt_config()
        sys.exit(0 if success else 1)

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the noon-backend directory")
    print("and that dependencies are installed (run: uv sync)")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
