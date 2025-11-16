import streamlit as st
import pandas as pd
import datetime
from pymongo import MongoClient
from streamlit_extras.switch_page_button import switch_page
import time

MAX_ANSWER = 5

# Cache evibench + db
@st.cache_data
def load_evibench():
    client = MongoClient(st.secrets["MONGO_URI"])
    db = client["database"]
    evibench_collection = db["evibench"]

    docs = list(evibench_collection.find({}, {"_id": 0}))
    return pd.DataFrame(docs)

@st.cache_resource
def get_db():
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI)
    return client["database"]

# Load in db 
evibench_df = load_evibench()
db = get_db()
responses_collection = db["responses"]

# Check if user is logged in 
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in the first page.")
    st.switch_page("app.py")

user_email = st.session_state.user_email
user_df = evibench_df[evibench_df['Email'].str.lower() == user_email]

completed_qids_ptr = responses_collection.find(
    {"email": user_email}, {"qid": 1, "_id": 0}
)
completed_qids = {doc["qid"] for doc in completed_qids_ptr}
uncompleted_qids = user_df[~user_df['QID'].isin(completed_qids)]

# Check the progress of the user
total = len(user_df)
completed = len(completed_qids)

if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()

# Add in the logout and progress bar for user
col1, col2 = st.columns([4, 1])

with col1:
    st.markdown("Progress")
    st.progress(completed / total if total > 0 else 0)
    st.caption(f"Completed {completed} of {total} Questions")

with col2:
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.success("You have been logged out.")
        st.switch_page("app.py")

st.divider()

# Display
if uncompleted_qids.empty:
    st.success("You've completed all annotation!")
else:
    row = uncompleted_qids.iloc[0]

    st.markdown("### 📌 Topic")
    st.info(row['Qtopic'])

    with st.expander("❓ Question"):
        st.write(row['Question'])
    
    if "answer_idx" not in st.session_state:
        st.session_state.answer_idx = 0
    if "current_responses" not in st.session_state:
        st.session_state.current_responses = {}

    idx = st.session_state.answer_idx

    # Only show answers when idx is greater than 4
    if idx < 4:
        ans_col = f"Answer{idx+1}"
        ref_col = f"Reference{idx+1}"

        with st.expander(f"📝 Answer {idx+1}"):
            st.write(row[ans_col])

        with st.expander(f"📚 Reference {idx+1}"):
            st.code(row[ref_col], language="text")

        # Eval Topics
        accuracy = st.radio(
            "How accurate was the answer?",
            ["High", "Moderate", "Low Accuracy"],
            index=None,
            key=f"accuracy_{row['QID']}_{idx+1}"
        )

        # Require explanation for Moderate or Low Answers
        if accuracy == "Moderate":
            accuracy_explain = st.text_area(
                "Please explain why the accuracy was moderate:",
                key=f"accuracy_explain_{row['QID']}_{idx+1}",
                height=80
            )
        elif accuracy == "Low Accuracy":
            accuracy_explain = st.text_area(
                "Please explain why the accuracy was low:",
                key=f"accuracy_explain_{row['QID']}_{idx+1}",
                height=80
            )
        else:
            accuracy_explain = None

        comp = st.slider(
            "How comprehensive was the answer?",
            1, 5, 3,
            key=f"comp_{row['QID']}_{idx+1}"
        )

        novel = st.radio(
            "Were there novel findings?",
            ["Yes", "No", "Maybe"],
            index=None,
            key=f"novel_{row['QID']}_{idx+1}"
        )

        analysis_cat = st.radio(
            "How was the analysis quality?",
            ["Good", "Average", "Bad"],
            index=None,
            key=f"analysis_cat_{row['QID']}_{idx+1}"
        )

        if analysis_cat == 'Good': 
            analysis_detail = st.multiselect(
                "Why was it good? (select all that apply)",
                [
                    "Good explanation of biological concepts",
                    "Insightful analysis of different aspects of the question",
                    "Strong evidence supporting the core conclusion",
                    "Profound summarization of the entire analysis",
                    "Others"
                ],
                key=f"analysis_good_{row['QID']}_{idx+1}"
            )
            if "Others" in analysis_detail:
                analysis_other_explain = st.text_area(
                    "Please explain why choose 'Others':",
                    key=f"analysis_good_other_{row['QID']}_{idx+1}"
                )
            else:
                analysis_other_explain = None

        elif analysis_cat == "Average":
            analysis_detail = st.multiselect(
                "Why was it average? (select all that apply)",
                [
                    "Broad explanation of biological concepts",
                    "Straightforward analysis of the question",
                    "Relevant evidence supporting the core conclusion",
                    "Reasonable summarization of the analysis",
                    "Others"
                ],
                key=f"analysis_general_{row['QID']}_{idx+1}"
            )
            if "Others" in analysis_detail:
                analysis_other_explain = st.text_area(
                    "Please explain why choose 'Others':",
                    key=f"analysis_average_other_{row['QID']}_{idx+1}"
                )
            else:
                analysis_other_explain = None

        elif analysis_cat == "Bad":
            analysis_detail = st.multiselect(
                "Why was it bad? (select all that apply)",
                [
                    "No or poor explanation of biological concepts",
                    "Shallow or overly brief analysis of the question",
                    "Limited or weak evidence for the core conclusion",
                    "Missing or superficial summarization of the analysis",
                    "Others"
                ],
                key=f"analysis_bad_{row['QID']}_{idx+1}"
            )
            if "Others" in analysis_detail:
                analysis_other_explain = st.text_area(
                    "Please explain why choose 'Others':",
                    key=f"analysis_bad_other_{row['QID']}_{idx+1}"
                )
            else:
                analysis_other_explain = None
        else:
            analysis_detail = []

        other_comments = st.text_area(
            "Is there any additional feedback you would like to give?",
            key=f"feedback_{row['QID']}_{idx+1}",
            height=80
        )

        # Next button for each answer
        if st.button("Next"): 
            valid = True
            error_msgs = []

            # Accuracy validation
            if accuracy in ["Moderate", "Low Accuracy"] and (not accuracy_explain or not accuracy_explain.strip()):
                valid = False
                error_msgs.append("Please provide an explanation for the accuracy rating.")
            
            if "Others" in analysis_detail and (not analysis_other_explain or not analysis_other_explain.strip()):
                valid = False
                error_msgs.append("Please provide an explanation for 'Others' in analysis detail.")

            if not valid:
                for msg in error_msgs:
                    st.error(msg)
            else:
                end_time = time.time()
                time_spent = end_time - st.session_state.start_time
                st.session_state.start_time = time.time()
                st.session_state.current_responses[f"Answer{idx+1}"] = {
                    "accuracy": {
                        "rating": accuracy,
                        "explanation": accuracy_explain
                    },
                    "comprehension": comp,
                    "novelty": novel, 
                    "analysis_logic": {
                        "category": analysis_cat,
                        "details": analysis_detail, 
                        "others_explanation": analysis_other_explain
                    },
                    "feedback": other_comments,
                    "time_spent_sec": round(time_spent, 2)
                }
                if idx < 3: 
                    st.session_state.answer_idx += 1
                    st.rerun() 
                else: 
                    st.session_state.answer_idx = 4
                    st.rerun()
        progress_fraction = (idx + 1) / MAX_ANSWER
        st.markdown("---")
        st.progress(progress_fraction)
        st.caption(f"Answer {idx+1} of 4")

    # Show reference page as last page
    if idx == 4:
        st.markdown('Select your preferred reference list')
        st.markdown("### 📚 References")
        for i in range(1, 5):
            with st.expander(f"📚 Reference {i}"):
                st.code(row[f"Reference{i}"], language="text")

        preferred = st.radio(
            "Which reference do you prefer overall?",
            ["Reference 1", "Reference 2", "Reference 3", "Reference 4"],
            index=None,
            key=f"preferred_{row['QID']}"
        )
        if st.button("Submit"):
            if preferred is None:
                st.error("Please select your preferred reference before submitting.")
            else:
                responses_collection.insert_one({
                    "email": user_email, 
                    "qid": int(row["QID"]),
                    "responses": st.session_state.current_responses, 
                    "preferred_reference": preferred,
                    "timestamp": datetime.datetime.utcnow()
                })
                st.session_state.answer_idx = 0
                st.session_state.current_responses = {}
                st.success("Response submitted!")
                st.switch_page("pages/annotation.py")
