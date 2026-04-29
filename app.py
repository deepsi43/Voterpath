import streamlit as st
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.tools.ddg_search import DuckDuckGoSearchRun

# --- PAGE CONFIG ---
st.set_page_config(page_title="VoterPath Dashboard", page_icon="🗳️", layout="wide")

# --- CUSTOM CSS FOR HIGH-END UI ---
st.markdown("""
<style>
    .stApp { background-color: #f7f9fa; }
    .title-highlight { color: #1e40af; font-weight: 800; font-family: 'Inter', sans-serif; }
    .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px; transition: transform 0.2s ease-in-out; }
    .card:hover { transform: translateY(-3px); }
    .metric-value { font-size: 2.5rem; font-weight: 800; color: #1e40af; }
    .metric-title { font-size: 1.1rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;}
    .profile-card { text-align: center; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
    .profile-img { border-radius: 50%; width: 120px; height: 120px; object-fit: cover; border: 3px solid #3b82f6; margin-bottom: 15px;}
    .process-step { border-left: 4px solid #3b82f6; padding-left: 15px; margin-bottom: 20px; }
    .process-step h4 { color: #1e3a8a; margin-bottom: 5px; }
    .process-step p { color: #475569; }
</style>
""", unsafe_allow_html=True)

# --- LOAD ENV & AGENT ---
load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    load_dotenv("../.env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("Please configure your GEMINI_API_KEY in the .env file.")
    st.stop()

@tool
def tinyfish_scraper(url: str) -> str:
    """Scrapes the content of a given URL returning the text. Useful for extracting details from a politician profile page."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script_or_style in soup(['script', 'style']):
            script_or_style.extract()
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk)[:8000]
    except Exception as e:
        return f"Error scraping: {str(e)}"

@tool
def search_tool(query: str) -> str:
    """Uses a search engine to get URLs for politicians given their names and state."""
    try:
        search = DuckDuckGoSearchRun()
        return search.invoke(query)
    except Exception as e:
        return f"Error searching: {str(e)}"

@st.cache_resource
def get_agent_executor():
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)
    tools = [tinyfish_scraper, search_tool]
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are VoterPath, an Agentic AI Election Assistant. Your task is to use the 'search_tool' to find details or the official website of a given MLA/politician, and then use the 'tinyfish_scraper' to read their site and produce a detailed, well-formatted markdown profile. Include: Full Name, Constituency, Party, Key achievements, and Background."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)

agent_executor = get_agent_executor()

# --- STATE MANAGEMENT ---
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "selected_mla" not in st.session_state:
    st.session_state.selected_mla = None

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🗳️ Navigation")

def nav_button(label, page_name):
    if st.sidebar.button(label, use_container_width=True):
        st.session_state.page = page_name
        st.session_state.selected_mla = None
        st.rerun()

nav_button("📊 Election Dashboard", "Dashboard")
nav_button("🏛️ State Ministers", "Ministers")
nav_button("📍 Regional MLAs", "Regional MLAs")
if st.session_state.selected_mla:
    nav_button("👤 MLA Profile (Active)", "MLA Profile")
nav_button("💬 AI Assistant (Chat)", "Chat Assistant")

st.sidebar.markdown("---")
st.sidebar.info("VoterPath is your intelligent guide to the election process, leaders, and real-time politician profiles.")


page = st.session_state.page

if page == "Dashboard":
    st.markdown("<h1 class='title-highlight'>Election Dashboard & Process Hub</h1>", unsafe_allow_html=True)
    st.write("Welcome to the **Andhra Pradesh Election Hub**. Stay informed on the assembly details and electoral process.")
    
    st.markdown("### 🏛️ Assembly Snapshot")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("<div class='card'><div class='metric-title'>Assembly</div><div class='metric-value'>16th</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='card'><div class='metric-title'>Total Seats</div><div class='metric-value'>175</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='card'><div class='metric-title'>Current Tenure</div><div class='metric-value'>2024-29</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown("<div class='card'><div class='metric-title'>Ruling Alliance</div><div class='metric-value'>NDA</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📅 Important Dates")
    d1, d2, d3 = st.columns(3)
    d1.info("**Notification Issued:** April 18, 2024")
    d2.warning("**Polling Day:** May 13, 2024")
    d3.success("**Results Declared:** June 4, 2024")

    st.markdown("---")
    st.markdown("### ⚙️ The Election Process")
    st.markdown("""
    <div class='process-step'>
        <h4>1. Delimitation & Voter Registration</h4>
        <p>Before elections, constituencies are defined and eligible citizens must enroll in the voter list.</p>
    </div>
    <div class='process-step'>
        <h4>2. Notification & Nominations</h4>
        <p>The Election Commission issues a formal notification. Candidates then file their nomination papers.</p>
    </div>
    <div class='process-step'>
        <h4>3. Campaigning</h4>
        <p>Candidates release manifestos and campaign. Campaigning officially stops 48 hours before polling begins.</p>
    </div>
    <div class='process-step'>
        <h4>4. Polling & Counting</h4>
        <p>Voters cast secret ballots using EVMs. After polling, votes are counted under strict supervision to declare winners.</p>
    </div>
    """, unsafe_allow_html=True)

elif page == "Ministers":
    st.markdown("<h1 class='title-highlight'>State Cabinet Ministers</h1>", unsafe_allow_html=True)
    st.markdown("Core leaders currently serving in the state assembly.")
    
    ministers = [
        {"name": "N. Chandrababu Naidu", "portfolio": "Chief Minister", "img": "https://upload.wikimedia.org/wikipedia/commons/e/e0/Chandrababu_Naidu_in_2017.jpg"},
        {"name": "Pawan Kalyan", "portfolio": "Deputy Chief Minister / PR & RD", "img": "https://upload.wikimedia.org/wikipedia/commons/6/63/Pawan_Kalyan_2024.jpg"},
        {"name": "Nara Lokesh", "portfolio": "HRD, IT & Electronics", "img": "https://upload.wikimedia.org/wikipedia/commons/2/29/Nara_Lokesh_Portrait.jpg"},
        {"name": "K. Atchannaidu", "portfolio": "Agriculture & Cooperation", "img": "https://ui-avatars.com/api/?name=K+Atchannaidu&background=0D8ABC&color=fff&size=200"},
        {"name": "Anitha Vangalapudi", "portfolio": "Home Affairs & Disaster Management", "img": "https://ui-avatars.com/api/?name=Anitha+Vangalapudi&background=0D8ABC&color=fff&size=200"},
        {"name": "Payyavula Keshav", "portfolio": "Finance & Planning", "img": "https://ui-avatars.com/api/?name=Payyavula+Keshav&background=0D8ABC&color=fff&size=200"},
    ]
    
    cols = st.columns(3)
    for idx, minister in enumerate(ministers):
        with cols[idx % 3]:
            # fallback image handling
            img_src = minister["img"]
            st.markdown(f"""
            <div class='profile-card'>
                <img src='{img_src}' class='profile-img' alt='{minister["name"]}' onerror="this.src='https://ui-avatars.com/api/?name=Placeholder&background=ddd&color=555&size=200';">
                <h4>{minister["name"]}</h4>
                <p style='color: #64748b; font-weight: 500;'>{minister["portfolio"]}</p>
            </div>
            <br/>
            """, unsafe_allow_html=True)

elif page == "Regional MLAs":
    st.markdown("<h1 class='title-highlight'>Regional MLAs Directory</h1>", unsafe_allow_html=True)
    st.markdown("Select a prominent MLA to fetch their comprehensive profile live from the web using our AI Web Scrapers.")
    
    # Predefined popular MLAs for quick selection
    mlas = [
        "Nandamuri Balakrishna (Hindupur)",
        "Ganta Srinivasa Rao (Bheemili)",
        "K. Raghu Rama Krishna Raju (Undi)",
        "Y. S. Jagan Mohan Reddy (Pulivendula)",
        "Nadendla Manohar (Tenali)",
        "Kinjarapu Ram Mohan Naidu (Srikakulam)",
    ]
    
    selected_mla = st.selectbox("Choose an MLA:", ["-- Select an MLA --"] + mlas)
    
    if st.button("Generate Detailed Live Profile", type="primary"):
        if selected_mla != "-- Select an MLA --":
            st.session_state.selected_mla = selected_mla
            st.session_state.page = "MLA Profile"
            st.rerun()
        else:
            st.warning("Please select a valid MLA from the dropdown.")

elif page == "MLA Profile":
    st.markdown("<h1 class='title-highlight'>Detailed MLA Profile</h1>", unsafe_allow_html=True)
    mla_name = st.session_state.selected_mla
    
    if not mla_name:
        st.warning("No MLA selected. Please go to 'Regional MLAs' and pick one.")
        if st.button("Go to Regional MLAs"):
            st.session_state.page = "Regional MLAs"
            st.rerun()
    else:
        st.markdown(f"### Live Web Analysis for **{mla_name}**")
        st.write("Using Agentic logic to search web sources, extract URLs, and scrape live facts...")
        
        with st.spinner(f"Agent executing DuckDuckGo search & TinyFish scraping routines for {mla_name}..."):
            try:
                query = f"Provide a detailed biography and political profile of {mla_name} from Andhra Pradesh. First use the search_tool to find URLs about them, then pick the most relevant one to scrape using tinyfish_scraper to gather details."
                response = agent_executor.invoke({"input": query, "chat_history": []})
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown(response["output"])
                st.markdown("</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error fetching and scraping profile details: {e}")
                
        if st.button("← Back to Regional Directory"):
            st.session_state.page = "Regional MLAs"
            st.rerun()

elif page == "Chat Assistant":
    st.markdown("<h1 class='title-highlight'>🤖 VoterPath Agentic Assistant</h1>", unsafe_allow_html=True)
    st.write("Ask any custom questions regarding the election process or request me to find URLs & scrape info for any politician.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        if isinstance(msg, AIMessage):
            st.chat_message("assistant").write(msg.content)
        elif isinstance(msg, HumanMessage):
            st.chat_message("user").write(msg.content)

    if prompt_val := st.chat_input("Ask anything..."):
        st.session_state.messages.append(HumanMessage(content=prompt_val))
        st.chat_message("user").write(prompt_val)
        
        with st.chat_message("assistant"):
            with st.spinner("Agent computing..."):
                try:
                    response = agent_executor.invoke({
                        "input": prompt_val,
                        "chat_history": st.session_state.messages[:-1]
                    })
                    output = response["output"]
                    st.write(output)
                    st.session_state.messages.append(AIMessage(content=output))
                except Exception as e:
                    st.error(f"Error: {e}")
