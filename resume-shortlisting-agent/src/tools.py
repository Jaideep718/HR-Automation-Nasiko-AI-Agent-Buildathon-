
"""
Tools for the HR Resume Screening Agent.
"""

import json
import random
import requests
import pandas as pd
import uuid

from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI
import numpy as np

load_dotenv()
client = OpenAI()


# ---------- LLM INITIALIZATION ----------

llm = ChatOpenAI(model="gpt-4o", temperature=0)
SKILL_ALIASES = {
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp"],
    "artificial intelligence": ["ai"],
    "computer vision": ["cv"],

    "static timing analysis": ["sta"],
    "design for testability": ["dft"],
    "register transfer level": ["rtl"],

    "javascript": ["js"],
    "typescript": ["ts"],
    "node.js": ["node"],

    "amazon web services": ["aws"],
    "google cloud platform": ["gcp"],

    "structured query language": ["sql"],
}

# ---------- NORMALIZE SKILL ----------

def normalize_skill(skill):
    """
    Convert skill shortcuts to canonical form
    Example: NLP -> natural language processing
    """

    skill = skill.lower().strip()

    for canonical, aliases in SKILL_ALIASES.items():
        if skill == canonical or skill in aliases:
            return canonical

    return skill
# ---------- EMBEDDING CACHE ----------

EMBED_CACHE = {}


def get_embedding(skill):
    """
    Get embedding vector for a skill with caching
    """

    if skill in EMBED_CACHE:
        return EMBED_CACHE[skill]

    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=skill
    ).data[0].embedding

    EMBED_CACHE[skill] = emb

    return emb
def similarity(skill1, skill2):
    """
    Compute semantic similarity between two skills
    """

    emb1 = np.array(get_embedding(skill1))
    emb2 = np.array(get_embedding(skill2))

    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

# ---------- STEP 1: EXTRACT JOB ROLE ----------

@tool
def extract_job_role(user_prompt: str) -> str:
    """
    Extract the job role from HR prompt.
    """

    prompt = f"""
Extract the job role from this prompt.

Prompt:
{user_prompt}

Return only the role name.
"""

    response = llm.invoke(prompt)

    return response.content.strip()


# ---------- STEP 2: GENERATE REQUIRED SKILLS ----------

@tool
def generate_required_skills(job_role: str) -> str:
    """
    Generate required technical skills for a job role.
    """

    prompt = f"""
List the most important technical skills required for a {job_role}.

Rules:
- Return ONLY the top 8 technical skills
- Each skill must be a single item
- Do NOT group skills inside parentheses
- Do NOT include explanations

Return JSON format:

{{
"job_role": "{job_role}",
"skills": []
}}
"""

    response = llm.invoke(prompt)
    print("\n==============================")
    print("Job Role:", job_role)
    print("LLM Generated Skills JSON:")
    print(response.content)
    print("==============================\n")
    return response.content


# ---------- STEP 3: READ HR SPREADSHEET ----------

@tool
def read_spreadsheet(file_path: str) -> str:
    """
    Read candidate spreadsheet containing
    name, email, resume_link.
    """

    import pandas as pd
    import json

    df = pd.read_csv(file_path)

    candidates = df.to_dict(orient="records")

    # Rename email to csv_email
    for c in candidates:
        c["csv_email"] = c.pop("email")

    return json.dumps(candidates)


# ---------- STEP 4: DOWNLOAD RESUME ----------
@tool
def download_resume(name: str, resume_link: str) -> str:
    """
    Download resume and save using candidate name.
    Handles Google Drive links automatically.
    """

    import os
    import re
    import requests

    os.makedirs("resumes", exist_ok=True)

    # Convert Google Drive link
    if "drive.google.com" in resume_link:

        match = re.search(r"/d/([a-zA-Z0-9_-]+)", resume_link)

        if match:
            file_id = match.group(1)
            resume_link = f"https://drive.google.com/uc?export=download&id={file_id}"

    file_path = f"resumes/{name}_resume.pdf"

    response = requests.get(resume_link, stream=True)

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return file_path


# ---------- STEP 5: EXTRACT TEXT FROM RESUME ----------

@tool
def extract_resume_text(file_path: str) -> str:
    """
    Extract text from PDF resume.
    """

    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        extracted = page.extract_text()

        if extracted:
            text += extracted

    return text


# ---------- STEP 6: EXTRACT CANDIDATE DETAILS ----------

@tool
def extract_resume_details(candidate_json: str, resume_text: str) -> str:
    """
    Extract candidate details and merge with original candidate data.
    """

    candidate = json.loads(candidate_json)

    prompt = f"""
Extract the following fields from this resume:

Name
Skills
Years of experience
Projects

Return ONLY valid JSON. Do not add explanations.

{{
"name": "",
"skills": [],
"experience": 0,
"projects": []
}}

Resume:
{resume_text}
"""

    response = llm.invoke(prompt)

    raw_output = response.content.strip()

    # remove markdown formatting if LLM adds it
    raw_output = raw_output.replace("```json", "").replace("```", "").strip()

    try:
        resume_data = json.loads(raw_output)
    except:
        return candidate_json

    # Merge resume data with original candidate
    candidate["resume_name"] = resume_data.get("name")
    candidate["skills"] = resume_data.get("skills", [])
    candidate["experience"] = resume_data.get("experience", 0)
    candidate["projects"] = resume_data.get("projects", [])

    return json.dumps(candidate)

# ---------- STEP 7: SCORE CANDIDATE ----------
@tool
def score_candidate(candidate_json: str, role_skills_json: str) -> str:
    """
    Score candidate based on skill match + semantic similarity + experience
    """

    import json
    import re

    candidate = json.loads(candidate_json)
    role_skills = json.loads(role_skills_json)

    candidate["job_role"] = role_skills.get("job_role") or "Position"

    candidate_skills = candidate.get("skills", [])
    required_skills_raw = role_skills.get("skills", [])

    # ---------- EXPAND GROUPED SKILLS ----------

    expanded_required_skills = []

    for skill in required_skills_raw:

        if "(" in skill and ")" in skill:
            inside = skill.split("(")[1].split(")")[0]
            parts = [p.strip() for p in inside.split(",")]
            expanded_required_skills.extend(parts)

        else:
            expanded_required_skills.append(skill)

    required_skills = expanded_required_skills

    # ---------- NORMALIZE ----------

    candidate_skills = [normalize_skill(s) for s in candidate_skills]
    required_skills = [normalize_skill(s) for s in required_skills]

    score = 0
    matched_skills = []

    # ---------- MATCHING ----------

    for req in required_skills:

        req_clean = re.sub(r"[^a-z0-9 ]", "", req)

        for cand in candidate_skills:

            cand_clean = re.sub(r"[^a-z0-9 ]", "", cand)

            # exact match
            if req_clean == cand_clean:
                score += 2
                matched_skills.append(cand)
                break

            # semantic match
            try:
                sim = similarity(req_clean, cand_clean)
            except Exception:
                sim = 0



            if sim > 0.75:
                score += 2
                matched_skills.append(cand)
                break

    # ---------- EXPERIENCE ----------

    experience = candidate.get("experience", 0)

    if experience >= 4:
        score += 3
    elif experience >= 2:
        score += 2
    elif experience == 1:
        score += 0.5

    candidate["matched_skills"] = matched_skills
    candidate["score"] = score

    report = f"""
############################################
        CANDIDATE SCORING REPORT
############################################
Candidate Name : {candidate["name"]}
Target Role    : {candidate["job_role"]}

Candidate Skills:
{candidate_skills}

Required Skills:
{required_skills}

Matched Skills:
{matched_skills}

Experience:
{experience}

Final Score:
{score}
############################################
"""

    print(report)

    return json.dumps(candidate)

# ---------- STEP 8: FILTER SHORTLISTED CANDIDATES ----------
@tool
def filter_candidates(candidate_json: str, threshold: int = 6) -> str:
    """
    Determine whether a candidate should be shortlisted or rejected
    based on the computed score and threshold.
    """

    import json

    candidate = json.loads(candidate_json)

    if "score" not in candidate:
        return json.dumps(candidate)

    score = candidate["score"]

    if score >= threshold:
        candidate["status"] = "shortlisted"

    else:
        candidate["status"] = "rejected"

        # send rejection email immediately
        send_interview_email.invoke(json.dumps(candidate))
        candidate["email_sent"] = True

    print(f"Candidate {candidate['name']} | Score: {score} | Status: {candidate['status']}")

    return json.dumps(candidate)


# ---------- STEP 9: SCHEDULE INTERVIEW ----------
INTERVIEW_COUNTER = 0

@tool
def schedule_interview(candidate_json: str) -> str:
    """
    Schedule interview slots dynamically.
    Each interview = 30 mins
    Buffer = 15 mins
    """

    import json
    from datetime import datetime, timedelta

    global INTERVIEW_COUNTER

    candidate = json.loads(candidate_json)

    if candidate.get("status") != "shortlisted":
        return json.dumps(candidate)

    # Interview start time
    start_time = datetime.strptime("10:00", "%H:%M")

    # Each slot increases by 45 minutes
    slot_time = start_time + timedelta(minutes=45 * INTERVIEW_COUNTER)

    interview_start = slot_time
    interview_end = slot_time + timedelta(minutes=30)

    candidate["interview_time"] = (
        interview_start.strftime("%I:%M %p")
        + " - "
        + interview_end.strftime("%I:%M %p")
    )
# generate meeting link
    meeting_id = str(uuid.uuid4())[:8]
    candidate["meeting_link"] = f"https://meet.google.com/{meeting_id}"

    print("Interview scheduled:", candidate["name"], candidate["interview_time"])
    print("Meeting link:", candidate["meeting_link"])
    # increment counter for next candidate
    INTERVIEW_COUNTER += 1

    # if not candidate.get("email_sent"):
    #     send_interview_email.invoke(json.dumps(candidate))
    # candidate["email_sent"] = True
    send_interview_email.invoke(json.dumps(candidate))
    candidate["email_sent"] = True
    print("Interview scheduled:", candidate["name"], candidate["interview_time"])
    return json.dumps(candidate)


# ---------- STEP 10: SEND EMAIL ----------
@tool
def send_interview_email(candidate_json: str) -> str:
    """
    Send an email to the candidate based on their application status.
    If shortlisted, send interview invitation.
    If rejected, send application update email.
    """

    import json
    import os
    import smtplib
    from dotenv import load_dotenv
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    load_dotenv()

    candidate = json.loads(candidate_json)

    # prevent duplicate emails
    if candidate.get("email_sent"):
        return "Email already sent."

    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")

    receiver_email = candidate.get("csv_email") or candidate.get("email")

    if not receiver_email:
        return f"No email found for candidate {candidate.get('name','Unknown')}"

    status = candidate.get("status", "rejected")
    if status == "shortlisted" and not candidate.get("interview_time"):
        return "Interview not scheduled yet."

    # ---------- SHORTLISTED EMAIL ----------
    if status == "shortlisted":

        subject = "Interview Invitation"

        body = f"""
<html>
<body>
<p>Dear {candidate['name']},</p>

<p><b>Congratulations! 🎉</b></p>

<p>You have been shortlisted for the next stage of our recruitment process.</p>

<p><b>Interview Details</b></p>

<ul>
<li><b>Role:</b> {candidate.get("job_role","Position")}</li>
<li><b>Time:</b> {candidate.get("interview_time")}</li>
<li><b>Duration:</b> 30 minutes</li>
<li><b>Meeting Link:</b> 
<a href="{candidate.get("meeting_link")}">
{candidate.get("meeting_link")}
</a>
</li>
</ul>

<p>Please be available at the scheduled time.</p>

<p>We look forward to speaking with you.</p>

<p>
Best regards,<br>
HR Team
</p>

</body>
</html>
"""

    # ---------- REJECTION EMAIL ----------
    else:

        subject = "Application Update"

        body = f"""
<html>
<body>
<p>Dear {candidate['name']},</p>

<p>Thank you for applying for the position with us.</p>

<p>After careful consideration, we regret to inform you that we will not be moving forward with your application at this time.</p>

<p>We appreciate your interest in our company and encourage you to apply again in the future.</p>

<p>
Best regards,<br>
HR Team
</p>

</body>
</html>
"""

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(sender_email, sender_password)

    print("\n----------------------------------")
    print("Candidate:", candidate.get("name"))
    print("Final Score:", candidate.get("score"))
    print("Status:", candidate.get("status"))
    print("Sending email to:", receiver_email)
    print("----------------------------------")

    server.sendmail(sender_email, receiver_email, msg.as_string())

    server.quit()

    return f"Email sent to {receiver_email} (status: {status})"