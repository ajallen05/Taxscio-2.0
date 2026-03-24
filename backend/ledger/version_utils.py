"""
Version comparison and hashing utilities for the ledger module.
Handles content-based versioning to detect actual changes in documents.
"""
import hashlib
import json
from typing import Optional, Dict, Any


def compute_content_hash(content_data: Optional[Dict[str, Any]]) -> str:
    """
    Compute a SHA256 hash of the document content.
    
    Args:
        content_data: Dictionary containing document fields
        
    Returns:
        Hex string of the content hash
    """
    if not content_data:
        return ""
    
    try:
        # Sort keys to ensure consistent hashing regardless of order
        serialized = json.dumps(content_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    except Exception:
        # Fallback if serialization fails
        return hashlib.sha256(str(content_data).encode()).hexdigest()


def has_content_changed(new_hash: str, previous_hash: Optional[str]) -> bool:
    """
    Check if document content has changed based on hash comparison.
    
    Args:
        new_hash: Hash of the new document content
        previous_hash: Hash of the previous document version
        
    Returns:
        True if content has changed, False if identical
    """
    if not previous_hash:
        # First upload always counts as a change
        return True
    
    return new_hash != previous_hash
