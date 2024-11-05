import hashlib
import os
import base64
import openai
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

MAX_RETRIES = 3  # Maximum number of retry attempts

def format_url(url):
    """Ensure the URL starts with http:// or https://"""
    if not url.startswith(('http://', 'https://')):
        return 'https://' + url  # Default to http if no protocol is provided
    return url

async def load_and_screenshot(url, retries=MAX_RETRIES):
    url = format_url(url)
    filename = hashlib.md5(url.encode()).hexdigest() + ".png"
    image_path = os.path.join("/tmp", filename)
    img_base64 = ""

    for attempt in range(1, retries + 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=80000)
                await page.screenshot(path=image_path)
                await browser.close()

            # Convert screenshot to base64
            with open(image_path, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            os.remove(image_path)
            return img_base64  # Successful capture
        except Exception as e:
            print(f"Attempt {attempt} failed for {url}: {e}")
            if attempt == retries:
                print(f"Failed to capture screenshot for {url} after {retries} attempts")
                return None  # Return None if all retries fail
            await asyncio.sleep(1)  # Short delay before retrying

async def gpt_classification(url):
    print(url)
    img_base64 = await load_and_screenshot(url)
    if img_base64 is None:
        return "classification failure"  # Indicate failure if screenshot failed

    img_str = f"data:image/jpeg;base64,{img_base64}"
    prompt = """Please tell me if this webpage is a generic parked landing page, a live website with a real business, a nonactive domain. Some websites may have certain graphics on it blocking you from using the website because the website owner has locked down the account, this would be generic parked landing page, make sure you analyze the text of any popups or overlays to determine if the site is parked or is a live website. Please only give me a single answer such as:

    generic parked landing page
    live website
    nonactive domain
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": img_str}}
                    ],
                }
            ],
            max_tokens=50
        )

        result = response['choices'][0]['message']['content'].strip()
        return result
    except Exception as e:
        print(f"Failed to classify {url}: {e}")
        return "classification failure"  # Return failure on error
