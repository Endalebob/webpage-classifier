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

MAX_RETRIES = 2  # Maximum number of retry attempts

def format_url(url):
    """Ensure the URL starts with http:// or https://"""
    if not url.startswith(('http://', 'https://')):
        return 'http://' + url  # Default to http if no protocol is provided
    return url

async def load_and_screenshot(url, retries=MAX_RETRIES):
    url = format_url(url)
    filename = hashlib.md5(url.encode()).hexdigest() + ".png"
    image_path = os.path.join("/tmp", filename)
    img_base64 = ""

    for attempt in range(1, retries + 1):
        try:
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)  # Use Firefox instead of Chromium
                page = await browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0")
                await page.goto(url, timeout=30000)
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


async def gpt_classification_without_image(url):
    print(f"Classifying without image for URL: {url}")

    prompt = f"""
Please classify the following webpage URL is provided. Determine if it is a generic parked landing page, a live website with a real business, or a nonactive domain:

URL: {url}

Please only give a single answer such as:
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
                    "content": prompt
                }
            ],
            max_tokens=50
        )

        result = response['choices'][0]['message']['content'].strip()
        return result
    except Exception as e:
        print(f"Failed to classify {url} without image: {e}")
        return "classification failure"  # Return failure on error


async def gpt_classification(url):
    print(url)
    img_base64 = await load_and_screenshot(url)
    if img_base64 is None:
        return await gpt_classification_without_image(url)

    img_str = f"data:image/jpeg;base64,{img_base64}"
    prompt = f"""
    Please classify the webpage based on the provided screenshot. Choose only one of the following options: 
    
    generic parked landing page
    live website
    nonactive domain

    Only return one of these options without additional commentary or explanation. Do not respond with anything other than these exact terms.
    URL: {url}
    Screenshot: (provided as image data)
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

        result = response['choices'][0]['message']['content'].strip().lower()
        # Ensure the output is one of the three expected options, default to "nonactive domain" if not
        if result not in ["generic parked landing page", "live website", "nonactive domain"]:
            result = "nonactive domain"
        return result
    except Exception as e:
        print(f"Failed to classify {url}: {e}")
        return "classification failure"  # Return failure on error
