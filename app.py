import streamlit as st
import pdfplumber
import re
from datetime import datetime

st.set_page_config(page_title="Smart Resume Analyzer", page_icon="📝")

# ----------------- Helpers -----------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{8,}\d)")

SECTION_HINTS = {
    "education": ["education", "academics", "qualifications", "coursework", "bsc", "msc", "university", "cgpa", "percentage"],
    "skills": ["skills", "technical skills", "tech stack", "tools", "technologies"],
    "projects": ["projects", "project experience", "academic projects", "personal projects"],
    "experience": ["experience", "work experience", "internship", "internships", "employment"],
    "summary": ["summary", "objective", "profile"],
}

ROLE_KEYWORDS = {
    "Data Analyst (Entry)": {
        "must": ["excel", "sql", "python", "pandas", "data analysis", "visualization", "statistics"],
        "nice": ["power bi", "tableau", "numpy", "matplotlib", "seaborn", "etl"],
    },
    "Frontend Developer (Entry)": {
        "must": ["html", "css", "javascript", "responsive", "git"],
        "nice": ["react", "typescript", "tailwind", "webpack", "rest api"],
    },
    "Cybersecurity Intern": {
        "must": ["linux", "networking", "owasp", "vulnerability", "threat", "nmap"],
        "nice": ["wireshark", "burp", "splunk", "siem", "mitre att&ck"],
    },
    "ML Engineer (Fresher)": {
        "must": ["python", "numpy", "pandas", "scikit-learn", "machine learning", "regression", "classification"],
        "nice": ["tensorflow", "pytorch", "feature engineering", "cross-validation"],
    },
}

def extract_text_from_pdf(file) -> str:
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text += "\n" + t
    return text

def has_any(text: str, keywords: list) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)

def count_found(text: str, keywords: list) -> int:
    t = text.lower()
    return sum(1 for k in keywords if k in t)

def detect_contact(text: str):
    emails = EMAIL_RE.findall(text)
    phones = PHONE_RE.findall(text)
    return list(set(emails)), list(set(p.strip() for p in phones))

def bullet_style_present(text: str) -> bool:
    # quick signal for bullet points or lists
    return any(s in text for s in ["•", "-", "–", "●", "* "])

# ----------------- UI -----------------
st.title("📝 Smart Resume Analyzer")
st.caption("Upload a PDF resume. Get a score, job match, missing keywords, and suggestions.")

resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

role = st.selectbox(
    "Target role (for keyword match)",
    list(ROLE_KEYWORDS.keys()) + ["Custom role (enter keywords below)"],
)

custom_must = st.text_input("Custom role: required keywords (comma-separated)", placeholder="e.g., python, sql, pandas")
custom_nice = st.text_input("Custom role: nice-to-have keywords (comma-separated)", placeholder="e.g., power bi, tableau")

if resume_file:
    text = extract_text_from_pdf(resume_file)

    st.subheader("Extracted Text (preview)")
    st.text_area("Resume Content", text, height=200)

    # ----------------- Checks -----------------
    emails, phones = detect_contact(text)
    has_email = len(emails) > 0
    has_phone = len(phones) > 0

    sections_found = {
        name: has_any(text, hints) for name, hints in SECTION_HINTS.items()
    }

    # Choose keywords
    if role == "Custom role (enter keywords below)":
        must_list = [w.strip().lower() for w in custom_must.split(",") if w.strip()]
        nice_list = [w.strip().lower() for w in custom_nice.split(",") if w.strip()]
    else:
        must_list = ROLE_KEYWORDS[role]["must"]
        nice_list = ROLE_KEYWORDS[role]["nice"]

    # Keyword coverage
    must_found = count_found(text, must_list) if must_list else 0
    nice_found = count_found(text, nice_list) if nice_list else 0

    # Formatting hint
    has_bullets = bullet_style_present(text)

    # ----------------- Scoring (out of 100) -----------------
    score = 0
    breakdown = {}

    # Contact info (10)
    s_contact = 0
    s_contact += 5 if has_email else 0
    s_contact += 5 if has_phone else 0
    breakdown["Contact info"] = s_contact
    score += s_contact

    # Sections (40 -> 10 each for: Summary, Education, Skills, Projects; Experience optional bonus)
    s_sections = 0
    for key in ["summary", "education", "skills", "projects"]:
        s_sections += 10 if sections_found[key] else 0
    # small bonus if experience is present
    s_sections += 5 if sections_found["experience"] else 0
    breakdown["Core sections"] = s_sections
    score += s_sections

    # Keywords vs target role (40 -> 30 must, 10 nice)
    must_score = 0
    nice_score = 0
    if must_list:
        must_score = round(30 * (must_found / len(must_list)))
    if nice_list:
        nice_score = round(10 * (nice_found / len(nice_list)))
    breakdown["Role keywords (must)"] = must_score
    breakdown["Role keywords (nice)"] = nice_score
    score += must_score + nice_score

    # Formatting signal (10)
    s_format = 10 if has_bullets else 5  # at least 5, better 10 if bullets exist
    breakdown["Formatting"] = s_format
    score += s_format

    score = min(score, 100)

    # ----------------- Suggestions -----------------
    suggestions = []

    if not has_email: suggestions.append("Add a professional email address.")
    if not has_phone: suggestions.append("Add a reachable phone number.")

    for k, present in sections_found.items():
        if not present and k in ["summary", "education", "skills", "projects"]:
            suggestions.append(f"Add a clear **{k.capitalize()}** section.")

    if must_list and must_found < len(must_list):
        missing_must = [k for k in must_list if k.lower() not in text.lower()]
        suggestions.append("Add or highlight these MUST keywords: " + ", ".join(missing_must[:10]))

    if nice_list and nice_found < len(nice_list):
        missing_nice = [k for k in nice_list if k.lower() not in text.lower()]
        suggestions.append("Consider adding these NICE-TO-HAVE keywords: " + ", ".join(missing_nice[:10]))

    if not has_bullets:
        suggestions.append("Use bullet points for achievements and responsibilities.")

    # Encourage measurable results
    if "project" in SECTION_HINTS and sections_found["projects"]:
        # quick heuristic: check for numbers or % for achievements
        if not re.search(r"\b\d+%?\b", text):
            suggestions.append("Add numbers (metrics, %, counts, time saved) to your project/experience bullets.")

    # ----------------- Display -----------------
    st.subheader("Overall Score")
    st.metric("Score (0–100)", value=score)

    st.subheader("Breakdown")
    for k, v in breakdown.items():
        st.write(f"- {k}: **{v}**")

    st.subheader("Job Match")
    st.write("**Role:**", role)
    if must_list:
        st.write(f"Must-have covered: {must_found}/{len(must_list)}")
    if nice_list:
        st.write(f"Nice-to-have covered: {nice_found}/{len(nice_list)}")

    st.subheader("Suggestions")
    if suggestions:
        for s in suggestions:
            st.write("• " + s)
    else:
        st.write("Looks good. Minor polishing only.")

    # ----------------- Downloadable feedback report -----------------
    report_lines = []
    report_lines.append("Smart Resume Analyzer – Feedback Report")
    report_lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("")
    report_lines.append(f"Overall Score: {score}/100")
    report_lines.append("")
    report_lines.append("Breakdown:")
    for k, v in breakdown.items():
        report_lines.append(f"- {k}: {v}")
    report_lines.append("")
    report_lines.append(f"Target Role: {role}")
    if must_list:
        report_lines.append(f"Must-have keywords matched: {must_found}/{len(must_list)}")
        missing_must = [k for k in must_list if k.lower() not in text.lower()]
        if missing_must:
            report_lines.append("Missing MUST keywords: " + ", ".join(missing_must))
    if nice_list:
        report_lines.append(f"Nice-to-have keywords matched: {nice_found}/{len(nice_list)}")
        missing_nice = [k for k in nice_list if k.lower() not in text.lower()]
        if missing_nice:
            report_lines.append("Missing NICE keywords: " + ", ".join(missing_nice))
    report_lines.append("")
    if suggestions:
        report_lines.append("Suggestions:")
        for s in suggestions:
            report_lines.append("- " + s)

    report_text = "\n".join(report_lines)
    st.download_button("Download Feedback (.txt)", data=report_text, file_name="resume_feedback.txt")
