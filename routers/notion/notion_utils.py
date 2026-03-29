"""
Notion API utilities for advanced operations
"""
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from supabase_client import supabase

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


class NotionAPIClient:
    """Client for interacting with Notion API"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = self._get_access_token()
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }
    
    def _get_access_token(self) -> str:
        """Get access token from database"""
        result = supabase.table("connected_accounts")\
            .select("access_token")\
            .eq("provider_id", self.user_id)\
            .eq("platform", "notion")\
            .execute()
        
        if not result.data:
            raise Exception("Notion not connected for this user")
        
        return result.data[0]["access_token"]
    
    def search(self, query: str = "", filter_type: str = None, page_size: int = 100) -> Dict:
        """Search for pages and databases"""
        search_data = {"page_size": page_size}
        
        if query:
            search_data["query"] = query
        
        if filter_type:
            search_data["filter"] = {
                "value": filter_type,
                "property": "object"
            }
        
        response = requests.post(
            f"{NOTION_BASE_URL}/search",
            headers=self.headers,
            json=search_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Search failed: {response.text}")
        
        return response.json()
    
    def get_page(self, page_id: str) -> Dict:
        """Get a specific page"""
        response = requests.get(
            f"{NOTION_BASE_URL}/pages/{page_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get page: {response.text}")
        
        return response.json()
    
    def get_page_content(self, page_id: str) -> Dict:
        """Get page content (blocks)"""
        response = requests.get(
            f"{NOTION_BASE_URL}/blocks/{page_id}/children",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get page content: {response.text}")
        
        return response.json()
    
    def create_page(self, parent_id: str, title: str, content: List[Dict] = None, 
                   properties: Dict = None, parent_type: str = "database") -> Dict:
        """Create a new page"""
        page_data = {
            "parent": {
                parent_type + "_id": parent_id
            },
            "properties": properties or {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
        }
        
        if content:
            page_data["children"] = content
        
        response = requests.post(
            f"{NOTION_BASE_URL}/pages",
            headers=self.headers,
            json=page_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to create page: {response.text}")
        
        return response.json()
    
    def update_page(self, page_id: str, properties: Dict) -> Dict:
        """Update page properties"""
        update_data = {"properties": properties}
        
        response = requests.patch(
            f"{NOTION_BASE_URL}/pages/{page_id}",
            headers=self.headers,
            json=update_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to update page: {response.text}")
        
        return response.json()
    
    def get_database(self, database_id: str) -> Dict:
        """Get database schema"""
        response = requests.get(
            f"{NOTION_BASE_URL}/databases/{database_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get database: {response.text}")
        
        return response.json()
    
    def query_database(self, database_id: str, filter_data: Dict = None, 
                      sorts: List[Dict] = None, page_size: int = 100) -> Dict:
        """Query database with filters and sorting"""
        query_data = {"page_size": page_size}
        
        if filter_data:
            query_data["filter"] = filter_data
        
        if sorts:
            query_data["sorts"] = sorts
        
        response = requests.post(
            f"{NOTION_BASE_URL}/databases/{database_id}/query",
            headers=self.headers,
            json=query_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to query database: {response.text}")
        
        return response.json()
    
    def create_database(self, parent_id: str, title: str, properties: Dict, 
                       parent_type: str = "page") -> Dict:
        """Create a new database"""
        database_data = {
            "parent": {
                parent_type + "_id": parent_id
            },
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }
            ],
            "properties": properties
        }
        
        response = requests.post(
            f"{NOTION_BASE_URL}/databases",
            headers=self.headers,
            json=database_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to create database: {response.text}")
        
        return response.json()
    
    def append_block_children(self, block_id: str, children: List[Dict]) -> Dict:
        """Add blocks to a page"""
        data = {"children": children}
        
        response = requests.patch(
            f"{NOTION_BASE_URL}/blocks/{block_id}/children",
            headers=self.headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to append blocks: {response.text}")
        
        return response.json()
    
    def delete_block(self, block_id: str) -> Dict:
        """Delete a block"""
        response = requests.delete(
            f"{NOTION_BASE_URL}/blocks/{block_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to delete block: {response.text}")
        
        return response.json()
    
    def get_users(self) -> Dict:
        """Get all users in the workspace"""
        response = requests.get(
            f"{NOTION_BASE_URL}/users",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get users: {response.text}")
        
        return response.json()
    
    def get_user(self, user_id: str = "me") -> Dict:
        """Get specific user info"""
        response = requests.get(
            f"{NOTION_BASE_URL}/users/{user_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get user: {response.text}")
        
        return response.json()


def create_text_block(text: str) -> Dict:
    """Helper to create a text block"""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": text
                    }
                }
            ]
        }
    }


def create_heading_block(text: str, level: int = 1) -> Dict:
    """Helper to create a heading block"""
    heading_type = f"heading_{level}"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": text
                    }
                }
            ]
        }
    }


def create_todo_block(text: str, checked: bool = False) -> Dict:
    """Helper to create a todo block"""
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": text
                    }
                }
            ],
            "checked": checked
        }
    }


def create_bulleted_list_block(text: str) -> Dict:
    """Helper to create a bulleted list item"""
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": text
                    }
                }
            ]
        }
    }


def create_numbered_list_block(text: str) -> Dict:
    """Helper to create a numbered list item"""
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": text
                    }
                }
            ]
        }
    }


def create_database_property(prop_type: str, **kwargs) -> Dict:
    """Helper to create database properties"""
    property_data = {"type": prop_type}
    
    if prop_type == "title":
        property_data["title"] = {}
    elif prop_type == "rich_text":
        property_data["rich_text"] = {}
    elif prop_type == "number":
        property_data["number"] = {"format": kwargs.get("format", "number")}
    elif prop_type == "select":
        property_data["select"] = {
            "options": kwargs.get("options", [])
        }
    elif prop_type == "multi_select":
        property_data["multi_select"] = {
            "options": kwargs.get("options", [])
        }
    elif prop_type == "date":
        property_data["date"] = {}
    elif prop_type == "checkbox":
        property_data["checkbox"] = {}
    elif prop_type == "url":
        property_data["url"] = {}
    elif prop_type == "email":
        property_data["email"] = {}
    elif prop_type == "phone_number":
        property_data["phone_number"] = {}
    
    return property_data