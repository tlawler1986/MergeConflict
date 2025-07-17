#!/usr/bin/env python3
"""
Verify card counts from the GraphQL API
"""
import requests
import json

GRAPHQL_URL = "https://www.restagainsthumanity.com/api/graphql"
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

def count_cards():
    print("Fetching card counts from GraphQL API...")
    query = """
    query {
      packs {
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
    packs = data["packs"]
    
    total_packs = len(packs)
    total_black = 0
    total_white = 0
    
    print(f"\nPack details:")
    print("-" * 50)
    
    for pack in packs:
        black_count = len(pack.get("black", []))
        white_count = len(pack.get("white", []))
        total_black += black_count
        total_white += white_count
        print(f"{pack['name']}: {black_count}B / {white_count}W")
    
    print("-" * 50)
    print(f"\nAPI Totals:")
    print(f"Packs: {total_packs}")
    print(f"Black: {total_black}")
    print(f"White: {total_white}")
    print(f"Total cards: {total_black + total_white}")

if __name__ == "__main__":
    count_cards()