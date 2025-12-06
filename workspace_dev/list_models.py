
import google.generativeai as genai
import os

API_KEY = "YOUR_GOOGLE_API_KEY_HERE" # User must replace this, or I can try to read from the other file if I could, but I can't read user's mind for the key if they didn't put it in the file yet. 
# Wait, the user *ran* the script, so they must have put the key in audit_script_gemini.py? 
# Or maybe they didn't? If they didn't, the error would be 403 or "invalid api key". 
# The error was 404 model not found. This implies auth worked but model name failed.

# I will try to read the key from audit_script_gemini.py using a mix of sed/grep to avoid printing it to logs if possible, 
# but for this script I'll just ask the user to run it or assume they can set the key.
# Actually, I can import the config from the other script?
# No, that runs the main block.

# Let's just hardcode the script to use the key from the environment or expect the user to have set it.
# PRO TIP: I can read the file `audit_script_gemini.py` to see if the user replaced the key.
# If they did, I can extract it (carefully).
# But if I write a new file, I have to ask them to paste it again.

# Better: create a script that imports the key from audit_script_gemini?
# But audit_script_gemini has `if __name__ == "__main__":` so safe to import?
# Yes.

from audit_script_gemini import API_KEY

genai.configure(api_key=API_KEY)

print("Listing available models...")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
