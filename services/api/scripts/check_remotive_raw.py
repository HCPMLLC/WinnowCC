"""Check raw Remotive API response for HTML."""

import httpx

response = httpx.get(
    "https://remotive.com/api/remote-jobs", params={"limit": 1}, timeout=30
)
if response.status_code == 200:
    data = response.json()
    jobs = data.get("jobs", [])
    if jobs:
        job = jobs[0]
        print(f"Title: {job.get('title')}")
        print(f"Company: {job.get('company_name')}")
        print()
        desc = job.get("description", "")
        has_html = any(
            tag in desc.lower()
            for tag in [
                "<p>",
                "<li>",
                "<ul>",
                "<strong>",
                "<br",
                "<div",
                "<h1",
                "<h2",
                "<h3",
            ]
        )
        print(f"Description contains HTML: {has_html}")
        print("\nFirst 1000 chars of description:")
        print(desc[:1000])
else:
    print(f"Error: {response.status_code}")
