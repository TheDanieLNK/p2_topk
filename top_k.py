import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import pygsheets

# Page config
st.set_page_config(page_title="Which Posts Should Be Fact-Checked?", layout="centered")

# Authenticate Google Sheets
@st.cache_resource
def get_gsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gspread"],
        scopes=scopes
    )
    return pygsheets.authorize(custom_credentials=credentials)

# Load posts from CSV
@st.cache_data
def load_posts():
    return pd.read_csv("posts.csv")

# Create unique user session ID
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

# Header and instructions
st.title("FactCheck-Worthiness Review Task")

# User identifier input
user_identifier = st.text_input("Please enter your Participant ID (required to proceed):")

st.markdown("""
These posts have been ranked by an AI model based on their check-worthiness.
Please review each post and rate how check-worthy *you* think it is on a scale of 1 to 5.
You may optionally view the AI's reasoning by clicking **"Show AI Insight"**.
""")

# Load and display posts
df = load_posts()
df['text'] = df['text'].apply(lambda x: x.replace('$', '\\$') if isinstance(x, str) else x)
df = df.sort_values(by="model_score", ascending=False).reset_index(drop=True)

ratings = []

with st.form("topk_form"):
    for idx, row in df.iterrows():
        st.markdown(f"### Rank #{idx + 1}")
        st.markdown(f"**@{row['username']}**  |  **Likes:** {row['likes']}  |  **Retweets:** {row['retweets']}  |  **Followers:** {row['followers']}  |  **Following:** {row['following']}")
        st.markdown(f"**Post:** {row['text']}")

        # AI Insight toggle tracker
        insight_clicked = st.checkbox("Did you view the AI insight for this post?", key=f"insight_click_{row['post_id']}")

        with st.expander("Show AI Insight"):
            insights = eval(row.get("ai_insight", "[]"))  # Cautiously parse list of tuples
            if insights:
                for title, description in insights:
                    st.markdown(f"**{title}:** {description}")
            else:
                st.markdown("_No insight available for this post._")

        rating = st.radio(
            "Would you recommend this post for fact-checking?",
            options=[1, 2, 3, 4, 5],
            format_func=lambda x: {
                1: "Definitely not",
                2: "Probably not",
                3: "Not sure",
                4: "Probably yes",
                5: "Definitely yes"
            }[x],
            key=f"rating_{row['post_id']}"
        )


        st.divider()

        ratings.append({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": st.session_state.user_id,
            "participant_id": user_identifier,
            "post_id": row['post_id'],
            "rank": idx + 1,
            "rating": rating,
            "ai_insight_clicked": insight_clicked
        })

    submitted = st.form_submit_button("Submit Ratings")

    if submitted:
        if not user_identifier:
            st.warning("Please enter your Participant ID before submitting.")
        else:
            result_df = pd.DataFrame(ratings)
            gc = get_gsheet_client()
            sheet = gc.open("TopK_Ratings")
            wks = sheet.sheet1
            wks.append_table(result_df.values.tolist(), start='A2', end=None, dimension='ROWS', overwrite=False)
            st.success("Thank you! Your ratings have been submitted.")
