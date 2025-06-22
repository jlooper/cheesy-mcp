#!/usr/bin/env python3
"""
Daily Cheese Scraping AI Agent
Autonomous agent that finds cheese images and prepares them for an AI assistant
to upload using MCP tools.
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from cheese_scraper import CheeseScraper

class CheeseScrapingAgent:
    def __init__(self):
        """Initialize the autonomous cheese scraping agent."""
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / "cheese_agent_output"
        self.output_dir.mkdir(exist_ok=True)
        
        self.state_file = self.output_dir / "agent_state.json"
        self.daily_log_dir = self.output_dir / "daily_logs"
        self.daily_log_dir.mkdir(exist_ok=True)
        
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = self.daily_log_dir / f"cheese_agent_{today}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)
        
        self.daily_target = 10
        self.state = self.load_agent_state()
        
        self.logger.info("🤖 Cheese Scraping Agent initialized")
        
        try:
            self.scraper = CheeseScraper()
            self.logger.info("✅ Scraper initialized successfully.")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize: {e}", exc_info=True)
            self.scraper = None

    def load_agent_state(self) -> Dict:
        """Load the agent's persistent state."""
        default_state = {
            'total_images_scraped': 0,
            'pending_uploads': [],
            'daily_stats': {},
        }
        
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                for key, value in default_state.items():
                    if key not in state:
                        state[key] = value
                return state
            except Exception as e:
                self.logger.warning(f"Failed to load agent state: {e}")
        
        return default_state
    
    def save_agent_state(self):
        """Save the agent's current state."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save agent state: {e}")

    def run(self):
        """
        Execute a scraping run to find and queue candidates.
        """
        if not self.scraper:
            self.logger.error("❌ Scraper not available. Aborting run.")
            return

        self.logger.info("🚀 Starting scraping mission...")
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        try:
            candidates = self.scraper.find_and_download_candidates(self.daily_target)
            if not candidates:
                self.logger.info("No new candidates found in this run.")
                return

            self.logger.info(f"Found {len(candidates)} new candidate images.")
            
            # Prepare candidates for MCP tool call
            pending_list = []
            for cand in candidates:
                file_path = Path(cand['file_path'])
                file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()[:8]
                public_id = f"cheese-collection/{file_path.stem}_{file_hash}"
                context_str = '|'.join([f'{k}={v}' for k, v in cand['metadata']['context'].items()])

                pending_list.append({
                    "file_path": f"file://{file_path.resolve()}",
                    "public_id": public_id,
                    "tags": ",".join(cand['metadata']['tags']),
                    "context": context_str
                })

            # Add new candidates to state, avoiding duplicates
            existing_paths = {p['file_path'] for p in self.state['pending_uploads']}
            new_candidates_added = 0
            for pending_item in pending_list:
                if pending_item['file_path'] not in existing_paths:
                    self.state['pending_uploads'].append(pending_item)
                    existing_paths.add(pending_item['file_path'])
                    new_candidates_added +=1
            
            self.state['total_images_scraped'] += new_candidates_added
            
            # Update or initialize daily stats
            if today_str not in self.state['daily_stats']:
                self.state['daily_stats'][today_str] = {'scraped': 0}
            self.state['daily_stats'][today_str]['scraped'] += new_candidates_added
            
            self.logger.info(f"✅ Added {new_candidates_added} new candidates to the upload queue.")
            self.logger.info("🎯 Mission complete!")
            self.logger.info("\n" + "="*50)
            self.logger.info("📣 The agent has found new images!")
            self.logger.info(f"   There are now {len(self.state['pending_uploads'])} images pending upload.")
            self.logger.info("   Ask your AI assistant to upload them for you.")
            self.logger.info("="*50 + "\n")

        except Exception as e:
            self.logger.error(f"❌ Agent run failed: {e}", exc_info=True)
        finally:
            self.save_agent_state()

if __name__ == '__main__':
    agent = CheeseScrapingAgent()
    agent.run() 