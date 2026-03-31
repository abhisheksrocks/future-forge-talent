#!/usr/bin/env python3
"""Fetch, process, and generate partner logos for futureforgetalent.com."""

import os
import io
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

PARTNERS = [
    {"name": "Radian Finserv", "filename": "radian-finserv.png", "url": "https://radianfinserv.com/"},
    {"name": "NMAH and Co", "filename": "nmah-and-co.png", "url": "https://nmah.co.in/"},
    {"name": "Basic Home Loan", "filename": "basic-home-loan.png", "url": "https://www.basichomeloan.com/"},
    {"name": "Responssa", "filename": "responssa.png", "url": None},
    {"name": "Boxman Logistics", "filename": "boxman-logistics.png", "url": "https://www.boxmanlogistics.in/"},
    {"name": "Stockify", "filename": "stockify.png", "url": "https://stockify.net.in/"},
    {"name": "RYDR.One", "filename": "rydr-one.png", "url": "https://rydr.one/"},
    {"name": "Communn", "filename": "communn.png", "url": "https://www.onecommunn.com/"},
    {"name": "Joules to Watts", "filename": "joules-to-watts.png", "url": "https://www.joulestowatts.com/"},
    {"name": "Novus Tribe", "filename": "novus-tribe.png", "url": "https://novus-tribe.com/"},
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "site", "assets", "partners")
FONT_PATH = os.path.join(SCRIPT_DIR, "site", "assets", "fonts", "GothamBook.ttf")
LOGO_HEIGHT = 70
NAVY = (27, 42, 74)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_page(url):
    """Fetch HTML content of a URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def find_logo_url(html, base_url):
    """Extract logo image URL from page HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: og:image meta tag
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        url = urljoin(base_url, og["content"])
        print(f"  Found og:image: {url}")
        return url

    # Strategy 2: <img> with "logo" in src/alt/class inside header/nav
    for container_tag in ["header", "nav"]:
        for container in soup.find_all(container_tag):
            for img in container.find_all("img"):
                src = img.get("src", "")
                alt = img.get("alt", "")
                cls = " ".join(img.get("class", []))
                if re.search(r"logo", f"{src} {alt} {cls}", re.I):
                    url = urljoin(base_url, src)
                    print(f"  Found logo in <{container_tag}>: {url}")
                    return url

    # Strategy 3: Any element with class/id containing "logo" or "header", look for <img>
    for el in soup.find_all(True, {"class": re.compile(r"logo|header|brand|navbar", re.I)}):
        img = el.find("img")
        if img and img.get("src"):
            url = urljoin(base_url, img["src"])
            print(f"  Found logo in .{' '.join(el.get('class', []))}: {url}")
            return url

    # Strategy 4: Any <img> with "logo" in src or alt anywhere on the page
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        if re.search(r"logo", f"{src} {alt}", re.I):
            url = urljoin(base_url, src)
            print(f"  Found logo img on page: {url}")
            return url

    # Strategy 5: Favicon as last resort
    for link in soup.find_all("link", rel=True):
        if "icon" in " ".join(link["rel"]).lower():
            href = link.get("href")
            if href:
                url = urljoin(base_url, href)
                print(f"  Found favicon: {url}")
                return url

    return None


def download_image(url):
    """Download an image and return as PIL Image."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content))
    except Exception as e:
        print(f"  ERROR downloading {url}: {e}")
        return None


def remove_white_background(img, threshold=240):
    """Replace near-white pixels with transparency."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > threshold and g > threshold and b > threshold:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def process_logo(img, target_height=LOGO_HEIGHT):
    """Process a logo image: convert to RGBA, attempt bg removal, resize."""
    img = img.convert("RGBA")

    # Try rembg first
    try:
        from rembg import remove
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        result = remove(buf.read())
        img = Image.open(io.BytesIO(result)).convert("RGBA")
        print("  Background removed with rembg")
    except ImportError:
        # Fallback: remove white-ish background
        img = remove_white_background(img)
        print("  White background removed with threshold")

    # Crop to content (trim transparent edges)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Resize to target height
    if img.height > 0:
        ratio = target_height / img.height
        new_width = int(img.width * ratio)
        img = img.resize((new_width, target_height), Image.LANCZOS)

    return img


def generate_text_logo(name, target_height=LOGO_HEIGHT):
    """Generate a text-based logo using GothamBook font."""
    # Try to load the site's font
    font_size = 48
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()

    # Measure text
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), name, font=font)
    text_w = bbox[2] - bbox[0] + 40  # padding
    text_h = bbox[3] - bbox[1] + 20

    # Create image with transparent background
    img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x = (text_w - (bbox[2] - bbox[0])) // 2
    y = (text_h - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), name, fill=NAVY + (255,), font=font)

    # Crop and resize
    content_bbox = img.getbbox()
    if content_bbox:
        img = img.crop(content_bbox)

    if img.height > 0:
        ratio = target_height / img.height
        new_width = int(img.width * ratio)
        img = img.resize((new_width, target_height), Image.LANCZOS)

    return img


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}\n")

    for partner in PARTNERS:
        name = partner["name"]
        output_path = os.path.join(OUTPUT_DIR, partner["filename"])
        print(f"[{name}]")

        if partner["url"] is None:
            print("  No website — generating text logo")
            img = generate_text_logo(name)
            img.save(output_path, "PNG")
            print(f"  Saved: {partner['filename']}")
            print()
            continue

        # Fetch page
        html = fetch_page(partner["url"])
        if not html:
            print("  FALLBACK: generating text logo")
            img = generate_text_logo(name)
            img.save(output_path, "PNG")
            print(f"  Saved: {partner['filename']}")
            print()
            continue

        # Find logo URL
        logo_url = find_logo_url(html, partner["url"])
        if not logo_url:
            print("  No logo found — FALLBACK: generating text logo")
            img = generate_text_logo(name)
            img.save(output_path, "PNG")
            print(f"  Saved: {partner['filename']}")
            print()
            continue

        # Download logo
        img = download_image(logo_url)
        if not img:
            print("  Download failed — FALLBACK: generating text logo")
            img = generate_text_logo(name)
            img.save(output_path, "PNG")
            print(f"  Saved: {partner['filename']}")
            print()
            continue

        # Process logo
        try:
            img = process_logo(img)
            img.save(output_path, "PNG")
            print(f"  Saved: {partner['filename']}")
        except Exception as e:
            print(f"  Processing error: {e} — FALLBACK: generating text logo")
            img = generate_text_logo(name)
            img.save(output_path, "PNG")
            print(f"  Saved: {partner['filename']}")

        print()

    print(f"Done! Logos saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
