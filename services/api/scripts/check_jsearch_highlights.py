"""Check JSearch API job_highlights field."""

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("RAPIDAPI_KEY")
if not api_key:
    print("No RAPIDAPI_KEY found")
    exit()

headers = {
    "X-RapidAPI-Key": api_key,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}
params = {
    "query": "project manager healthcare",
    "page": "1",
    "num_pages": "1",
}

response = httpx.get(
    "https://jsearch.p.rapidapi.com/search", headers=headers, params=params, timeout=30
)

if response.status_code == 200:
    data = response.json()
    if data.get("data"):
        job = data["data"][0]
        print("=== JOB INFO ===")
        print(f"Title: {job.get('job_title')}")
        print(f"Company: {job.get('employer_name')}")
        print()
        print("=== JOB_HIGHLIGHTS ===")
        highlights = job.get("job_highlights")
        if highlights:
            print(json.dumps(highlights, indent=2))
        else:
            print("No job_highlights field")
        print()
        print("=== JOB_DESCRIPTION (first 500 chars) ===")
        desc = job.get("job_description", "")
        print(desc[:500])
else:
    print(f"Error: {response.status_code}")
