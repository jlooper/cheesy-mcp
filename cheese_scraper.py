#!/usr/bin/env python3
"""
Cheese Image Scraper

This version scrapes cheese images and saves them locally.
The uploading is handled by a separate Node.js script.
"""

import os
import requests
import time
import hashlib
from pathlib import Path
import logging
from typing import List, Dict, Optional
import json
from datetime import datetime
import base64

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cheese_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CheeseScraper:
    def __init__(self):
        """Initialize the cheese image scraper."""
        
        self.output_dir = Path("scraped_cheese_images")
        self.output_dir.mkdir(exist_ok=True)
        
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        
        self.cheese_types = [
            'semi soft', 'bloomy', 'blue', 'hard', 'washed rind', 'fresh'
        ]
        
        self.min_width = 100
        self.min_height = 100
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
    def get_search_url(self, cheese_type: str) -> str:
        """Generate Google Image Search URL for a specific cheese type."""
        base_url = "https://www.google.com/search?"
        params = {
            'q': f'{cheese_type} cheese',
            'tbm': 'isch',
            'as_st': 'y',
            'imgtype': 'photo',
            'tbs': 'sur:cl',
        }
        return base_url + requests.compat.urlencode(params)

    def scrape_image_data(self, search_url: str, max_images: int) -> List[str]:
        """Scrape Base64 image data from a Google Images search results page."""
        logger.info(f"Scraping image data from: {search_url}")
        image_data_list = []
        driver = None
        try:
            service = Service()
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.get(search_url)

            # Wait for the inner img elements to be present inside the g-img wrappers
            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "g-img img"))
            )

            # Scroll down multiple times to ensure all images are loaded
            for _ in range(3): # Scroll 3 times
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            # Find all g-img wrapper elements
            g_img_elements = driver.find_elements(By.CSS_SELECTOR, "g-img")
                     
            for g_img in g_img_elements:
                try:
                    # Find the actual <img> tag inside the <g-img> wrapper
                    img = g_img.find_element(By.TAG_NAME, 'img')
                    src = img.get_attribute('src')
                    if src and src.startswith('data:image'):
                        if src not in image_data_list:
                            image_data_list.append(src)
                except Exception:
                    continue

            if not image_data_list:
                logger.warning(f"⚠️  Could not find any valid Base64 image data within <g-img> elements.")
                return []

            logger.info(f"Successfully extracted {len(image_data_list)} Base64 image sources.")
            return image_data_list[:max_images]
        
        except Exception as e:
            logger.error(f"Error scraping {search_url}: {e}", exc_info=True)
            return []
        finally:
            if driver:
                driver.quit()

    def save_base64_image(self, base64_data: str, filename: str) -> Optional[Path]:
        """Decode a Base64 string and save it as an image file."""
        try:
            header, encoded = base64_data.split(",", 1)
            image_data = base64.b64decode(encoded)

            if len(image_data) > self.max_file_size:
                logger.warning(f"Skipping large file generated from Base64 data.")
                return None

            file_path = self.output_dir / filename
            with open(file_path, 'wb') as f:
                f.write(image_data)

            # Re-enable size validation
            with Image.open(file_path) as img:
                if img.width < self.min_width or img.height < self.min_height:
                    logger.warning(f"Skipping small image: {filename} ({img.width}x{img.height})")
                    file_path.unlink()
                    return None
            
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to save Base64 image {filename}: {e}")
        return None

    def analyze_image_content(self, file_path: Path, cheese_type: str) -> Dict:
        """Generate tags and context for the image."""
        return {
            'tags': ['cheese', cheese_type],
            'context': {
                'source': 'google-images',
                'license': 'creative-commons',
                'scrape_date': datetime.now().strftime('%Y-%m-%d')
            }
        }

    def cleanup_local_images(self):
        """Remove all downloaded image files after processing."""
        try:
            image_files = list(self.output_dir.glob("*.jpg"))
            if image_files:
                logger.info(f"🧹 Cleaning up {len(image_files)} downloaded images...")
                for img_file in image_files:
                    img_file.unlink()
                logger.info("✅ Image cleanup completed.")
        except Exception as e:
            logger.warning(f"⚠️  Error during cleanup: {e}")

    def find_and_download_candidates(self, max_total_images: int = 12) -> List[Dict]:
        """
        Finds and downloads cheese images, returning a list of candidates for upload.
        """
        candidates_found = []
        processed_count = 0
        
        logger.info(f"🚀 Starting cheese image candidate search. Target: {max_total_images} images.")

        for cheese_type in self.cheese_types:
            if len(candidates_found) >= max_total_images:
                break
                
            logger.info(f"--- Starting search for '{cheese_type}' cheese ---")
            search_url = self.get_search_url(cheese_type)
            
            # For each category, we aim to get a few images
            images_per_type = max_total_images // len(self.cheese_types) + 1
            image_data_list = self.scrape_image_data(search_url, images_per_type)
        
            for b64_data in image_data_list:
                if len(candidates_found) >= max_total_images:
                    break
                
                processed_count += 1
                file_hash = hashlib.md5(b64_data.encode()).hexdigest()[:10]
                filename = f"{cheese_type.replace(' ', '_')}_{file_hash}.jpg"
                
                file_path = self.save_base64_image(b64_data, filename)
                if not file_path:
                    continue
                
                try:
                    metadata = self.analyze_image_content(file_path, cheese_type)
                    
                    candidate = {
                        'id': filename,
                        'file_path': str(file_path),
                        'cheese_type': cheese_type,
                        'metadata': metadata
                    }
                    candidates_found.append(candidate)
                    logger.info(f"✅ Found candidate: {filename} for type {cheese_type}")
                    
                except Exception as e:
                    logger.error(f"Error processing and analyzing {filename}: {e}")
            
            if len(candidates_found) >= max_total_images:
                logger.info("🎯 Reached maximum total image target.")
                break

        logger.info(f"Scraping session completed! Found {len(candidates_found)} total candidates.")
        return candidates_found

if __name__ == '__main__':
    scraper = CheeseScraper()
    candidates = scraper.find_and_download_candidates(5)
    print("\n--- Found Candidates ---")
    for cand in candidates:
        print(json.dumps(cand, indent=2))
    scraper.cleanup_local_images() 