# Video Playback Setup Guide

## Problem
The video player shows this error:
```
⚠️ Could not load video player: you need a private key to sign credentials.
the credentials you are currently using <class 'google.auth.compute_engine.credentials.Credentials'>
just contains a token.
```

## Why This Happens
- Video playback requires **signed URLs** to serve GCS videos securely
- Signed URLs need a **service account with a private key**
- Compute Engine credentials are **token-based** and cannot sign URLs
- You need to use a **downloaded JSON key file** instead

## Solution: Download and Configure Service Account Key

### Step 1: Download Service Account Key

1. Go to [GCP Console → IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Find your **Qwiklabs User Service Account** (or the service account you want to use)
3. Click on the service account email
4. Go to **Keys** tab
5. Click **Add Key → Create new key**
6. Choose **JSON** format
7. Click **Create** - the key will download automatically

### Step 2: Save Key File

Save the downloaded JSON key as `key.json` in the `bball_annotation` directory:

```bash
# If you downloaded it to ~/Downloads/your-project-abc123.json
mv ~/Downloads/your-project-*.json /path/to/bball_annotation/key.json

# Or if you're already in the bball_annotation directory
mv ~/Downloads/your-project-*.json ./key.json
```

### Step 3: Set Environment Variable

The `run_local.sh` script will automatically detect `key.json` and set the environment variable.

**Or set it manually:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/key.json
```

### Step 4: Test Credentials

Run the test script to verify signing works:

```bash
python test_credentials.py
```

If successful, you should see:
```
✅ SUCCESS! Signed URL generated
🎉 Video player should work with these credentials!
```

### Step 5: Run the App

```bash
./run_local.sh
```

The video player should now work without errors! 🎉

## Alternative: Make Bucket Public (Not Recommended)

If you don't want to use service account keys, you can make your GCS bucket publicly readable:

```bash
gsutil iam ch allUsers:objectViewer gs://bball_project
```

**⚠️ Warning:** This makes ALL videos in the bucket publicly accessible to anyone with the URL.

## Troubleshooting

### "Key file does not exist"
- Make sure the file is named exactly `key.json` (not `key.json.txt` or similar)
- Verify it's in the `bball_annotation` directory: `ls -la key.json`

### "Permission denied" when generating signed URL
- Make sure the service account has `Storage Object Viewer` role on the bucket
- Grant access: `gsutil iam ch serviceAccount:YOUR-SA@PROJECT.iam.gserviceaccount.com:objectViewer gs://bball_project`

### Still not working?
- Check the service account has the right permissions in GCP Console
- Verify the JSON key file is valid (should start with `{"type": "service_account",...}`)
- Make sure you're using the correct bucket name in `.env`: `GCP_BUCKET_NAME=bball_project`

## What Gets Fixed

Once configured correctly:
- ✅ Video player appears at the top of analysis results
- ✅ Clickable timestamps jump to exact moments in the video
- ✅ No more credential errors
- ✅ Smooth video playback directly in the Streamlit app
