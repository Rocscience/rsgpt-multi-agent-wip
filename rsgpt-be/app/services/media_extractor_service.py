import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import logging
import aiohttp
import asyncio
import time
import logging
import asyncwhois
from app.models.media_link_greenlist import WHITELIST, SOURCE_URLS

async def fetch_html(session, url, timeout=10) -> str: 
    """
    Fetch HTML content from a URL using aiohttp.
    Args:
        session (aiohttp.ClientSession): The aiohttp session to use for the request.
        url (str): The URL to fetch.
        timeout (int): Timeout in seconds for the request.
    Returns:
        str: The HTML content of the page.
    """
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return ""

async def extract_single_url(session, url) -> tuple[str, list[str], list[str]]:
    """
    Extract images and YouTube video links from a single URL.
    Args:
        session (aiohttp.ClientSession): The aiohttp session to use for the request.
        url (str): The URL to extract media from.
    Returns:
        tuple: A tuple containing the URL, a list of images, and a list of YouTube videos.
    """
    images = []
    youtube_videos = []
    try:
        html = await fetch_html(session, url)
        if not html:
            return url, images, youtube_videos

        soup = BeautifulSoup(html, 'lxml')

        for img_tag in soup.find_all('img'):
            src = img_tag.get('src')
            if src and not src.startswith('data:'):
                full_url = urljoin(url, src)
                # Skip images with "button" in the URL path (case-insensitive) and SVG files
                if (
                    'button' not in full_url.lower()
                    and 'buttons' not in full_url.lower()
                    and not full_url.lower().endswith('.svg')
                ):
                    images.append(full_url)

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(url, href)
            if 'youtube.com' in full_url or 'youtu.be' in full_url:
                youtube_videos.append(full_url)
    except Exception as e:
        logging.warning(f"Error processing {url}: {e}") 
    return url, images, youtube_videos

async def a_extract_media_from_links(urls):
    """
    Asynchronous function to extract images and YouTube video links from a list of URLs.
    Args:
        urls (list): List of URLs to extract media from.
    Returns:
        tuple: A tuple containing structured image objects, YouTube videos, and detailed results.
    """
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [extract_single_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    
    all_image_objects = []
    all_youtube_videos = []

    for source_url, images, youtube_videos in results:
        # Create image objects with both image_url and source_url
        for image_url in images:
            image_obj = {
                "image_url": image_url,
                "source_url": source_url
            }
            all_image_objects.append(image_obj)
        
        all_youtube_videos.extend(youtube_videos)

    # Remove duplicate images based on image_url
    seen_image_urls = set()
    unique_image_objects = []
    for img_obj in all_image_objects:
        if img_obj["image_url"] not in seen_image_urls:
            seen_image_urls.add(img_obj["image_url"])
            unique_image_objects.append(img_obj)
    
    # Remove duplicate YouTube videos
    all_youtube_videos = list(set(all_youtube_videos))
    
    return unique_image_objects, all_youtube_videos, results

async def is_reachable_url(url):
    """ 
    Check if a URL is reachable by sending a HEAD request.
    Args:
        url (str): The URL to check.
    Returns:
        bool: True if the URL is reachable, False otherwise.
    """
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(url, allow_redirects=True) as response:
                return response.status == 200
        except Exception as e:
            logging.error(f"Error checking {url}: {e}")
            return False

async def is_allowed_link(url):
    """
    Check if a URL is allowed based on its domain.
    Args:
        url (str): The URL to check.
    Returns:
        bool: True if the URL is allowed, False otherwise.
    """
    # Define the disallowed extensions
    skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                      '.zip', '.rar', '.tar', '.gz', '.exe', '.dmg', '.pkg',
                      '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flv']
    
    url_lower = url.lower()
    
    # Check for file extensions (including with anchors like .pdf#page=1)
    for ext in skip_extensions:
        if url_lower.endswith(ext) or f'{ext}#' in url_lower or f'{ext}?' in url_lower:
            logging.warning(f"Skipping file with extension {ext}: {url}")
            return False

    try:
        s, w = await asyncwhois.aio_whois(url)
    except Exception as e:
        logging.warning(f"Error fetching WHOIS data for {url}: {e}")
        return False
    try:
        # Extract domain name using regex
        domain_match = re.search(r'Domain Name:\s*([^\s\n]+)', s, re.IGNORECASE)
        registrar_match = re.search(r'Registrar:\s*([^\n]+)', s, re.IGNORECASE)
        
        if not domain_match or not registrar_match:
            logging.warning(f"Could not extract domain name or registrar from WHOIS data for {url}")
            return False
            
        domain_name = domain_match.group(1).lower()
        registrar = registrar_match.group(1).strip().lower()
        
        id_package = {"domain_name": domain_name, "registrar": registrar}
    except Exception as e:
        logging.warning(f"Error when processing WHOIS data for {url}: {e}")
        return False
    # Check if the id_package matches any entry in the WHITELIST
    # Whitelist is defined in the media_link_greenlist.py file
    if id_package not in WHITELIST:
        logging.warning(f"Domain {domain_name} is not in the whitelist.")
        return False

    return True
    


async def extract_media_from_sources(sources_used: list[str]) -> dict:
    """
    Extract media from sources used in the response.
    Args:
        sources_used (list[str]): List of source identifiers (e.g., ["ROC", "DIANA"])
    Returns:
        dict: Media data with images and YouTube videos
    """
    urls_to_scrape = []

    for source in sources_used:
        if source in SOURCE_URLS:
            urls_to_scrape.append(SOURCE_URLS[source])
        else:
            logging.warning(f"Unknown source: {source}, skipping media extraction")

    if not urls_to_scrape:
        logging.info("No valid sources found for media extraction")
        return {"images": [], "videos": []}

    # Extract media from the source URLs
    images, videos, _ = await a_extract_media_from_links(urls_to_scrape)

    return {
        "images": images,
        "videos": videos
    }

async def extract_media_from_urls(urls: list[str]) -> dict:
    """
    Extract media from a list of URLs directly.
    Args:
        urls (list[str]): List of URLs to extract media from
    Returns:
        dict: Media data with images and YouTube videos
    """
    if not urls:
        logging.info("No URLs provided for media extraction")
        return {"images": [], "videos": []}

    # Filter URLs to only include those that are allowed
    valid_urls = []
    for url in urls:
        try:
            if await is_allowed_link(url):
                valid_urls.append(url)
            else:
                logging.warning(f"URL not allowed by WHOIS: {url}")
        except Exception as e:
            logging.warning(f"Error validating URL {url}: {e}")

    if not valid_urls:
        logging.info("No valid URLs found for media extraction")
        return {"images": [], "videos": []}

    # Extract media from the valid URLs
    images, videos, _ = await a_extract_media_from_links(valid_urls)

    # Cap total media items to 15 (images + videos combined)
    all_media = images + videos
    if len(all_media) > 15:
        # Prioritize images, then videos
        capped_images = images[:15]
        capped_videos = videos[:max(0, 15 - len(capped_images))]
        images = capped_images
        videos = capped_videos

    return {
        "images": images,
        "videos": videos
    }

async def extract_source_link_from_text(response_text) -> list[str]:
    """
    Extracts URLs from the given text using regex.
    Args:
        response_text (str): The text to extract URLs from.
    Returns:
        list: A list of extracted URLs.
    """

    # Regex pattern to extract URLs
    # (https?://[^\s\]\),>]+)

    # Explanation:
    # - https?://     -> Matches 'http://' or 'https://' (This will start the extraction)
    # - [^\s\]\),>]+  -> Matches one or more characters that are NOT: (When it detects any of these characters, it stops the extraction)
    #                    - whitespace (\s)
    #                    - closing square bracket (])
    #                    - closing parenthesis ())
    #                    - comma (,)
    #                    - angle bracket (>)
    # This helps avoid including common trailing punctuation that often follows URLs in natural text.
    url_pattern = r'(https?://[^\s\]\),>]+)'
    links = re.findall(url_pattern, response_text)

    # Remove duplicates
    links = list(set(links))

    # Filter valid and reachable links
    valid_links = []

    for link in links:
        logging.info(f"Checking link: {link}")
        if not await is_reachable_url(link):
            logging.warning(f"Link is NOT reachable: {link}")
            continue
        if not await is_allowed_link(link):
            logging.warning(f"Link is NOT ALLOWED BY WHOIS: {link}")
            continue

        valid_links.append(link)
    return valid_links

