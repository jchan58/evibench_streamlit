import streamlit as st
import pandas as pd
from pymongo import MongoClient
import datetime


def fix_encoding(val):
    """Fix mojibake: UTF-8 bytes that were decoded as Latin-1."""
    if isinstance(val, str):
        try:
            return val.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return val
    return val

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
    df = pd.DataFrame(docs)
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].map(fix_encoding)
    return df

evibench_df = load_evibench()
st.title("EviBench - Pilot Study Login")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    user_email = st.text_input("Please enter your username").strip().lower()

    if st.button("Enter"):
        if not user_email:
            st.error("Please enter your username")
        elif user_email not in evibench_df["Email"].str.lower().tolist():
            st.error("Sorry, your username is not approved for this study")
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
