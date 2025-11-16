import streamlit as st
import pandas as pd
from pymongo import MongoClient
import datetime
from streamlit_extras.switch_page_button import switch_page

# Connect to MongoDB
MONGO_URI = st.secrets["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["database"]
users_collection = db["users"]

def load_evibench():
    client = MongoClient(st.secrets["MONGO_URI"])
    db = client["database"]
    evibench_collection = db["evibench"]
    docs = list(evibench_collection.find({}, {"_id": 0}))
    return pd.DataFrame(docs)

evibench_df = load_evibench()
st.title("EviBench - Pilot Study Login")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    user_email = st.text_input("Please enter your email").strip().lower()

    if st.button("Enter"):
        if not user_email:
            st.error("Please enter your email")
        elif user_email not in evibench_df["Email"].str.lower().tolist():
            st.error("Sorry, your email is not approved for this study")
        else:
            # Save user info if never logged in
            user = users_collection.find_one({"email": user_email})
            if not user:
                users_collection.insert_one(
                    {"email": user_email, "created_at": datetime.datetime.utcnow()}
                )

            st.session_state.logged_in = True
            st.session_state.user_email = user_email
            st.switch_page("pages/annotation.py")

else:
    st.info("You are already logged in. Redirecting to annotation page...")
    st.switch_page("pages/annotation.py")
