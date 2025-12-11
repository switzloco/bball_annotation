#!/usr/bin/env python3
"""
Test script to verify service account credentials can sign URLs
Usage: python test_credentials.py
"""

import os
import sys
from google.cloud import storage
from datetime import timedelta

def test_signing():
    """Test if current credentials can sign URLs"""

    # Check if credentials are set
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        print(f"✅ GOOGLE_APPLICATION_CREDENTIALS set to: {creds_path}")
        if not os.path.exists(creds_path):
            print(f"❌ ERROR: Key file does not exist at {creds_path}")
            return False
    else:
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set - using default credentials")

    try:
        # Initialize storage client
        client = storage.Client()
        print(f"✅ Storage client initialized")
        print(f"   Project: {client.project}")

        # Try to sign a test URL
        bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")
        print(f"\n🔍 Testing URL signing with bucket: {bucket_name}")

        bucket = client.bucket(bucket_name)
        blob = bucket.blob("test_video.mp4")  # Doesn't need to exist

        # Attempt to generate signed URL
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET"
        )

        print(f"✅ SUCCESS! Signed URL generated:")
        print(f"   {url[:100]}...")
        print(f"\n🎉 Video player should work with these credentials!")
        return True

    except Exception as e:
        error_str = str(e)
        print(f"\n❌ ERROR: {error_str}")

        if "private key" in error_str or "credentials" in error_str:
            print("\n💡 SOLUTION:")
            print("   1. Download service account key from GCP Console")
            print("   2. Save as 'key.json' in this directory")
            print("   3. Set environment variable:")
            print("      export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/key.json")
            print("   4. Run this test script again")

        return False

if __name__ == "__main__":
    print("🔐 Testing Service Account Credentials for Video Playback")
    print("=" * 60)
    print()

    success = test_signing()
    sys.exit(0 if success else 1)
