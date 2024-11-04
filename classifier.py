import hashlib
import os
import base64
import openai
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


def format_url(url):
    """Ensure the URL starts with http:// or https://"""
    if not url.startswith(('http://', 'https://')):
        return 'http://' + url  # Default to http if no protocol is provided
    return url


async def load_and_screenshot(url):
    # Format the URL
    url = format_url(url)

    # Generate a unique filename for the screenshot
    filename = hashlib.md5(url.encode()).hexdigest() + ".png"
    image_path = os.path.join("/tmp", filename)
    img_base64 = ""

    # Use Playwright to load the URL and take a screenshot asynchronously
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=40000)  # 40 seconds timeout
        await page.screenshot(path=image_path)
        await browser.close()

    # Convert the screenshot to a base64-encoded string
    with open(image_path, "rb") as image_file:
        img_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    # Clean up by removing the temporary file
    os.remove(image_path)
    return img_base64


async def gpt_classification(url):
    print(url)
    # Take a screenshot of the webpage
    img_base64 = await load_and_screenshot(url)
    img_str = f"data:image/jpeg;base64,{img_base64}"

    # Define the prompt for classification
    prompt = """Please tell me if this webpage is a generic parked landing page, a live website with a real business, a nonactive domain. Some websites may have certain graphics on it blocking you from using the website because the website owner has locked down the account, this would be generic parked landing page, make sure you analyze the text of any popups or overlays to determine if the site is parked or is a live website. Please only give me a single answer such as:

    generic parked landing page
    live website
    nonactive domain
    """

    # Create the request to OpenAI with the prompt and image data
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

    # Extract and print the classification result
    result = response['choices'][0]['message']['content'].strip()
    return result
