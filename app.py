import streamlit as st
import anthropic
import requests
import json

st.set_page_config(page_title="Job Posting Forensics", page_icon="🔍", layout="wide")

st.title("🔍 Job Posting Forensics")
st.markdown("*Decode what a company's hiring patterns really mean*")

ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
ADZUNA_APP_ID = st.secrets["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = st.secrets["ADZUNA_APP_KEY"]

def get_job_postings(company, role=None):
    url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": 50,
        "what_and": role if role else "",
        "where": "",
        "company": company,
        "content-type": "application/json"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

def analyze_postings(company, jobs_data, role=None):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    job_summary = []
    if jobs_data and "results" in jobs_data:
        for job in jobs_data["results"][:20]:
            job_summary.append({
                "title": job.get("title", ""),
                "created": job.get("created", ""),
                "location": job.get("location", {}).get("display_name", ""),
                "salary_min": job.get("salary_min", ""),
                "salary_max": job.get("salary_max", ""),
                "category": job.get("category", {}).get("label", "")
            })

    role_line = f"Role of interest: {role}" if role else ""
    role_intel_field = f'"role_intel": "<2-3 sentences specific to the {role} role>"' if role else '"role_intel": null'
    total = jobs_data.get("count", 0) if jobs_data else 0

    prompt = f"""You are a job market intelligence analyst. Analyze this hiring data for {company} and give a candidate intelligence brief.

Company: {company}
{role_line}
Total jobs found: {total}
Sample of current postings: {json.dumps(job_summary, indent=2)}

Provide analysis in this exact JSON format:
{{
  "hiring_velocity": "accelerating",
  "open_roles": 0,
  "avg_days_open": 0,
  "reposted_roles": 0,
  "departments": [
    {{"name": "dept name", "count": 0, "pct": 0}}
  ],
  "flags": [
    {{"type": "warning", "text": "observation"}}
  ],
  "strategic_signal": "2-3 sentences on what hiring patterns reveal",
  {role_intel_field},
  "recommendation": {{
    "verdict": "apply now",
    "title": "short punchy title",
    "body": "2-3 sentences of specific candidate advice"
  }}
}}

hiring_velocity must be one of: accelerating, stable, slowing, contracting
verdict must be one of: apply now, apply with caution, watch and wait, avoid for now
flag type must be one of: warning, info, positive

Return only valid JSON, no markdown, no explanation."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)

col1, col2 = st.columns([2, 1])
with col1:
    company = st.text_input("Company name", placeholder="e.g. Notion, Rippling, Carta...")
with col2:
    role = st.text_input("Role (optional)", placeholder="e.g. Account Executive")

if st.button("Analyze hiring patterns", type="primary"):
    if not company:
        st.error("Please enter a company name.")
    else:
        with st.spinner("Scanning job boards..."):
            jobs_data = get_job_postings(company, role)

        with st.spinner("Building intelligence brief..."):
            result = analyze_postings(company, jobs_data, role)

        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Open roles", result.get("open_roles", 0))
        col2.metric("Avg. days open", result.get("avg_days_open", 0))
        col3.metric("Reposted roles", result.get("reposted_roles", 0))
        col4.metric("Hiring velocity", result.get("hiring_velocity", "—"))

        st.subheader("Posting behavior flags")
        for flag in result.get("flags", []):
            if flag["type"] == "warning":
                st.warning(flag["text"])
            elif flag["type"] == "positive":
                st.success(flag["text"])
            else:
                st.info(flag["text"])

        st.subheader("Department breakdown")
        for d in result.get("departments", []):
            st.write(f"**{d['name']}** — {d['count']} roles ({d['pct']}%)")

        st.subheader("Strategic signal read")
        st.write(result.get("strategic_signal", ""))

        if role and result.get("role_intel"):
            st.subheader(f"Role intelligence: {role}")
            st.write(result.get("role_intel", ""))

        st.divider()
        verdict = result.get("recommendation", {})
        verdict_map = {
            "apply now": st.success,
            "apply with caution": st.warning,
            "watch and wait": st.info,
            "avoid for now": st.error
        }
        fn = verdict_map.get(verdict.get("verdict", ""), st.info)
        fn(f"**{verdict.get('title', '')}** — {verdict.get('body', '')}")