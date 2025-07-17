#!/usr/bin/env python3
"""
Final working GraphQL fetcher for Merge Conflict.
Fetches all packs and their cards (black/white with text only).
Saves to card_data/cards_final.json for Django import.
"""
import requests
import json
import os
from datetime import datetime

GRAPHQL_URL = "https://www.restagainsthumanity.com/api/graphql"
OUTPUT_DIR = "card_data"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def run_query(query):
    response = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise Exception(data["errors"])
    return data["data"]

def fetch_all_packs_and_cards():
    print(f"[{datetime.now()}] Fetching all packs and cards via GraphQL…")
    query = """
    query {
      packs {
        id
        name
        black {
          text
        }
        white {
          text
        }
      }
    }
    """
    data = run_query(query)
    return data["packs"]

def save_json(obj, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    print(f"✅ Saved: {path}")

def main():
    print("GraphQL Fetcher for Merge Conflict")
    print("=" * 50)
    try:
        all_packs = fetch_all_packs_and_cards()
        save_json(all_packs, "cards_final.json")
        print(f"\nDone! Fetched {len(all_packs)} packs.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()