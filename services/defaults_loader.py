"""
Local Defaults Loader - Automatically loads default documents to speed up development
"""

import os
import json
import pickle
import streamlit as st
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class LocalDefaultsLoader:
    """Loads and saves default documents and processed data for faster development"""
    
    def __init__(self):
        self.defaults_dir = "local_defaults"
        self.documents_dir = os.path.join(self.defaults_dir, "documents")
        self.processed_dir = os.path.join(self.defaults_dir, "processed")
        
        # Ensure directories exist
        os.makedirs(self.documents_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
    
    def save_uploaded_files(self, uploaded_files: List[Any]) -> bool:
        """Save uploaded files to local defaults for future use"""
        try:
            saved_files = []
            for uploaded_file in uploaded_files:
                if uploaded_file is not None:
                    file_path = os.path.join(self.documents_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_files.append(uploaded_file.name)
                    logger.info(f"💾 Saved default document: {uploaded_file.name}")
            
            if saved_files:
                # Save metadata about saved files
                metadata = {
                    "files": saved_files,
                    "count": len(saved_files)
                }
                metadata_path = os.path.join(self.documents_dir, "_metadata.json")
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)
                
                logger.info(f"✅ Saved {len(saved_files)} files as defaults")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to save defaults: {e}")
        return False
    
    def load_default_files(self) -> List[str]:
        """Load list of available default files"""
        try:
            files = []
            if os.path.exists(self.documents_dir):
                for filename in os.listdir(self.documents_dir):
                    if filename.endswith(('.pdf', '.docx', '.txt')) and not filename.startswith('_'):
                        files.append(filename)
            return sorted(files)
        except Exception as e:
            logger.error(f"❌ Failed to load default files: {e}")
            return []
    
    def get_default_file_path(self, filename: str) -> Optional[str]:
        """Get the full path to a default file"""
        file_path = os.path.join(self.documents_dir, filename)
        return file_path if os.path.exists(file_path) else None
    
    def save_processed_data(self, data_key: str, data: Any) -> bool:
        """Save processed data (like vector DB, extracted text, etc.)"""
        try:
            file_path = os.path.join(self.processed_dir, f"{data_key}.pkl")
            with open(file_path, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"💾 Saved processed data: {data_key}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save processed data {data_key}: {e}")
            return False
    
    def load_processed_data(self, data_key: str) -> Optional[Any]:
        """Load processed data if it exists"""
        try:
            file_path = os.path.join(self.processed_dir, f"{data_key}.pkl")
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
                logger.info(f"📁 Loaded processed data: {data_key}")
                return data
        except Exception as e:
            logger.error(f"❌ Failed to load processed data {data_key}: {e}")
        return None
    
    def get_processed_data_keys(self) -> List[str]:
        """Get list of available processed data keys"""
        try:
            keys = []
            if os.path.exists(self.processed_dir):
                for filename in os.listdir(self.processed_dir):
                    if filename.endswith('.pkl'):
                        keys.append(filename[:-4])  # Remove .pkl extension
            return sorted(keys)
        except Exception as e:
            logger.error(f"❌ Failed to get processed data keys: {e}")
            return []
    
    def clear_defaults(self) -> bool:
        """Clear all default files and processed data"""
        try:
            # Clear documents
            if os.path.exists(self.documents_dir):
                for filename in os.listdir(self.documents_dir):
                    file_path = os.path.join(self.documents_dir, filename)
                    os.remove(file_path)
            
            # Clear processed data
            if os.path.exists(self.processed_dir):
                for filename in os.listdir(self.processed_dir):
                    file_path = os.path.join(self.processed_dir, filename)
                    os.remove(file_path)
            
            logger.info("🗑️ Cleared all defaults")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear defaults: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of default files and processed data"""
        default_files = self.load_default_files()
        processed_keys = self.get_processed_data_keys()
        
        return {
            "default_files": default_files,
            "default_files_count": len(default_files),
            "processed_data_keys": processed_keys,
            "processed_data_count": len(processed_keys),
            "has_defaults": len(default_files) > 0 or len(processed_keys) > 0
        }

# Global instance
defaults_loader = LocalDefaultsLoader()