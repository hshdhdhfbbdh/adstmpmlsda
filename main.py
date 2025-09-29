import asyncio
import json
import random
from datetime import datetime
import requests
from js import document, Blob, URL
import re
import html

# --- Global State ---
BASE_URL = "https://api.mail.tm"
STOP_GENERATION = False

# --- UI Element References ---
num_accounts_input = document.getElementById("num-accounts")
generate_btn = document.getElementById("generate-btn")
stop_generate_btn = document.getElementById("stop-generate-btn")
download_link = document.getElementById("download-link")
generator_output = document.getElementById("generator-output")
email_input = document.getElementById("email")
password_input = document.getElementById("password")
login_btn = document.getElementById("login-btn")
checker_output = document.getElementById("checker-output")

def gen_log(message):
    generator_output.innerText += f"{message}\n"
    generator_output.scrollTop = generator_output.scrollHeight

def linkify(text):
    """Escapes text and then converts URLs into clickable HTML links for security."""
    escaped_text = html.escape(text)
    url_pattern = re.compile(r'(https?://[^\s&lt;&gt;&quot;]+)')

    def make_link(match):
        url_from_escaped_text = match.group(0)
        href_url = html.unescape(url_from_escaped_text)
        return f'<a href="{href_url}" target="_blank" rel="noopener noreferrer">{url_from_escaped_text}</a>'

    return url_pattern.sub(make_link, escaped_text)

# ================================================
# == Account Generation Logic
# ================================================
def get_domain():
    try:
        r = requests.get(f"{BASE_URL}/domains")
        r.raise_for_status()
        return random.choice(r.json()["hydra:member"])["domain"]
    except Exception as e:
        gen_log(f"Error fetching domains: {e}")
        return None

def make_credentials():
    user = "user" + str(random.randint(100000, 999999))
    pwd = "Pass@" + str(random.randint(100000, 999999))
    return user, pwd

async def create_account():
    domain = await asyncio.to_thread(get_domain)
    if not domain:
        gen_log("Could not get a domain. Stopping.")
        return None, None

    rate_limit_attempt = 0
    while not STOP_GENERATION:
        user, password = make_credentials()
        address = f"{user}@{domain}"
        try:
            r = await asyncio.to_thread(
                requests.post,
                f"{BASE_URL}/accounts",
                json={"address": address, "password": password}
            )
            if r.status_code in (200, 201):
                gen_log(f"Success -> {address}:{password}")
                return address, password
            elif r.status_code == 422:
                gen_log("Address conflict, retrying...")
                continue
            elif r.status_code == 429:
                rate_limit_attempt += 1
                wait = 2 ** rate_limit_attempt
                gen_log(f"Rate limited. Retrying in {wait}s...")

                for _ in range(wait):
                    if STOP_GENERATION:
                        gen_log("Generation stopped during wait.")
                        return None, None
                    await asyncio.sleep(1)
                continue
            else:
                gen_log(f"API Error: {r.status_code} – {r.text}")
                return None, None
        except Exception as e:
            gen_log(f"Request exception: {e}. Retrying in 5s...")
            for _ in range(5):
                if STOP_GENERATION:
                    gen_log("Generation stopped during wait.")
                    return None, None
                await asyncio.sleep(1)

    return None, None

def stop_generator_handler(e):
    global STOP_GENERATION
    gen_log("\n! Stop request received. Finishing current task...")
    STOP_GENERATION = True
    stop_generate_btn.disabled = True

async def generate_handler(e):
    global STOP_GENERATION
    STOP_GENERATION = False

    generate_btn.disabled = True
    stop_generate_btn.style.display = "block"
    stop_generate_btn.disabled = False
    download_link.style.display = "none"
    generator_output.innerText = "Starting...\n"

    creds = []
    try:
        try:
            num_to_create = int(num_accounts_input.value)
        except ValueError:
            num_to_create = 0

        if 1 <= num_to_create <= 50:
            for i in range(num_to_create):
                if STOP_GENERATION:
                    gen_log("Generation stopped by user.")
                    break
                gen_log(f"--- Creating account {i+1}/{num_to_create} ---")
                email, pwd = await create_account()
                if email and pwd:
                    creds.append(f"{email}:{pwd}")
                else:
                    gen_log(f"Failed to create account {i+1}. Stopping.")
                    break
                await asyncio.sleep(1)
        else:
            gen_log("Please enter a number between 1 and 50.")
    finally:
        if creds:
            gen_log(f"\nGeneration finished. Total accounts: {len(creds)}")
            content = "\n".join(creds)
            filename = f"accounts_{datetime.now().strftime('%Y-%m-%d')}.txt"
            blob = Blob.new([content], { "type": "text/plain;charset=utf-8" })
            download_link.href = URL.createObjectURL(blob)
            download_link.download = filename
            download_link.style.display = "block"
        else:
            gen_log("\nNo accounts were generated successfully.")

        generate_btn.disabled = False
        stop_generate_btn.style.display = "none"

# ================================================
# == Mail Checker Logic
# ================================================
def get_token(email, password):
    try:
        r = requests.post(f"{BASE_URL}/token", json={"address": email, "password": password})
        if r.status_code == 200:
            return r.json().get("token")
        else:
            checker_output.innerHTML = f"<p>Login failed: {r.status_code} - {r.text}</p>"
            return None
    except Exception as e:
        checker_output.innerHTML = f"<p>Exception during login: {e}</p>"
        return None

async def fetch_and_display_messages(token):
    checker_output.innerHTML = "<p>Checking for messages...</p>"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        def fetch_all_messages():
            list_r = requests.get(f"{BASE_URL}/messages", headers=headers)
            list_r.raise_for_status()
            messages = list_r.json().get("hydra:member", [])

            full_messages = []
            for msg_summary in messages:
                msg_r = requests.get(f"{BASE_URL}/messages/{msg_summary['id']}", headers=headers)
                if msg_r.status_code == 200:
                    full_messages.append(msg_r.json())
            return full_messages

        all_messages = await asyncio.to_thread(fetch_all_messages)

        if not all_messages:
            checker_output.innerHTML = "<p>The inbox is empty.</p>"
            return

        checker_output.innerHTML = ""
        for msg_data in all_messages:
            msg_div = document.createElement('div')
            msg_div.className = 'message-box'
            subject = msg_data.get("subject", "(No Subject)")
            from_addr = msg_data.get("from", {}).get("address", "Unknown")
            date = msg_data.get("createdAt", "Unknown Date")
            raw_text = msg_data.get("text", "No text content.")
            linked_text = linkify(raw_text)

            html_content = f"<b>From:</b> {html.escape(from_addr)}<br>"
            html_content += f"<b>Subject:</b> {html.escape(subject)}<br>"
            html_content += f"<b>Date:</b> {html.escape(date.split('T')[0])}<br>"
            html_content += f"<pre>{linked_text}</pre>"
            msg_div.innerHTML = html_content

            checker_output.appendChild(msg_div)
    except Exception as e:
        checker_output.innerHTML = f"<p>Error fetching messages: {e}</p>"

async def login_handler(e):
    email = email_input.value.strip()
    password = password_input.value.strip()
    if not email or not password:
        checker_output.innerHTML = "<p>Please enter email and password.</p>"
        return

    checker_output.innerHTML = "<p>Logging in...</p>"
    login_btn.disabled = True
    try:
        token = await asyncio.to_thread(get_token, email, password)
        if token:
            await fetch_and_display_messages(token)
    finally:
        login_btn.disabled = False

# --- Assign Event Handlers ---
generate_btn.onclick = generate_handler
stop_generate_btn.onclick = stop_generator_handler
login_btn.onclick = login_handler
