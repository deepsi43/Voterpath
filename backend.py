import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    load_dotenv("../.env")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import tool, AgentExecutor, create_tool_calling_agent
from langchain_community.tools.ddg_search import DuckDuckGoSearchRun

app = FastAPI(title="VoterPath Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_profile_cache: dict = {}

# ──────────────────────────────────────────────────────────────────
# REAL-TIME WIKIPEDIA SCRAPER  (fast, no agent loop)
# ──────────────────────────────────────────────────────────────────
def scrape_wikipedia_profile(name: str) -> str:
    """Searches DuckDuckGo for the politician's Wikipedia page and scrapes it."""
    try:
        search = DuckDuckGoSearchRun()
        results = search.invoke(f"{name} Andhra Pradesh politician Wikipedia site:en.wikipedia.org")
        # Extract first Wikipedia URL from search results
        wiki_url = None
        for line in results.split():
            if "en.wikipedia.org/wiki/" in line:
                wiki_url = line.strip("().,")
                break
        if not wiki_url:
            # Fallback: direct Wikipedia URL guess
            slug = name.replace(" ", "_")
            wiki_url = f"https://en.wikipedia.org/wiki/{slug}"

        headers = {"User-Agent": "Mozilla/5.0 (compatible; VoterPath/1.0)"}
        r = requests.get(wiki_url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        # Extract infobox data
        infobox = {}
        ib = soup.find("table", {"class": "infobox"})
        if ib:
            for row in ib.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    infobox[th.get_text(strip=True)] = td.get_text(" ", strip=True)

        # Extract first 3 paragraphs
        content_div = soup.find("div", {"id": "mw-content-text"})
        paras = []
        if content_div:
            for p in content_div.find_all("p", recursive=True):
                text = p.get_text(strip=True)
                if len(text) > 80:
                    paras.append(text)
                if len(paras) >= 4:
                    break

        # Build markdown output
        md = f"## {name}\n\n"
        md += f"*Source: [Wikipedia]({wiki_url})*\n\n"
        if paras:
            md += "### Overview\n" + "\n\n".join(paras[:2]) + "\n\n"
        if infobox:
            md += "### Key Facts\n"
            for k, v in list(infobox.items())[:15]:
                if v.strip():
                    md += f"- **{k}:** {v}\n"
        if len(paras) > 2:
            md += "\n### Background\n" + "\n\n".join(paras[2:4])
        return md
    except Exception as e:
        return None  # Signal to fall back to LLM

# ──────────────────────────────────────────────────────────────────
# LLM SETUP
# ──────────────────────────────────────────────────────────────────
api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", google_api_key=api_key)

@tool
def tinyfish_scraper(url: str) -> str:
    """Scrapes a URL and returns its text content."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for tag in soup(["script", "style"]): tag.extract()
        text = soup.get_text(separator=" ")
        lines = (l.strip() for l in text.splitlines())
        chunks = (p.strip() for l in lines for p in l.split("  "))
        return "\n".join(c for c in chunks if c)[:6000]
    except Exception as e:
        return f"Error: {e}"

@tool
def search_tool(query: str) -> str:
    """Searches DuckDuckGo."""
    try:
        return DuckDuckGoSearchRun().invoke(query)
    except Exception as e:
        return f"Error: {e}"

fast_profile_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are VoterPath AI. Generate a comprehensive markdown politician profile. "
     "Sections: ## Overview, ## Party & Position, ## Constituency, ## Background, "
     "## Key Achievements, ## Electoral History (table), ## Recent Initiatives. "
     "Be factual and concise."),
    ("user", "Profile for: {name}, Andhra Pradesh politician"),
])

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are VoterPath, AP election assistant. Be concise and factual."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

chat_agent = AgentExecutor(
    agent=create_tool_calling_agent(llm, [tinyfish_scraper, search_tool], chat_prompt),
    tools=[tinyfish_scraper, search_tool], verbose=True, max_iterations=3, handle_parsing_errors=True
)

# ──────────────────────────────────────────────────────────────────
# STATIC DATA — MINISTERS (expanded to 12)
# ──────────────────────────────────────────────────────────────────
MINISTERS = [
    {"name": "N. Chandrababu Naidu",  "role": "Chief Minister",                 "party": "TDP",       "constituency": "Kuppam",
     "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Chandrababu_Naidu_in_2017.jpg/440px-Chandrababu_Naidu_in_2017.jpg"},
    {"name": "Pawan Kalyan",          "role": "Deputy Chief Minister",           "party": "Jana Sena", "constituency": "Pithapuram",
     "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/Pawan_Kalyan_-_Alliance_press_meet_%28cropped%29.jpg/440px-Pawan_Kalyan_-_Alliance_press_meet_%28cropped%29.jpg"},
    {"name": "Nara Lokesh",           "role": "Minister for IT & HRD",           "party": "TDP",       "constituency": "Mangalagiri",
     "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/Nara_Lokesh_-_2019_%28cropped%29.jpg/440px-Nara_Lokesh_-_2019_%28cropped%29.jpg"},
    {"name": "Payyavula Keshav",      "role": "Minister for Finance",            "party": "TDP",       "constituency": "Patchikala",
     "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Payyavula_keshav.jpg/440px-Payyavula_keshav.jpg"},
    {"name": "K. Atchannaidu",        "role": "Minister for Agriculture",        "party": "TDP",       "constituency": "Tekkali",
     "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Kinjarapu_Atchannaidu_2014.jpg/440px-Kinjarapu_Atchannaidu_2014.jpg"},
    {"name": "Anitha Vangalapudi",    "role": "Minister for Home Affairs",       "party": "TDP",       "constituency": "Eluru",
     "img": "https://ui-avatars.com/api/?name=Anitha+Vangalapudi&background=1e3a8a&color=c9a84c&size=400&bold=true"},
    {"name": "Nadendla Manohar",      "role": "Minister for Industries",         "party": "TDP",       "constituency": "Tenali",
     "img": "https://ui-avatars.com/api/?name=Nadendla+Manohar&background=1e3a8a&color=c9a84c&size=400&bold=true"},
    {"name": "Nimmala Ramanaidu",     "role": "Minister for Education",          "party": "TDP",       "constituency": "Narasaraopet",
     "img": "https://ui-avatars.com/api/?name=Nimmala+Ramanaidu&background=1e3a8a&color=c9a84c&size=400&bold=true"},
    {"name": "Kolusu Parthasarathy",  "role": "Minister for Municipal Admin",    "party": "TDP",       "constituency": "Narasapuram",
     "img": "https://ui-avatars.com/api/?name=Kolusu+Parthasarathy&background=1e3a8a&color=c9a84c&size=400&bold=true"},
    {"name": "Gottipati Ravi Kumar",  "role": "Minister for Water Resources",    "party": "TDP",       "constituency": "Machilipatnam",
     "img": "https://ui-avatars.com/api/?name=Gottipati+Ravi+Kumar&background=1e3a8a&color=c9a84c&size=400&bold=true"},
    {"name": "S. Savitha",            "role": "Minister for Women & Child",      "party": "TDP",       "constituency": "Rajam",
     "img": "https://ui-avatars.com/api/?name=S+Savitha&background=1e3a8a&color=c9a84c&size=400&bold=true"},
    {"name": "Mandipalli Ramprasad",  "role": "Minister for Health",             "party": "TDP",       "constituency": "Tuni",
     "img": "https://ui-avatars.com/api/?name=Mandipalli+Ramprasad&background=1e3a8a&color=c9a84c&size=400&bold=true"},
]

# ──────────────────────────────────────────────────────────────────
# STATIC DATA — MLAs (expanded with vote margins)
# ──────────────────────────────────────────────────────────────────
MLAS = {
    "Coastal Andhra": [
        {"name": "Nandamuri Balakrishna",   "constituency": "Hindupur",        "party": "TDP",    "votes": 95432, "margin": 28754},
        {"name": "Ganta Srinivasa Rao",     "constituency": "Bheemili",        "party": "TDP",    "votes": 72341, "margin": 18920},
        {"name": "Nadendla Manohar",        "constituency": "Tenali",          "party": "TDP",    "votes": 88213, "margin": 22100},
        {"name": "Vasantha Krishna Prasad", "constituency": "Gudivada",        "party": "TDP",    "votes": 68900, "margin": 15340},
        {"name": "Gottipati Ravi Kumar",    "constituency": "Machilipatnam",   "party": "TDP",    "votes": 79442, "margin": 21205},
        {"name": "Nimmala Ramanaidu",       "constituency": "Narasaraopet",    "party": "TDP",    "votes": 70123, "margin": 17800},
        {"name": "Kolusu Parthasarathy",    "constituency": "Narasapuram",     "party": "TDP",    "votes": 74500, "margin": 19300},
    ],
    "Rayalaseema": [
        {"name": "Y.S. Jagan Mohan Reddy", "constituency": "Pulivendula",     "party": "YSRCP",  "votes": 110234, "margin": 45310},
        {"name": "Anil Kumar Yadav",       "constituency": "Nandyal",          "party": "TDP",    "votes": 82100,  "margin": 23400},
        {"name": "S. V. Mohan Reddy",      "constituency": "Rajampet",         "party": "TDP",    "votes": 69800,  "margin": 14200},
        {"name": "G. Srikanth Reddy",      "constituency": "Anantapur Urban",  "party": "TDP",    "votes": 75600,  "margin": 18700},
        {"name": "Payyavula Keshav",       "constituency": "Patchikala",       "party": "TDP",    "votes": 63400,  "margin": 12900},
    ],
    "North Andhra": [
        {"name": "Kinjarapu Ram Mohan Naidu",    "constituency": "Srikakulam",    "party": "TDP",         "votes": 85200,  "margin": 24100},
        {"name": "K. Raghu Rama Krishna Raju",   "constituency": "Undi",          "party": "Independent", "votes": 58900,  "margin": 8700},
        {"name": "Giddi Eswara Rao",             "constituency": "Palakonda",     "party": "TDP",         "votes": 64300,  "margin": 16200},
        {"name": "Pulaparthi Ramanjaneyulu",     "constituency": "Araku Valley",  "party": "TDP",         "votes": 71200,  "margin": 19500},
        {"name": "K. Atchannaidu",               "constituency": "Tekkali",       "party": "TDP",         "votes": 78900,  "margin": 22300},
        {"name": "Ganta Srinivasa Rao",          "constituency": "Bheemili",      "party": "TDP",         "votes": 72341,  "margin": 18920},
    ],
    "Krishna & Guntur": [
        {"name": "Nara Lokesh",            "constituency": "Mangalagiri",      "party": "TDP",    "votes": 91200,  "margin": 30100},
        {"name": "Pawan Kalyan",           "constituency": "Pithapuram",       "party": "Jana Sena", "votes": 103400, "margin": 41200},
        {"name": "Anitha Vangalapudi",     "constituency": "Eluru",            "party": "TDP",    "votes": 76800,  "margin": 20400},
        {"name": "Nandamuri Balakrishna",  "constituency": "Hindupur",         "party": "TDP",    "votes": 95432,  "margin": 28754},
    ],
}

# ──────────────────────────────────────────────────────────────────
# ELECTION INFO
# ──────────────────────────────────────────────────────────────────
ELECTION_DATES = [
    {"event": "Election Commission Notification", "date": "April 4, 2024",  "type": "info"},
    {"event": "Last Date to File Nominations",    "date": "April 11, 2024", "type": "warning"},
    {"event": "Campaign Silence Period Begins",   "date": "May 11, 2024",   "type": "warning"},
    {"event": "Polling Day",                      "date": "May 13, 2024",   "type": "primary"},
    {"event": "Vote Counting & Results",          "date": "June 4, 2024",   "type": "success"},
    {"event": "New Government Sworn In",          "date": "June 12, 2024",  "type": "success"},
]

CONSTITUENCY_STATS = [
    {"constituency": "Kuppam",      "winner": "N. Chandrababu Naidu", "party": "TDP",      "votes": 89200,  "margin": 27400, "turnout": "82%"},
    {"constituency": "Pithapuram",  "winner": "Pawan Kalyan",         "party": "Jana Sena","votes": 103400, "margin": 41200, "turnout": "79%"},
    {"constituency": "Mangalagiri", "winner": "Nara Lokesh",          "party": "TDP",      "votes": 91200,  "margin": 30100, "turnout": "81%"},
    {"constituency": "Pulivendula", "winner": "Y.S. Jagan Mohan Reddy","party": "YSRCP",   "votes": 110234, "margin": 45310, "turnout": "84%"},
    {"constituency": "Hindupur",    "winner": "Nandamuri Balakrishna","party": "TDP",      "votes": 95432,  "margin": 28754, "turnout": "80%"},
    {"constituency": "Tekkali",     "winner": "K. Atchannaidu",       "party": "TDP",      "votes": 78900,  "margin": 22300, "turnout": "77%"},
    {"constituency": "Eluru",       "winner": "Anitha Vangalapudi",   "party": "TDP",      "votes": 76800,  "margin": 20400, "turnout": "78%"},
    {"constituency": "Patchikala",  "winner": "Payyavula Keshav",     "party": "TDP",      "votes": 63400,  "margin": 12900, "turnout": "75%"},
]

PARTY_SEATS = [
    {"party": "Telugu Desam Party (TDP)", "seats": 135, "votes_pct": "45.6%", "color": "#FF8C00"},
    {"party": "Jana Sena Party (JSP)",    "seats": 21,  "votes_pct": "21.4%", "color": "#FFD700"},
    {"party": "YSRCP",                    "seats": 11,  "votes_pct": "26.5%", "color": "#1E90FF"},
    {"party": "BJP",                      "seats": 8,   "votes_pct": "4.8%",  "color": "#FF4500"},
    {"party": "Others/Independent",       "seats": 0,   "votes_pct": "1.7%",  "color": "#6B7280"},
]

# ──────────────────────────────────────────────────────────────────
# PRE-BUILT STATIC PROFILES
# ──────────────────────────────────────────────────────────────────
STATIC_PROFILES = {
    "n. chandrababu naidu": """
## N. Chandrababu Naidu — Chief Minister, Andhra Pradesh

### Overview
N. Chandrababu Naidu is the incumbent Chief Minister of Andhra Pradesh (2024–present), serving his fourth term. He is widely regarded as one of India's most tech-savvy and development-oriented politicians, credited with transforming Hyderabad into a global IT hub.

### Party & Position
- **Party:** Telugu Desam Party (TDP) — Founder-President
- **Current Role:** Chief Minister of Andhra Pradesh
- **Alliance:** NDA (TDP + Jana Sena + BJP)

### Constituency
- **Constituency:** Kuppam, Chittoor District
- **Votes (2024):** 89,200 | **Margin:** 27,400

### Background & Education
- Born: **April 20, 1950**, Naravaripalle, Chittoor District
- Education: MA Economics, Sri Venkateswara University
- Early career as student leader; joined TDP founding team under NT Rama Rao

### Key Achievements
- Transformed Hyderabad into "HITEC City" — attracted Microsoft, Amazon, Infosys
- Earned title **"CEO of Andhra Pradesh"** for governance-as-business model
- First CM to use IT for online government services in India
- Laid foundation for Amaravati greenfield capital city

### Electoral History
| Year | Constituency | Result |
|------|-------------|--------|
| 1978 | Chandragiri | Won |
| 1983 | Chandragiri | Won |
| 1989–2019 | Kuppam | Won (every election) |
| 2024 | Kuppam | Won ✅ (Margin: 27,400) |

### Recent Initiatives (2024–)
- **Amaravati Revival** — Rs 15,000 Cr capital city allocation
- **Swarna Andhra Pradesh Vision 2047**
- Super Six welfare schemes: Anna Canteen, housing, etc.
- AP Gig Workers Act for platform worker rights
""",
    "pawan kalyan": """
## Pawan Kalyan — Deputy Chief Minister, Andhra Pradesh

### Overview
Pawan Kalyan is the Deputy Chief Minister of Andhra Pradesh and President of Jana Sena Party. A superstar actor-turned-politician, he is one of the most charismatic figures in Telugu politics.

### Party & Position
- **Party:** Jana Sena Party (JSP) — Founder & President
- **Alliance:** NDA (TDP + Jana Sena + BJP)
- **Portfolios:** Panchayati Raj, Rural Development, Environment

### Constituency
- **Constituency:** Pithapuram, East Godavari
- **Votes (2024):** 1,03,400 | **Margin:** 41,200 (one of the largest in AP 2024)

### Background
- **Born:** September 2, 1971 | Younger brother of megastar Chiranjeevi
- Started as stuntman; became top Telugu film hero before entering politics
- Founded Jana Sena Party in **March 2014**

### Key Achievements
- Won Pithapuram with a landslide in first-ever personal victory (2024)
- Championed causes of farmers, fishermen, and unorganised sector workers
- Jana Sena's 21-seat performance was critical to NDA's 164-seat majority
- Established AP Village and Ward Secretariat model as Deputy CM

### Electoral History
| Year | Constituency | Result |
|------|-------------|--------|
| 2019 | Bhimavaram | Lost |
| 2019 | Gajuwaka | Lost |
| 2024 | Pithapuram | **Won** ✅ (Margin: 41,200) |

### Recent Initiatives (2024–)
- Welfare programs for rural and coastal communities
- AP Marine Fishermen housing scheme
- Grassroots gram sabha empowerment initiative
""",
    "nara lokesh": """
## Nara Lokesh — Minister for IT, HRD & Electronics

### Overview
Nara Lokesh is the son of CM N. Chandrababu Naidu and one of the youngest Cabinet Ministers in AP. He is the face of next-generation leadership in TDP and holds critical portfolios of IT, Education, and Electronics.

### Party & Position
- **Party:** Telugu Desam Party (TDP)
- **Portfolios:** Human Resources Development, IT & Electronics
- **Relation:** Son of CM N. Chandrababu Naidu

### Constituency
- **Constituency:** Mangalagiri, Guntur District
- **Votes (2024):** 91,200 | **Margin:** 30,100

### Background & Education
- **Born:** February 25, 1983
- **Education:** MBA — Stanford Graduate School of Business, USA
- Gold medalist; specialised in tech policy and development economics

### Key Achievements
- Completed historic **4,000 km Padayatra** across AP (2022–24) highlighting YSRCP governance failures
- As TDP advisor (2014–19): attracted Google, Microsoft, Amazon to Hyderabad
- Drove AP Fiber Grid (one of Asia's largest rural broadband programs)
- Created AP Skill Development Corporation

### Electoral History
| Year | Constituency | Result |
|------|-------------|--------|
| 2019 | Mangalagiri | Lost |
| 2024 | Mangalagiri | **Won** ✅ (Margin: 30,100) |

### Recent Initiatives (2024–)
- AP AI Mission and Data Centre Policy
- MoU with 50+ global tech companies for AP investments
- Restructuring government school curriculum with NCERT + digital tools
""",
    "payyavula keshav": """
## Payyavula Keshav — Minister for Finance & Planning

### Overview
Payyavula Keshav is the Finance Minister of Andhra Pradesh and one of the most trusted economic managers in TDP. A Chartered Accountant by profession, he managed AP's difficult finances post-bifurcation.

### Party & Position
- **Party:** Telugu Desam Party (TDP) — State Treasurer
- **Portfolio:** Finance, Planning, and Legislative Affairs

### Constituency
- **Constituency:** Patchikala, Chittoor District
- **Votes (2024):** 63,400 | **Margin:** 12,900

### Background & Education
- Qualified Chartered Accountant (CA)
- Long-standing TDP economic advisor
- Expert in public finance and revenue policy

### Key Achievements
- Served as Finance Minister 2014–2019; managed AP's revenue recovery post-Hyderabad loss
- Presented 5 consecutive state budgets under the most fiscally constrained conditions in AP's history
- Implemented AP FRBM (Fiscal Responsibility) Act
- Secured central devolution and special category status negotiations

### Electoral History
| Year | Result |
|------|--------|
| 2014 | Won |
| 2019 | Lost |
| 2024 | **Won** ✅ |

### Recent Initiatives (2024–)
- AP Fiscal Consolidation Roadmap 2024–29
- Revenue mobilisation from property registration reforms
- Green infrastructure bonds for Amaravati
""",
    "k. atchannaidu": """
## K. Atchannaidu — Minister for Agriculture & Cooperation

### Overview
Kinjarapu Atchannaidu is a senior TDP leader from North Andhra and Cabinet Minister for Agriculture, Cooperation, and related portfolios. He is a strong farmer advocate and key party organiser in Srikakulam.

### Party & Position
- **Party:** Telugu Desam Party (TDP)
- **Portfolio:** Agriculture, Cooperation, Marketing

### Constituency
- **Constituency:** Tekkali, Srikakulam District
- **Votes (2024):** 78,900 | **Margin:** 22,300

### Key Achievements
- Labour Minister 2014–2019 — implemented minimum wage revisions
- Built mass farmer support base in North Andhra
- Instrumental in TDP's 2024 North Andhra sweep (region returned 20+ TDP seats)

### Recent Initiatives (2024–)
- Rytu Bharosa (farmer support) at Rs 20,000/acre
- Zero-interest crop loans for small farmers
- Cold chain infrastructure for North Andhra fisheries
""",
    "anitha vangalapudi": """
## Anitha Vangalapudi — Minister for Home Affairs

### Overview
Anitha Vangalapudi is one of the few women Cabinet Ministers in AP, handling the important Home Affairs and Disaster Management portfolio. She represents Eluru constituency in West Godavari.

### Party & Position
- **Party:** Telugu Desam Party (TDP)
- **Portfolio:** Home Affairs, Disaster Management

### Constituency
- **Constituency:** Eluru, West Godavari District
- **Votes (2024):** 76,800 | **Margin:** 20,400

### Key Achievements
- Strong women's rights record as TDP women's wing leader
- Leads AP's disaster preparedness for cyclone-prone coastal regions
- Spearheaded AP Police modernization proposal (2024)

### Recent Initiatives (2024–)
- Women's safety SHE Teams expansion
- AP Police body-cam modernization
- Cyclone-preparedness shelters in Godavari delta
""",
    "y.s. jagan mohan reddy": """
## Y.S. Jagan Mohan Reddy — Leader of Opposition

### Overview
Y.S. Jagan Mohan Reddy is the incumbent President of YSRCP (Yuvajana Sramika Rythu Congress Party) and Leader of Opposition in the AP Legislative Assembly. He served as Chief Minister of Andhra Pradesh from 2019–2024.

### Party & Position
- **Party:** YSRCP — President & Founder
- **Current Role:** Leader of Opposition, AP Legislative Assembly

### Constituency
- **Constituency:** Pulivendula, Kadapa District (family stronghold)
- **Votes (2024):** 1,10,234 | **Margin:** 45,310

### Background & Education
- **Born:** December 21, 1972 | Son of late CM Y.S. Rajasekhar Reddy
- Education: B.Com, Loyola Academy, Hyderabad

### Key Achievements (as CM 2019–24)
- **Amma Vodi** — Rs 15,000/year for every mother sending children to school
- **YSR Rythu Bharosa** — Rs 13,500/year per farmer household
- **Jagananna Chedodu** — financial support to BC communities
- Decentralised 3-capital concept (Amaravati, Kurnool, Visakhapatnam)

### Electoral History
| Year | Constituency | Result |
|------|-------------|--------|
| 2009 | Kadapa | Won |
| 2014 | Kadapa | Won (CM candidate) |
| 2019 | Pulivendula | Won (became CM with 151 seats) |
| 2024 | Pulivendula | Won (but YSRCP won only 11 seats overall) |
""",
    "nandamuri balakrishna": """
## Nandamuri Balakrishna — MLA, Hindupur

### Overview
Nandamuri Balakrishna (Balayya) is a legendary Telugu film star and TDP MLA from Hindupur. Son of Telugu film legend and TDP founder NT Rama Rao, he is one of the most popular public figures in Andhra Pradesh.

### Party & Position
- **Party:** Telugu Desam Party (TDP)
- **Constituency:** Hindupur, Anantapur District

### Votes & Margin (2024)
- **Votes:** 95,432 | **Margin:** 28,754 | **Turnout:** 80%

### Background
- **Born:** June 10, 1960 | Son of NT Rama Rao (Founder, TDP & former CM)
- Telugu superstar with 100+ films; known for high-action roles

### Political Career
- First contested in 1994, won Hindupur
- Won from Hindupur in 2014, 2019, and 2024
- Known for constituency development work and grassroots connections

### Recent Work
- Hindupur infrastructure development fund
- Local employment boost via film industry collaborations
""",
}
# Add lookup by first unique name tokens
def find_static_profile(name: str):
    key = name.strip().lower()
    # Direct key match
    for sk, sv in STATIC_PROFILES.items():
        if sk in key:
            return sv
    # Partial word match (first 2 meaningful words)
    words = [w for w in key.split() if len(w) > 2]
    for sk, sv in STATIC_PROFILES.items():
        sk_words = [w for w in sk.split() if len(w) > 2]
        matches = sum(1 for w in words if any(w in sw or sw in w for sw in sk_words))
        if matches >= 2:
            return sv
    return None

# ──────────────────────────────────────────────────────────────────
# API ROUTES
# ──────────────────────────────────────────────────────────────────
@app.get("/api/ministers")
def get_ministers():
    return {"ministers": MINISTERS}

@app.get("/api/mlas")
def get_mlas():
    return {"mlas": MLAS}

@app.get("/api/election-dates")
def get_election_dates():
    return {"dates": ELECTION_DATES}

@app.get("/api/constituency-stats")
def get_constituency_stats():
    return {"stats": CONSTITUENCY_STATS, "party_seats": PARTY_SEATS}

class ProfileRequest(BaseModel):
    name: str

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@app.post("/api/profile")
def get_profile(req: ProfileRequest):
    cache_key = req.name.strip().lower()

    # 1. Instant static profile
    static = find_static_profile(req.name)
    if static:
        return {"profile": static, "source": "static"}

    # 2. In-memory cache
    if cache_key in _profile_cache:
        return {"profile": _profile_cache[cache_key], "source": "cache"}

    # 3. Real-time Wikipedia scrape (fast, no agent loop)
    wiki_result = scrape_wikipedia_profile(req.name)
    if wiki_result:
        _profile_cache[cache_key] = wiki_result
        return {"profile": wiki_result, "source": "wikipedia"}

    # 4. LLM fallback with retry on rate limit
    for attempt in range(2):
        try:
            chain = fast_profile_prompt | llm
            result = chain.invoke({"name": req.name})
            text = result.content if hasattr(result, "content") else str(result)
            _profile_cache[cache_key] = text
            return {"profile": text, "source": "llm"}
        except Exception as e:
            if "429" in str(e) and attempt == 0:
                time.sleep(4)
                continue
            return {"profile": f"## {req.name}\n\nProfile unavailable at this moment. Please try again.\n\n_{str(e)}_"}

@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        history = []
        for h in req.history:
            if h["role"] == "user":
                history.append(HumanMessage(content=h["content"]))
            else:
                history.append(AIMessage(content=h["content"]))
        result = chat_agent.invoke({"input": req.message, "chat_history": history})
        return {"reply": result["output"]}
    except Exception as e:
        if "429" in str(e):
            return {"reply": "⚠️ Rate limit hit. Please wait 30 seconds and retry."}
        return {"reply": f"Error: {str(e)}"}

app.mount("/", StaticFiles(directory=".", html=True), name="static")
