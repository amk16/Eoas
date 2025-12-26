#!/usr/bin/env python3
"""
Test script for Phase 7 - Analyze Transcript Endpoint

This script tests the /api/analyze endpoint by:
1. Registering a test user (or logging in)
2. Creating a character
3. Creating a session
4. Adding the character to the session
5. Analyzing a sample D&D transcript

Usage:
    python test_phase7.py
"""

import requests
import json
import sys
from typing import Optional

BASE_URL = "http://localhost:3001/api"

class Phase7Tester:
    def __init__(self):
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.character_id: Optional[int] = None
        self.session_id: Optional[int] = None
    
    def get_headers(self) -> dict:
        """Get headers with authentication token."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def register_or_login(self, email: str = "test@example.com", password: str = "testpass123"):
        """Register a new user or login if exists."""
        print("\n🔐 Step 1: Authenticating...")
        
        # Try to login first
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["token"]
                self.user_id = data["user"]["id"]
                print(f"✅ Logged in as {email}")
                return
        except:
            pass
        
        # If login fails, try to register
        try:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["token"]
                self.user_id = data["user"]["id"]
                print(f"✅ Registered and logged in as {email}")
                return
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            sys.exit(1)
        
        print("❌ Authentication failed")
        sys.exit(1)
    
    def create_character(self, name: str = "Gandalf", max_hp: int = 100):
        """Create a test character."""
        print(f"\n👤 Step 2: Creating character '{name}'...")
        
        response = requests.post(
            f"{BASE_URL}/characters",
            json={"name": name, "max_hp": max_hp},
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            self.character_id = data["id"]
            print(f"✅ Created character: {name} (ID: {self.character_id}, Max HP: {max_hp})")
        else:
            print(f"❌ Failed to create character: {response.text}")
            sys.exit(1)
    
    def create_session(self, name: str = "Test Session"):
        """Create a test session."""
        print(f"\n🎲 Step 3: Creating session '{name}'...")
        
        response = requests.post(
            f"{BASE_URL}/sessions",
            json={"name": name},
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            self.session_id = data["id"]
            print(f"✅ Created session: {name} (ID: {self.session_id})")
        else:
            print(f"❌ Failed to create session: {response.text}")
            sys.exit(1)
    
    def add_character_to_session(self):
        """Add character to session."""
        print(f"\n➕ Step 4: Adding character to session...")
        
        response = requests.post(
            f"{BASE_URL}/sessions/{self.session_id}/characters",
            json={"character_ids": [self.character_id]},
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            print(f"✅ Added character to session")
        else:
            print(f"❌ Failed to add character to session: {response.text}")
            sys.exit(1)
    
    def analyze_transcript(self, transcript: str):
        """Test the analyze endpoint."""
        print(f"\n🔍 Step 5: Analyzing transcript...")
        print(f"   Transcript: {transcript[:100]}...")
        
        response = requests.post(
            f"{BASE_URL}/analyze",
            json={
                "transcript": transcript,
                "session_id": self.session_id
            },
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Analysis successful!")
            print(f"   Found {data['count']} event(s)")
            print(f"\n   Events:")
            for i, event in enumerate(data['events'], 1):
                print(f"   {i}. {event['type'].upper()}: {event['amount']} to {event.get('character_name', 'Unknown')}")
                print(f"      Character ID: {event['character_id']}")
                print(f"      Segment: {event.get('transcript_segment', 'N/A')[:80]}...")
            return data
        else:
            print(f"❌ Analysis failed: {response.status_code}")
            print(f"   Response: {response.text}")
            sys.exit(1)
    
    def run_test(self):
        """Run the complete test suite."""
        print("=" * 60)
        print("Phase 7 Test Suite - Analyze Transcript Endpoint")
        print("=" * 60)
        
        # Sample D&D transcript with damage/healing events
        sample_transcript = """
        The goblin swings its rusty sword at Gandalf, dealing 15 points of damage. 
        Gandalf staggers back, his robes torn. The cleric quickly casts a healing spell, 
        restoring 20 hit points to Gandalf. The wizard then casts a fireball, 
        dealing 30 damage to the goblin. Another goblin attacks and hits Gandalf for 8 damage.
        """
        
        try:
            self.register_or_login()
            self.create_character()
            self.create_session()
            self.add_character_to_session()
            self.analyze_transcript(sample_transcript)
            
            print("\n" + "=" * 60)
            print("✅ All tests passed!")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    tester = Phase7Tester()
    tester.run_test()

