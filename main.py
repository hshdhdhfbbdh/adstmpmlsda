import asyncio
import random
import requests
import re
import html
from js import document, window

BASE_URL = "https://api.mail.tm"

# --- Global State Variables ---
current_email = ""
current_password = ""
current_token = ""
current_code = ""
copied_code = False
copied_pass = False
stop_polling = False

# --- UI Element References ---
status_box = document.getElementById("status-box")
btn_generate = document.getElementById("btn-generate")
btn_copy_email = document.getElementById("btn-copy-email")
btn_check = document.getElementById("btn-check")
btn_copy_code = document.getElementById("btn-copy-code")
btn_copy_pass = document.getElementById("btn-copy-pass")
btn_show_email = document.getElementById("btn-show-email")
btn_generate_more = document.getElementById("btn-generate-more")
email_content = document.getElementById("email-content")
raw_email_data = document.getElementById("raw-email-data")

# --- Helper Functions ---
def update_status(text):
    status_box.innerHTML = f"<b>{text}</b>"

def hide_all_buttons():
    for btn in [btn_generate, btn_copy_email, btn_check, btn_copy_code, btn_copy_pass, btn_show_email, btn_generate_more]:
        btn.style.display = "none"

def get_domain():
    try:
        r = requests.get(f"{BASE_URL}/domains")
        r.raise_for_status()
        return random.choice(r.json()["hydra:member"])["domain"]
    except Exception as e:
        print(f"Error fetching domains: {e}")
        return None

def make_credentials():
    user = "user" + str(random.randint(100000, 999999))
    pwd = "Pass@" + str(random.randint(100000, 999999))
    return user, pwd

# --- Application Logic ---
async def generate_handler(e):
    global current_email, current_password, copied_code, copied_pass, stop_polling
    
    # Reset states for new cycle
    copied_code = False
    copied_pass = False
    stop_polling = True # Stop any lingering checkers
    email_content.style.display = "none"
    hide_all_buttons()
    
    update_status("Generating account...")
    btn_generate.disabled = True
    
    domain = await asyncio.to_thread(get_domain)
    if not domain:
        update_status("Network Error: Could not fetch domain.")
        btn_generate.style.display = "block"
        btn_generate.disabled = False
        return

    user, password = make_credentials()
    address = f"{user}@{domain}"
    
    try:
        r = await asyncio.to_thread(
            requests.post,
            f"{BASE_URL}/accounts",
            json={"address": address, "password": password}
        )
        if r.status_code in (200, 201):
            current_email = address
            current_password = password
            update_status(f"{address}")
            
            # Show next step buttons
            btn_copy_email.innerText = "Copy Email"
            btn_copy_email.style.display = "block"
            btn_check.style.display = "block"
        else:
            update_status(f"Failed to create: {r.status_code}")
            btn_generate.style.display = "block"
    except Exception as e:
        update_status("API Error during generation.")
        btn_generate.style.display = "block"
        
    btn_generate.disabled = False


def copy_email_handler(e):
    window.copyToClipboard(current_email)
    btn_copy_email.innerText = "Copied!"
    
async def check_handler(e):
    global current_token, stop_polling
    hide_all_buttons()
    update_status("Logging in...")
    
    try:
        r = await asyncio.to_thread(
            requests.post,
            f"{BASE_URL}/token",
            json={"address": current_email, "password": current_password}
        )
        if r.status_code == 200:
            current_token = r.json().get("token")
            stop_polling = False
            update_status("Waiting for email... (Refreshing every 5s)")
            asyncio.create_task(poll_for_email())
        else:
            update_status("Login failed. Try generating again.")
            btn_generate.style.display = "block"
    except Exception as e:
        update_status("Exception during login.")
        btn_generate.style.display = "block"

async def poll_for_email():
    global stop_polling, current_code
    headers = {"Authorization": f"Bearer {current_token}"}
    
    while not stop_polling:
        try:
            # 1. Check for messages
            def fetch_msg_list():
                r = requests.get(f"{BASE_URL}/messages", headers=headers)
                return r.json().get("hydra:member", []) if r.status_code == 200 else []
                
            messages = await asyncio.to_thread(fetch_msg_list)
            
            if messages:
                msg_id = messages[0]['id']
                
                # 2. Fetch full message content
                def fetch_full_msg():
                    r = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
                    return r.json() if r.status_code == 200 else {}
                    
                full_msg = await asyncio.to_thread(fetch_full_msg)
                
                if full_msg:
                    subject = full_msg.get("subject", "")
                    
                    # Extract first 6 numbers from the subject
                    # re.sub removes non-digits. We take up to the first 6 characters.
                    all_digits = re.sub(r'\D', '', subject)
                    current_code = all_digits[:6] if len(all_digits) >= 6 else all_digits
                    
                    raw_text = full_msg.get("text", "No text content.")
                    html_display = f"From: {html.escape(full_msg.get('from', {}).get('address', 'Unknown'))}\n"
                    html_display += f"Subject: {html.escape(subject)}\n\n"
                    html_display += html.escape(raw_text)
                    raw_email_data.innerText = html_display
                    
                    update_status("Email Received!")
                    stop_polling = True
                    show_post_receive_buttons()
                    break
                    
        except Exception as e:
            print(f"Polling error: {e}")
            
        if not stop_polling:
            await asyncio.sleep(5)

def show_post_receive_buttons():
    hide_all_buttons()
    btn_copy_code.innerText = f"Copy Code ({current_code})" if current_code else "Copy Code (Not Found)"
    btn_copy_pass.innerText = "Copy Pass"
    btn_show_email.innerText = "Show Full Email"
    
    btn_copy_code.style.display = "block"
    btn_copy_pass.style.display = "block"
    btn_show_email.style.display = "block"

def check_for_generate_more():
    if copied_code and copied_pass:
        btn_generate_more.style.display = "block"

def copy_code_handler(e):
    global copied_code
    if current_code:
        window.copyToClipboard(current_code)
    else:
        window.copyToClipboard("No code found")
    btn_copy_code.innerText = "Copied Code!"
    copied_code = True
    check_for_generate_more()

def copy_pass_handler(e):
    global copied_pass
    window.copyToClipboard(current_password)
    btn_copy_pass.innerText = "Copied Pass!"
    copied_pass = True
    check_for_generate_more()

def show_email_handler(e):
    if email_content.style.display == "none":
        email_content.style.display = "block"
        btn_show_email.innerText = "Hide Full Email"
    else:
        email_content.style.display = "none"
        btn_show_email.innerText = "Show Full Email"

# --- Assign Event Listeners ---
btn_generate.onclick = generate_handler
btn_copy_email.onclick = copy_email_handler
btn_check.onclick = check_handler
btn_copy_code.onclick = copy_code_handler
btn_copy_pass.onclick = copy_pass_handler
btn_show_email.onclick = show_email_handler
btn_generate_more.onclick = generate_handler # Restarts cycle
