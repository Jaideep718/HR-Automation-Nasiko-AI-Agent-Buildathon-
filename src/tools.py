
"""
Tools for the HR Resume Screening Agent.
"""

import json
import random
import requests
import pandas as pd

from pypdf import PdfReader
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


# ---------- LLM INITIALIZATION ----------

llm = ChatOpenAI(model="gpt-4o", temperature=0)


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
List the important technical skills required for a {job_role}.

Return JSON format:

{{
"job_role": "{job_role}",
 "skills": []
}}
"""

    response = llm.invoke(prompt)

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
    Score candidate based on skill similarity and experience.
    Works for any role.
    """

    import json
    import re

    candidate = json.loads(candidate_json)
    role_skills = json.loads(role_skills_json)
    candidate["job_role"] = role_skills.get("job_role") or "Position"

    candidate_skills = candidate.get("skills", [])
    required_skills = role_skills.get("skills", [])

    candidate_skills = [s.lower() for s in candidate_skills]
    required_skills = [s.lower() for s in required_skills]

    score = 0
    matched_skills = []

    # Skill matching
    for req in required_skills:

        req_clean = re.sub(r"[^a-z0-9 ]", "", req)

        for cand in candidate_skills:

            cand_clean = re.sub(r"[^a-z0-9 ]", "", cand)

            if req_clean in cand_clean or cand_clean in req_clean:

                score += 2
                matched_skills.append(cand)
                break

    # Experience scoring
    experience = candidate.get("experience", 0)

    if experience >= 4:
        score += 3
    elif experience >= 2:
        score += 2
    elif experience == 1:
        score += 0.5

    candidate["matched_skills"] = matched_skills
    candidate["score"] = score
    print("Candidate score:", candidate["score"], candidate["name"])
    return json.dumps(candidate)


# ---------- STEP 8: FILTER SHORTLISTED CANDIDATES ----------
@tool
def filter_candidates(candidate_json: str, threshold: int = 6) -> str:
        """
        Determine whether a candidate should be shortlisted or rejected
        based on the computed score and threshold.
        """
        candidate = json.loads(candidate_json)

        if "score" not in candidate:
            return json.dumps(candidate)

        score = candidate["score"]

        if score >= threshold:
            candidate["status"] = "shortlisted"
        else:
            candidate["status"] = "rejected"

        if not candidate.get("email_sent"):
            send_interview_email(json.dumps(candidate))
            candidate["email_sent"] = True

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

    # increment counter for next candidate
    INTERVIEW_COUNTER += 1

    if not candidate.get("email_sent"):
        send_interview_email(json.dumps(candidate))
    candidate["email_sent"] = True

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

    # ---------- SHORTLISTED EMAIL ----------
    if status == "shortlisted":

        subject = "Interview Invitation"

        body = f"""
Dear {candidate['name']},

Congratulations! 🎉

You have been shortlisted for the next stage of our recruitment process.

Interview Details
-----------------
Role: {candidate.get("job_role","Position")}
Time: {candidate.get("interview_time")}
Duration: 30 minutes

Please be available at the scheduled time.

We look forward to speaking with you.

Best regards,
HR Team
"""

    # ---------- REJECTION EMAIL ----------
    else:

        subject = "Application Update"

        body = f"""
Dear {candidate['name']},

Thank you for taking the time to apply for the position with us.

After careful consideration, we regret to inform you that we will not be moving forward with your application at this time.

We truly appreciate your interest in our company and encourage you to apply again in the future if a suitable opportunity arises.

We wish you all the best in your career journey.

Kind regards,
HR Team
"""

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(sender_email, sender_password)

    print("Sending email to:", receiver_email)

    server.sendmail(sender_email, receiver_email, msg.as_string())

    server.quit()

    return f"Email sent to {receiver_email} (status: {status})"