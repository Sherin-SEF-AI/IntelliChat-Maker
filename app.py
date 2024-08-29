import streamlit as st
import google.generativeai as genai
import sqlite3
import hashlib
from datetime import datetime
import json
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import base64

# Set up Gemini API
GOOGLE_API_KEY = ""
genai.configure(api_key=GOOGLE_API_KEY)

# Database setup
conn = sqlite3.connect('intellichat_maker.db')
c = conn.cursor()

def create_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, email TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS chatbots
                 (id INTEGER PRIMARY KEY, name TEXT, description TEXT, 
                  industry TEXT, personality TEXT, created_at TEXT, user_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY, chatbot_id INTEGER, user_message TEXT, 
                  bot_response TEXT, timestamp TEXT, sentiment TEXT,
                  FOREIGN KEY(chatbot_id) REFERENCES chatbots(id))''')

    conn.commit()

create_tables()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, hashed):
    return hash_password(password) == hashed

def register_user(username, password, email):
    hashed_password = hash_password(password)
    try:
        c.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, hashed_password, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_user(username):
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    return c.fetchone()

def create_chatbot(name, description, industry, personality, user_id):
    c.execute("""INSERT INTO chatbots (name, description, industry, personality, created_at, user_id)
                 VALUES (?, ?, ?, ?, ?, ?)""", 
              (name, description, industry, personality, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()

def get_user_chatbots(user_id):
    c.execute("SELECT * FROM chatbots WHERE user_id = ?", (user_id,))
    return c.fetchall()

def delete_chatbot(chatbot_id):
    c.execute("DELETE FROM chatbots WHERE id = ?", (chatbot_id,))
    c.execute("DELETE FROM conversations WHERE chatbot_id = ?", (chatbot_id,))
    conn.commit()

def add_conversation(chatbot_id, user_message, bot_response, sentiment):
    c.execute("""INSERT INTO conversations (chatbot_id, user_message, bot_response, timestamp, sentiment)
                 VALUES (?, ?, ?, ?, ?)""", 
              (chatbot_id, user_message, bot_response, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sentiment))
    conn.commit()

def get_conversations(chatbot_id):
    c.execute("SELECT user_message, bot_response, timestamp, sentiment FROM conversations WHERE chatbot_id = ? ORDER BY timestamp", (chatbot_id,))
    return c.fetchall()

def get_chatbot(chatbot_id):
    c.execute("SELECT * FROM chatbots WHERE id = ?", (chatbot_id,))
    return c.fetchone()

def get_chatbot_stats(chatbot_id):
    c.execute("SELECT COUNT(*) FROM conversations WHERE chatbot_id = ?", (chatbot_id,))
    total_messages = c.fetchone()[0]
    c.execute("SELECT AVG(LENGTH(user_message)) FROM conversations WHERE chatbot_id = ?", (chatbot_id,))
    avg_user_message_length = c.fetchone()[0] or 0
    c.execute("SELECT AVG(LENGTH(bot_response)) FROM conversations WHERE chatbot_id = ?", (chatbot_id,))
    avg_bot_response_length = c.fetchone()[0] or 0
    return total_messages, avg_user_message_length, avg_bot_response_length

# Gemini API functions
def generate_response(prompt, chatbot_info):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(
        f"You are a chatbot with the following characteristics:\n"
        f"Description: {chatbot_info[2]}\n"
        f"Industry: {chatbot_info[3]}\n"
        f"Personality: {chatbot_info[4]}\n"
        f"Please respond to the following message in character: {prompt}"
    )
    return response.text

def analyze_sentiment(text):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(
        f"Analyze the sentiment of the following text and respond with either 'Positive', 'Negative', or 'Neutral': {text}"
    )
    return response.text.strip()

def generate_image_prompt(description):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(
        f"Generate a detailed image prompt for a text-to-image AI based on this description: {description}"
    )
    return response.text

def summarize_conversation(conversation):
    model = genai.GenerativeModel('gemini-pro')
    conversation_text = "\n".join([f"User: {msg}\nBot: {resp}" for msg, resp, _, _ in conversation])
    response = model.generate_content(
        f"Summarize the following conversation in 3-5 sentences:\n\n{conversation_text}"
    )
    return response.text

def generate_chatbot_persona(industry, personality_traits):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(
        f"Generate a chatbot persona for the {industry} industry with the following personality traits: {personality_traits}. "
        "Include a name, brief description, and 3 example dialogue responses."
    )
    return response.text

# Streamlit UI
def main():
    st.set_page_config(page_title="IntelliChat Maker", layout="wide")
    st.title("IntelliChat Maker")

    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

    if 'current_chatbot' not in st.session_state:
        st.session_state.current_chatbot = None

    if st.session_state.user_id is None:
        show_login_register()
    else:
        show_main_interface()

def show_login_register():
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.header("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            user = get_user(username)
            if user and check_password(password, user[2]):
                st.session_state.user_id = user[0]
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.header("Register")
        new_username = st.text_input("Username", key="register_username")
        new_password = st.text_input("Password", type="password", key="register_password")
        new_email = st.text_input("Email", key="register_email")
        if st.button("Register"):
            if register_user(new_username, new_password, new_email):
                st.success("Registration successful! Please login.")
            else:
                st.error("Username or email already exists")

def show_main_interface():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Create Chatbot", "My Chatbots", "Chat Interface", "AI Tools", "Analytics"])

    if page == "Create Chatbot":
        show_create_chatbot()
    elif page == "My Chatbots":
        show_my_chatbots()
    elif page == "Chat Interface":
        show_chat_interface()
    elif page == "AI Tools":
        show_ai_tools()
    elif page == "Analytics":
        show_analytics()

    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.session_state.current_chatbot = None
        st.rerun()

def show_create_chatbot():
    st.header("Create a New Chatbot")
    name = st.text_input("Chatbot Name")
    description = st.text_area("Description")
    industry = st.selectbox("Industry", ["Technology", "Healthcare", "Finance", "Education", "Entertainment", "Other"])
    personality_traits = st.text_area("Personality Traits (comma-separated)")
    
    if st.button("Generate Chatbot Persona"):
        persona = generate_chatbot_persona(industry, personality_traits)
        st.write("Generated Persona:")
        st.write(persona)
    
    if st.button("Create Chatbot"):
        if name and description and industry and personality_traits:
            create_chatbot(name, description, industry, personality_traits, st.session_state.user_id)
            st.success(f"Chatbot '{name}' created successfully!")
        else:
            st.error("Please fill in all fields")

def show_my_chatbots():
    st.header("My Chatbots")
    chatbots = get_user_chatbots(st.session_state.user_id)
    
    if not chatbots:
        st.warning("You haven't created any chatbots yet. Go to 'Create Chatbot' to get started!")
        return

    for chatbot in chatbots:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.subheader(chatbot[1])
            st.write(f"Description: {chatbot[2]}")
            st.write(f"Industry: {chatbot[3]}")
        with col2:
            if st.button("Chat", key=f"chat_{chatbot[0]}"):
                st.session_state.current_chatbot = chatbot[0]
                st.rerun()
        with col3:
            if st.button("Export", key=f"export_{chatbot[0]}"):
                export_data = {
                    "name": chatbot[1],
                    "description": chatbot[2],
                    "industry": chatbot[3],
                    "personality": chatbot[4],
                    "created_at": chatbot[5]
                }
                st.download_button(
                    label="Download Chatbot Config",
                    data=json.dumps(export_data, indent=2),
                    file_name=f"{chatbot[1]}_config.json",
                    mime="application/json"
                )
        with col4:
            if st.button("Delete", key=f"delete_{chatbot[0]}"):
                delete_chatbot(chatbot[0])
                st.rerun()
        st.divider()

def show_chat_interface():
    st.header("Chat Interface")
    
    chatbots = get_user_chatbots(st.session_state.user_id)
    if not chatbots:
        st.warning("You haven't created any chatbots yet. Go to 'Create Chatbot' to get started!")
        return

    chatbot_names = [chatbot[1] for chatbot in chatbots]
    selected_chatbot = st.selectbox("Select a chatbot", chatbot_names)
    
    for chatbot in chatbots:
        if chatbot[1] == selected_chatbot:
            st.session_state.current_chatbot = chatbot[0]
            break
    
    if st.session_state.current_chatbot is None:
        st.warning("Please select a chatbot to start chatting.")
        return

    chatbot = get_chatbot(st.session_state.current_chatbot)
    st.subheader(f"Chatting with {chatbot[1]}")

    # Display chat history
    chat_history = get_conversations(st.session_state.current_chatbot)
    for user_msg, bot_msg, timestamp, sentiment in chat_history:
        with st.chat_message("user"):
            st.write(user_msg)
            st.caption(f"Sent at: {timestamp}")
        with st.chat_message("assistant"):
            st.write(bot_msg)
            st.caption(f"Received at: {timestamp}")

    # User input
    user_input = st.chat_input("Type your message here...")
    if user_input:
        with st.chat_message("user"):
            st.write(user_input)

        # Generate and display chatbot response
        response = generate_response(user_input, chatbot)
        with st.chat_message("assistant"):
            st.write(response)

        # Analyze sentiment
        sentiment = analyze_sentiment(user_input)

        # Save conversation
        add_conversation(st.session_state.current_chatbot, user_input, response, sentiment)
        st.rerun()

    if st.button("Summarize Conversation"):
        summary = summarize_conversation(chat_history)
        st.info(f"Conversation Summary:\n\n{summary}")

def show_ai_tools():
    st.header("AI Tools")
    
    tool = st.selectbox("Select AI Tool", ["Sentiment Analysis", "Image Prompt Generator", "Text Summarizer"])
    
    if tool == "Sentiment Analysis":
        text = st.text_area("Enter text for sentiment analysis")
        if st.button("Analyze Sentiment"):
            sentiment = analyze_sentiment(text)
            st.write(f"Sentiment: {sentiment}")
    
    elif tool == "Image Prompt Generator":
        description = st.text_area("Enter a description for the image")
        if st.button("Generate Image Prompt"):
            prompt = generate_image_prompt(description)
            st.write("Generated Image Prompt:")
            st.write(prompt)
    
    elif tool == "Text Summarizer":
        text = st.text_area("Enter text to summarize")
        if st.button("Summarize Text"):
            summary = summarize_conversation([(text, "", "", "")])
            st.write("Summary:")
            st.write(summary)

def show_analytics():
    st.header("Chatbot Analytics")
    
    chatbots = get_user_chatbots(st.session_state.user_id)
    if not chatbots:
        st.warning("You haven't created any chatbots yet. Go to 'Create Chatbot' to get started!")
        return

    chatbot_names = [chatbot[1] for chatbot in chatbots]
    selected_chatbot = st.selectbox("Select a chatbot for analytics", chatbot_names)
    
    chatbot_id = None
    for chatbot in chatbots:
        if chatbot[1] == selected_chatbot:
            chatbot_id = chatbot[0]
            break
    
    if chatbot_id is None:
        st.warning("Please select a chatbot to view analytics.")
        return

    total_messages, avg_user_message_length, avg_bot_response_length = get_chatbot_stats(chatbot_id)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Messages", total_messages)
    col2.metric("Avg User Message Length", f"{avg_user_message_length:.2f}")
    col3.metric("Avg Bot Response Length", f"{avg_bot_response_length:.2f}")
    
    # Create a bar chart for message lengths
    fig = go.Figure(data=[
        go.Bar(name='User', x=['Message Length'], y=[avg_user_message_length]),
        go.Bar(name='Bot', x=['Message Length'], y=[avg_bot_response_length])
    ])
    fig.update_layout(title="Average Message Length Comparison", barmode='group')
    st.plotly_chart(fig)

    # Sentiment analysis
    conversations = get_conversations(chatbot_id)
    sentiments = [sentiment for _, _, _, sentiment in conversations if sentiment != "Unknown"]
    if sentiments:
        sentiment_counts = pd.Series(sentiments).value_counts()
        fig = px.pie(sentiment_counts, values=sentiment_counts.values, names=sentiment_counts.index, title="Sentiment Distribution")
        st.plotly_chart(fig)
    else:
        st.write("No sentiment data available.")

    # Message frequency over time
    timestamps = [datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") for _, _, ts, _ in conversations]
    df = pd.DataFrame({'timestamp': timestamps})
    df['date'] = df['timestamp'].dt.date
    message_counts = df['date'].value_counts().sort_index()
    
    fig = px.line(x=message_counts.index, y=message_counts.values, title="Messages per Day")
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Number of Messages")
    st.plotly_chart(fig)

    # Export analytics
    if st.button("Export Analytics"):
        analytics_data = {
            "chatbot_name": selected_chatbot,
            "total_messages": total_messages,
            "avg_user_message_length": avg_user_message_length,
            "avg_bot_response_length": avg_bot_response_length,
            "sentiment_distribution": sentiment_counts.to_dict() if sentiments else {},
            "message_frequency": {date.strftime("%Y-%m-%d"): count for date, count in message_counts.items()}
        }
        
        json_data = json.dumps(analytics_data, indent=2, default=str)
        b64 = base64.b64encode(json_data.encode()).decode()
        href = f'<a href="data:application/json;base64,{b64}" download="chatbot_analytics.json">Download Analytics JSON</a>'
        st.markdown(href, unsafe_allow_html=True)

# Main execution
if __name__ == "__main__":
    main()
