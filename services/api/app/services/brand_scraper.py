"""
Brand scraper — extracts branding (logo, colors, fonts, hero image) from a website.
Used to auto-populate career page branding from a customer's existing site.
"""

import colorsys
import logging
import re
from collections import Counter
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Fonts the builder supports
ALLOWED_HEADING_FONTS = [
    "Inter", "Poppins", "Roboto", "Open Sans", "Montserrat",
    "Playfair Display", "Lora", "DM Sans", "Lato",
]
ALLOWED_BODY_FONTS = [
    "Inter", "Roboto", "Open Sans", "Lato", "Source Sans Pro",
    "DM Sans", "Nunito",
]
# Combined lookup for matching
ALL_FONTS = set(ALLOWED_HEADING_FONTS + ALLOWED_BODY_FONTS)

_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
_URL_RE = re.compile(r"url\(['\"]?([^'\")\s]+)['\"]?\)")
_FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}{]+)", re.IGNORECASE)
_GOOGLE_FONTS_RE = re.compile(r"fonts\.googleapis\.com/css2?\?family=([^\"'&]+)")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class BrandKit(BaseModel):
    logo_url: str | None = None
    favicon_url: str | None = None
    hero_image_url: str | None = None
    colors: dict[str, str] = {}
    fonts: dict[str, str] = {}


def scrape_brand(url: str) -> BrandKit:
    """Fetch a website and extract branding elements."""
    try:
        html, final_url = _fetch_page(url)
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return BrandKit()

    soup = BeautifulSoup(html, "lxml")

    logo_url = _extract_logo(soup, final_url)
    favicon_url = _extract_favicon(soup, final_url)
    hero_image_url = _extract_hero_image(soup, final_url, html)
    colors = _extract_colors(soup, html)
    fonts = _extract_fonts(soup, html)

    return BrandKit(
        logo_url=logo_url,
        favicon_url=favicon_url,
        hero_image_url=hero_image_url,
        colors=colors,
        fonts=fonts,
    )


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _fetch_page(url: str) -> tuple[str, str]:
    """Fetch the page HTML. Returns (html, final_url)."""
    if not url.startswith("http"):
        url = f"https://{url}"
    with httpx.Client(
        timeout=15, follow_redirects=True, verify=True
    ) as client:
        resp = client.get(url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return resp.text, str(resp.url)


# ---------------------------------------------------------------------------
# Logo extraction
# ---------------------------------------------------------------------------

def _extract_logo(soup: BeautifulSoup, base_url: str) -> str | None:
    # 1. <img> in header/nav with "logo" in src, alt, or class
    for container_tag in ["header", "nav"]:
        container = soup.find(container_tag)
        if container:
            for img in container.find_all("img", limit=10):
                src = img.get("src", "")
                alt = img.get("alt", "")
                cls = " ".join(img.get("class", []))
                if any("logo" in s.lower() for s in [src, alt, cls]):
                    return _resolve(src, base_url)
            # If no explicit logo, take the first img in header
            first_img = container.find("img")
            if first_img and first_img.get("src"):
                return _resolve(first_img["src"], base_url)

    # 2. Any img on page with "logo" in attributes
    for img in soup.find_all("img", limit=30):
        src = img.get("src", "")
        alt = img.get("alt", "")
        cls = " ".join(img.get("class", []))
        if any("logo" in s.lower() for s in [src, alt, cls]):
            return _resolve(src, base_url)

    # 3. og:image as fallback (sometimes it's the logo)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return _resolve(og["content"], base_url)

    return None


def _extract_favicon(soup: BeautifulSoup, base_url: str) -> str | None:
    # Apple touch icon first (higher quality)
    for rel in ["apple-touch-icon", "icon", "shortcut icon"]:
        link = soup.find("link", rel=lambda r: r and rel in (r if isinstance(r, list) else [r]))
        if link and link.get("href"):
            return _resolve(link["href"], base_url)
    return None


# ---------------------------------------------------------------------------
# Hero image extraction
# ---------------------------------------------------------------------------

def _extract_hero_image(
    soup: BeautifulSoup, base_url: str, html: str
) -> str | None:
    # 1. Look for large images or background images in the first major section
    # Skip nav/header, look at the first few top-level sections
    body = soup.find("body")
    if not body:
        return None

    # Check for background-image in inline styles on early elements
    for el in body.find_all(True, limit=50):
        style = el.get("style", "")
        if "background-image" in style or "background:" in style:
            match = _URL_RE.search(style)
            if match:
                img_url = match.group(1)
                if _looks_like_image(img_url):
                    return _resolve(img_url, base_url)

    # 2. Look for large <img> near the top (skip small icons)
    for img in body.find_all("img", limit=20):
        # Skip imgs inside nav/header (likely logos)
        if img.find_parent("nav") or img.find_parent("header"):
            continue
        src = img.get("src", "")
        if not src:
            continue
        # Heuristic: skip tiny images (icons, tracking pixels)
        width = img.get("width", "")
        height = img.get("height", "")
        if width and str(width).isdigit() and int(width) < 100:
            continue
        if height and str(height).isdigit() and int(height) < 100:
            continue
        if _looks_like_image(src):
            return _resolve(src, base_url)

    # 3. og:image as final fallback
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return _resolve(og["content"], base_url)

    return None


# ---------------------------------------------------------------------------
# Color extraction
# ---------------------------------------------------------------------------

def _extract_colors(soup: BeautifulSoup, html: str) -> dict[str, str]:
    all_colors: list[str] = []

    # 1. <meta name="theme-color">
    theme = soup.find("meta", attrs={"name": "theme-color"})
    if theme and theme.get("content"):
        c = _normalize_color(theme["content"])
        if c:
            all_colors.append(c)

    # 2. CSS custom properties (--primary, --brand, etc.)
    style_blocks = " ".join(
        tag.string or "" for tag in soup.find_all("style")
    )
    for var_name, color in re.findall(
        r"--(primary|brand|main|accent|secondary|color-primary|color-brand)"
        r"\s*:\s*([^;}\s]+)",
        style_blocks,
        re.IGNORECASE,
    ):
        c = _normalize_color(color)
        if c:
            all_colors.append(c)

    # 3. Inline styles on header, nav, body, footer
    for tag_name in ["header", "nav", "body", "footer", "main"]:
        el = soup.find(tag_name)
        if el and el.get("style"):
            for c in _colors_from_style(el["style"]):
                all_colors.append(c)

    # 4. All hex and rgb colors from <style> blocks
    for match in _HEX_RE.finditer(style_blocks):
        c = _normalize_hex(match.group(0))
        if c:
            all_colors.append(c)
    for match in _RGB_RE.finditer(style_blocks):
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        all_colors.append(f"#{r:02x}{g:02x}{b:02x}")

    # 5. Inline styles across the page
    for el in soup.find_all(True, style=True, limit=100):
        for c in _colors_from_style(el["style"]):
            all_colors.append(c)

    # Filter out near-black, near-white, and grays — we want brand colors
    brand_colors = [c for c in all_colors if _is_brand_color(c)]
    neutral_colors = [c for c in all_colors if not _is_brand_color(c)]

    # Also collect dark background colors from header/nav/footer and CSS
    dark_bg_colors: list[str] = []
    for tag_name in ["header", "nav", "footer"]:
        el = soup.find(tag_name)
        if el and el.get("style"):
            for c in _colors_from_style(el["style"]):
                h_val = c.lstrip("#")
                r, g, b = int(h_val[:2], 16), int(h_val[2:4], 16), int(h_val[4:6], 16)
                lightness = (r + g + b) / (3 * 255)
                if lightness < 0.25:
                    dark_bg_colors.append(c)

    # Scan <style> blocks for background-color on header/nav/footer selectors
    for match in re.finditer(
        r"(?:header|nav|footer|\.header|\.nav|\.footer|\.navbar)"
        r"[^{]*\{[^}]*background(?:-color)?\s*:\s*([^;}\s]+)",
        style_blocks,
        re.IGNORECASE,
    ):
        c = _normalize_color(match.group(1))
        if c:
            h_val = c.lstrip("#")
            r, g, b = int(h_val[:2], 16), int(h_val[2:4], 16), int(h_val[4:6], 16)
            lightness = (r + g + b) / (3 * 255)
            if lightness < 0.25:
                dark_bg_colors.append(c)

    if brand_colors:
        freq = Counter(brand_colors)
        primary = freq.most_common(1)[0][0]
        # Try to find a second brand color
        secondary = None
        for color, _ in freq.most_common(5):
            if color != primary and _color_distance(primary, color) > 0.15:
                secondary = color
                break
        # If we found a dark background, use it as primary and the brand color as secondary
        if dark_bg_colors:
            dark_primary = Counter(dark_bg_colors).most_common(1)[0][0]
            if _color_distance(dark_primary, primary) > 0.15:
                return _build_palette(dark_primary, primary)
        return _build_palette(primary, secondary)

    # If no brand colors found, look at the most common non-white colors
    if neutral_colors:
        freq = Counter(neutral_colors)
        # Pick the darkest non-black color as primary
        for color, _ in freq.most_common(10):
            if color not in ("#000000", "#ffffff", "#fff", "#000"):
                return _build_palette(color, None)

    return _build_palette("#1B3025", None)  # Fallback to Winnow defaults


def _build_palette(primary: str, secondary: str | None) -> dict[str, str]:
    """Build a full 5-color palette from primary (and optional secondary)."""
    h, l, s = _hex_to_hls(primary)
    is_dark = l < 0.5

    if not secondary:
        # Generate a complementary accent
        accent_h = (h + 0.5) % 1.0
        secondary = _hls_to_hex(accent_h, 0.55, max(s, 0.5))

    # Accent: a lighter version of secondary
    sh, sl, ss = _hex_to_hls(secondary)
    accent = _hls_to_hex(sh, 0.85, max(ss, 0.3))

    # Text color should always be dark enough to read on white (l <= 0.25)
    if l <= 0.25:
        text = primary
    else:
        # Darken the primary for text
        text_l = max(l * 0.25, 0.08)
        text = _hls_to_hex(h, text_l, s)

    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "background": "#FFFFFF",
        "text": text,
    }


# ---------------------------------------------------------------------------
# Font extraction
# ---------------------------------------------------------------------------

def _extract_fonts(soup: BeautifulSoup, html: str) -> dict[str, str]:
    found_fonts: list[str] = []

    # 1. Google Fonts link tags
    for match in _GOOGLE_FONTS_RE.finditer(html):
        families = match.group(1)
        for family in families.split("|"):
            # Handle both CSS1 (family=Lato:400) and CSS2 (family=Lato:wght@400)
            name = family.split(":")[0].replace("+", " ").strip()
            if name:
                found_fonts.append(name)

    # 2. font-family in <style> blocks and inline styles
    all_styles = " ".join(
        tag.string or "" for tag in soup.find_all("style")
    )
    for el in soup.find_all(True, style=True, limit=50):
        all_styles += " " + (el.get("style", ""))

    for match in _FONT_FAMILY_RE.finditer(all_styles):
        families = match.group(1)
        for f in families.split(","):
            name = f.strip().strip("'\"").strip()
            if name and name.lower() not in (
                "sans-serif", "serif", "monospace", "cursive", "system-ui",
                "inherit", "initial", "-apple-system", "blinkmacsystemfont",
                "segoe ui", "arial", "helvetica", "helvetica neue",
            ):
                found_fonts.append(name)

    # Match against allowed fonts
    heading = "Inter"
    body = "Inter"
    for font in found_fonts:
        for allowed in ALL_FONTS:
            if font.lower() == allowed.lower():
                if heading == "Inter":
                    heading = allowed
                if body == "Inter":
                    body = allowed
                break

    # If we found multiple distinct fonts, use first for heading, second for body
    matched = []
    for font in found_fonts:
        for allowed in ALL_FONTS:
            if font.lower() == allowed.lower() and allowed not in matched:
                matched.append(allowed)
                break
    if len(matched) >= 2:
        heading, body = matched[0], matched[1]
    elif len(matched) == 1:
        heading = body = matched[0]

    return {"heading": heading, "body": body}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(url: str, base: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base, url)


def _looks_like_image(url: str) -> bool:
    lower = url.lower()
    return any(
        ext in lower
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif", "isteam"]
    )


def _normalize_color(value: str) -> str | None:
    value = value.strip()
    if value.startswith("#"):
        return _normalize_hex(value)
    match = _RGB_RE.match(value)
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _normalize_hex(h: str) -> str | None:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) == 6:
        return f"#{h.lower()}"
    if len(h) == 8:  # with alpha
        return f"#{h[:6].lower()}"
    return None


def _colors_from_style(style: str) -> list[str]:
    colors = []
    for match in _HEX_RE.finditer(style):
        c = _normalize_hex(match.group(0))
        if c:
            colors.append(c)
    for match in _RGB_RE.finditer(style):
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        colors.append(f"#{r:02x}{g:02x}{b:02x}")
    return colors


def _is_brand_color(hex_color: str) -> bool:
    """Return True if the color is a 'brand' color (not near-white/black/gray)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # Check saturation — grays have near-equal R, G, B
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    if max_c == 0:
        return False
    saturation = (max_c - min_c) / max_c
    lightness = (r + g + b) / (3 * 255)
    # Skip very light (>0.92) or very dark (<0.08) or low saturation (<0.15)
    return saturation > 0.15 and 0.08 < lightness < 0.92


def _color_distance(c1: str, c2: str) -> float:
    """Simple Euclidean distance in RGB space, normalized to 0-1."""
    h1, h2 = c1.lstrip("#"), c2.lstrip("#")
    r1, g1, b1 = int(h1[:2], 16), int(h1[2:4], 16), int(h1[4:6], 16)
    r2, g2, b2 = int(h2[:2], 16), int(h2[2:4], 16), int(h2[4:6], 16)
    return (((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5) / 441.7


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
