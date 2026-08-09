# Deploy Your Flask App as a Databricks App

## ⚠️ IMPORTANT: Flask Apps Cannot Run in Notebooks!

Your `app.py` is a **Flask web application** that must run as a **Databricks App**. 

The error `ModuleNotFoundError: No module named 'flask'` happens because:
- Notebooks on serverless compute don't have Flask installed
- Flask apps need a proper web server environment
- Your app needs to run 24/7 to serve web requests

## 📋 Prerequisites

Make sure your `requirements.txt` includes:

```txt
flask>=2.3.0
databricks-sdk>=0.20.0
```

## 🚀 Deployment Steps

### Step 1: Create a Databricks App

1. **Go to Databricks Apps UI**
   - In your Databricks workspace sidebar, click on **"Apps"**
   - Or navigate directly to: `/apps`

2. **Click "Create App"**

3. **Configure Your App:**
   ```
   Name: day-one-data-engineer
   Source Type: Workspace Files
   Source Path: /Users/valeria.s.caras@gmail.com/data-engineer-handbook-valst/day-one-data-engineer
   Command: ["python", "app.py"]
   ```

4. **Important Settings:**
   - ✅ Check "Enable App Serving"
   - Port: `8000` (or whatever port your app.py uses)
   - Compute: Select a cluster or use serverless (recommended)

### Step 2: Verify File Structure

Your app folder should have:

```
day-one-data-engineer/
├── app.py                    ← Main Flask app
├── agent_runner.py           ← AI agent logic
├── agent_tools.py            ← Tool functions
├── flask_agent_routes.py     ← Agent endpoints
├── lakebase.py              ← Database connection
├── requirements.txt          ← Dependencies
└── templates/
    ├── scenario_play.html    ← WITH AI chat UI ✅
    ├── test_chat.html        ← Test page
    └── ...
```

### Step 3: Start Your App

1. In the Apps UI, find your app
2. Click **"Start"**
3. Wait for status to change to **"Running"**
4. You'll see a URL like: `https://xxxxx.cloud.databricks.com/apps/xxxxx`

### Step 4: Test the AI Mentor

#### Option A: Test Page (Recommended First)

1. Visit: `https://your-app-url/test-chat`
2. Click "Test Endpoint"
3. You should see:
   ```json
   {
     "response": "...",
     "conversation_id": "...",
     "tool_calls": []
   }
   ```

#### Option B: In a Scenario

1. Visit: `https://your-app-url/`
2. Create/login as a user
3. Click on any scenario
4. **Scroll down** - you'll see the AI Mentor chat panel!
5. Type a question and click "Send"

## 🐛 Troubleshooting

### Issue: "Module not found" errors

**Solution:** Add missing packages to `requirements.txt` and restart the app

```bash
# Check your requirements.txt has:
flask>=2.3.0
databricks-sdk>=0.20.0
```

### Issue: AI Mentor panel doesn't appear

**Solution:** The chat UI is now in `scenario_play.html`. Make sure:
1. Your app is actually running (check Apps UI)
2. You're visiting the app URL (not localhost)
3. Hard refresh the page (Ctrl+F5 / Cmd+Shift+R)

### Issue: "WorkspaceClient() failed"

**Solution:** This happens if running locally. The app MUST run as a Databricks App to access Foundation Models.

### Issue: Chat endpoint returns 500 error

**Debug steps:**

1. **Check app logs** in the Apps UI
2. **Visit debug endpoint:** `https://your-app-url/debug/agent-test`
   - Should return: `{"status": "ok"}`
   - If error, check the error message
3. **Open browser console** (F12) when testing chat
   - Look for network errors
   - Check what the `/agent/chat` endpoint returns

### Issue: Nothing happens when clicking Send

**Solution:**

1. **Open browser console** (F12)
2. Look for JavaScript errors
3. Check Network tab for the `/agent/chat` request
4. If you see `CORS` errors, the app URL might be wrong

## 📊 Monitoring

### Check App Status

```
Apps UI → Your App → Status
```

Should show: **"Running"** ✅

### View Logs

```
Apps UI → Your App → Logs tab
```

You should see:
```
 * Running on http://0.0.0.0:8000
 * Running on all addresses (0.0.0.0)
```

### Test Endpoints

1. **Health check:** `GET /`
2. **Agent test:** `GET /debug/agent-test`
3. **Chat test:** `GET /test-chat`
4. **Agent chat:** `POST /agent/chat`

## 🎯 Quick Verification Checklist

- [ ] App is deployed and status is "Running"
- [ ] Can access app URL in browser
- [ ] `/test-chat` loads without errors
- [ ] Clicking "Test Endpoint" returns valid JSON
- [ ] Can see AI Mentor panel in scenario pages
- [ ] Browser console (F12) shows no errors
- [ ] Clicking Send triggers network request to `/agent/chat`

## 💡 Pro Tips

1. **Always test with `/test-chat` first** before trying the full scenario UI
2. **Check browser console** - it shows detailed error messages
3. **Watch app logs** in real-time while testing
4. **Use Ctrl+F5** to hard refresh after code changes

## 🆘 Still Stuck?

If the chat still doesn't work after deployment:

1. Visit `/test-chat` and click "Test Endpoint"
2. Copy the exact error message from:
   - Browser console (F12)
   - Network tab (the `/agent/chat` response)
   - App logs (from Apps UI)
3. Share those error messages for specific help

---

## Summary

✅ **DO:**
- Deploy as a Databricks App
- Test with `/test-chat` first
- Check browser console and app logs

❌ **DON'T:**
- Try to run Flask in a notebook
- Run `python app.py` locally (won't access Databricks Foundation Models)
- Expect Flask modules on serverless notebook compute

Your AI Mentor will work once the app is properly deployed! 🚀