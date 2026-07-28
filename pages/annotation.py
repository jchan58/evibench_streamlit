import streamlit as st
import pandas as pd
import datetime
from pymongo import MongoClient
import time
import re


def fix_encoding(val):
    """Fix mojibake: UTF-8 bytes that were decoded as Latin-1."""
    if isinstance(val, str):
        try:
            return val.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return val
    return val


def linkify_urls(text):
    """Convert URLs in text to clickable markdown links."""
    url_pattern = r'(https?://[^\s\)]+)'
    return re.sub(url_pattern, r'[\1](\1)', text)

# remove the pages sidebar
st.markdown("""
<style>
[data-testid="stSidebarNav"] { 
    display: none !important; 
}
</style>
""", unsafe_allow_html=True)

MAX_ANSWER = 5

# Cache evibench + db
@st.cache_data
def load_evibench():
    client = MongoClient(st.secrets["MONGO_URI"])
    db = client["database"]
    evibench_collection = db["evibench"]

    docs = list(evibench_collection.find({}, {"_id": 0}))
    df = pd.DataFrame(docs)
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].map(fix_encoding)
    return df

@st.cache_resource
def get_db():
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI)
    return client["database"]

# Load in db 
evibench_df = load_evibench()
db = get_db()
responses_collection = db["responses_2"]
edits_collection = db["response_edits"]

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

def go_to_next_uncompleted():
    completed_qids_ptr = responses_collection.find(
        {"email": user_email}, {"qid": 1, "_id": 0}
    )
    completed = {doc["qid"] for doc in completed_qids_ptr}
    remaining = user_df[~user_df["QID"].isin(completed)]
    if not remaining.empty:
        next_qid = remaining.iloc[0]["QID"]
        st.session_state.current_qid = next_qid
        st.session_state.answer_idx = 0
        st.session_state.current_responses = {}
    else:
        # All done — move to the next question in the list after the current one
        all_qids = user_df["QID"].tolist()
        current = st.session_state.current_qid
        if current in all_qids:
            curr_idx = all_qids.index(current)
            next_idx = (curr_idx + 1) % len(all_qids)
            st.session_state.current_qid = all_qids[next_idx]
        else:
            st.session_state.current_qid = all_qids[0]
        st.session_state.answer_idx = 0
        st.session_state.current_responses = load_saved_response(st.session_state.current_qid)

def load_saved_response(qid):
    doc = responses_collection.find_one({"email": user_email, "qid": int(qid)})
    if doc:
        return doc.get("responses", {})
    return {}

def switch_question(target_qid):
    st.session_state.current_qid = target_qid
    st.session_state.answer_idx = 0
    if target_qid in completed_qids:
        st.session_state.current_responses = load_saved_response(target_qid)
    else:
        st.session_state.current_responses = {}
    st.rerun()

st.sidebar.markdown("## 📋 Your Questions")
user_qids = user_df["QID"].tolist()
if "current_qid" not in st.session_state:
    first_qid = uncompleted_qids.iloc[0]["QID"] if not uncompleted_qids.empty else user_qids[0]
    st.session_state.current_qid = first_qid
    if first_qid in completed_qids:
        st.session_state.current_responses = load_saved_response(first_qid)
    else:
        st.session_state.current_responses = {}

for qid in user_qids:
    is_current = (qid == st.session_state.current_qid)
    label = f"➡️ QID {qid}" if is_current else f"QID {qid}"
    if st.sidebar.button(label, key=f"goto_{qid}"):
        switch_question(qid)

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
    st.info("You've completed all annotations. You may review and edit your previous responses.")

if st.session_state.current_qid is not None:
    row = user_df[user_df["QID"] == st.session_state.current_qid].iloc[0]
    st.markdown("### 📌 Topic")
    st.info(row['Qtopic'])
    with st.expander("❓ Question"):
        st.write(row['Question'])
    
    if "answer_idx" not in st.session_state:
        st.session_state.answer_idx = 0
    if "current_responses" not in st.session_state:
        st.session_state.current_responses = {}

    idx = st.session_state.answer_idx
    
    # save the current values
    saved = st.session_state.current_responses.get(f"Answer{idx+1}", {})

    def get_saved(path, default=None):
        node = saved
        for p in path:
            if node and p in node:
                node = node[p]
            else:
                return default
        return node

    accuracy_default = get_saved(["accuracy", "rating"])
    accuracy_explain_default = get_saved(["accuracy", "explanation"], "")
    comp_default = get_saved(["comprehension"], 3)
    novel_default = get_saved(["novelty"])
    analysis_cat_default = get_saved(["analysis_logic", "category"])
    analysis_detail_default = get_saved(["analysis_logic", "details"], [])
    analysis_other_default = get_saved(["analysis_logic", "others_explanation"], "")
    other_comments_default = get_saved(["feedback"], "")


    # Only show answers when idx is less than 4
    if idx < 4:
        ans_col = f"Answer{idx+1}"
        ref_col = f"Reference{idx+1}"

        with st.expander(f"📝 Answer {idx+1}"):
            st.write(row[ans_col])

        with st.expander(f"📚 Reference {idx+1}"):
            st.markdown(linkify_urls(row[ref_col]))

        # Eval Topics
        accuracy = st.radio(
            "How accurate was the answer? (i.e. were the facts, claims, and conclusions scientifically correct and supported by the references?)",
            ["High", "Moderate", "Low Accuracy"],
            index=(["High","Moderate","Low Accuracy"].index(accuracy_default)
                if accuracy_default else None),
            key=f"accuracy_{row['QID']}_{idx+1}"
        )
        
        # clear the accuracy comment when change
        prev_accuracy_key = f"prev_accuracy_{row['QID']}_{idx+1}"
        if prev_accuracy_key not in st.session_state:
            st.session_state[prev_accuracy_key] = accuracy

        # if the user changes radio then update
        explain_key = f"accuracy_explain_{row['QID']}_{idx+1}"
        if accuracy != st.session_state[prev_accuracy_key]:
            if explain_key in st.session_state:
                st.session_state[explain_key] = ""

        # update previous key
        st.session_state[prev_accuracy_key] = accuracy

        # require explanation for moderate or low answers
        if accuracy == "Moderate":
            accuracy_explain = st.text_area(
                "Please explain why the accuracy was moderate (optional):",
                value=accuracy_explain_default,
                key=f"accuracy_explain_{row['QID']}_{idx+1}",
                height=80
            )
        elif accuracy == "Low Accuracy":
            accuracy_explain = st.text_area(
                "Please explain why the accuracy was low (optional):",
                value=accuracy_explain_default,
                key=f"accuracy_explain_{row['QID']}_{idx+1}",
                height=80
            )
        else:
            accuracy_explain = None

        comp = st.slider(
            "How comprehensive was the answer? (i.e. did it fully address all aspects of the question, or were there gaps in coverage?)",
            1, 5,
            value=comp_default,
            key=f"comp_{row['QID']}_{idx+1}"
        )

        novel = st.radio(
            "Were there any novel insights? (i.e. correct information that is often overlooked or underappreciated)",
            ["Yes", "No", "Maybe"],
            index=(["Yes","No","Maybe"].index(novel_default)
                if novel_default else None),
            key=f"novel_{row['QID']}_{idx+1}"
        )
        analysis_cat = st.radio(
            "How was the analysis quality? (i.e. how well did the answer break down and reason through the question?)",
            ["Good", "Average", "Bad"],
            index=(["Good","Average","Bad"].index(analysis_cat_default)
                if analysis_cat_default else None),
            key=f"analysis_cat_{row['QID']}_{idx+1}"
        )
        # reset if category changes
        if analysis_cat != analysis_cat_default:
            analysis_detail_default = []
            analysis_other_default = ""

        if analysis_cat == 'Good':
            good_options = [
                "Good explanation of biological concepts",
                "Insightful analysis of different aspects of the question",
                "Evidence is relevant to the question/claim",
                "Profound summarization of the entire analysis",
                "Others"
            ]
            analysis_detail = st.multiselect(
                "Why was it good? (select all that apply)",
                good_options,
                default=[d for d in analysis_detail_default if d in good_options],
                key=f"analysis_good_{row['QID']}_{idx+1}"
            )
            if "Others" in analysis_detail:
                analysis_other_explain = st.text_area(
                    "Please explain why choose 'Others':",
                    value=analysis_other_default,
                    key=f"analysis_good_other_{row['QID']}_{idx+1}"
                )
            else:
                analysis_other_explain = None

        elif analysis_cat == "Average":
            avg_options = [
                "Broad explanation of biological concepts",
                "Straightforward analysis of the question",
                "Evidence is partially relevant to the question/claim",
                "Reasonable summarization of the analysis",
                "Others"
            ]
            analysis_detail = st.multiselect(
                "Why was it average? (select all that apply)",
                avg_options,
                default=[d for d in analysis_detail_default if d in avg_options],
                key=f"analysis_general_{row['QID']}_{idx+1}"
            )
            if "Others" in analysis_detail:
                analysis_other_explain = st.text_area(
                    "Please explain why choose 'Others':",
                    value=analysis_other_default,
                    key=f"analysis_average_other_{row['QID']}_{idx+1}"
                )
            else:
                analysis_other_explain = None

        elif analysis_cat == "Bad":
            bad_options = [
                "No or poor explanation of biological concepts",
                "Shallow or overly brief analysis of the question",
                "Evidence is not relevant to the question/claim",
                "Missing or superficial summarization of the analysis",
                "Others"
            ]
            analysis_detail = st.multiselect(
                "Why was it bad? (select all that apply)",
                bad_options,
                default=[d for d in analysis_detail_default if d in bad_options],
                key=f"analysis_bad_{row['QID']}_{idx+1}"
            )
            if "Others" in analysis_detail:
                analysis_other_explain = st.text_area(
                    "Please explain why choose 'Others':",
                    value=analysis_other_default,
                    key=f"analysis_bad_other_{row['QID']}_{idx+1}"
                )
            else:
                analysis_other_explain = None
        else:
            analysis_detail = []

        other_comments = st.text_area(
            "Is there any additional feedback you would like to give?",
            value=other_comments_default,
            key=f"feedback_{row['QID']}_{idx+1}",
            height=80
        )

        cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1])
        with cols[0]:
            if st.button("Back") and idx > 0:
                st.session_state.answer_idx -= 1
                st.rerun()
        with cols[7]:
            if st.button("Next"): 
                valid = True
                error_msgs = []

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

    # show reference page as last page
    if idx == 4:
        st.markdown("### 📚 Reference Evaluation")
        st.markdown("Please rate the quality of each reference and then select your preferred one.")

        # ALWAYS define these at the top of this block
        saved_refs = st.session_state.current_responses.get("reference_ratings", {}) or {}
        saved_pref = st.session_state.current_responses.get("preferred_reference")

        reference_ratings = {}

        for i in range(1, 5):
            ref_key = f"Reference{i}"

            st.markdown(f"#### Reference {i}")
            with st.expander(f"📚 Reference {i} Content"):
                st.markdown(linkify_urls(row[ref_key]))

            rating_key = f"ref_rating_{row['QID']}_{i}"
            comment_key = f"ref_comment_{row['QID']}_{i}"

            # pull any previously saved rating/comment
            saved_rating = saved_refs.get(ref_key, {}).get("rating")
            saved_comment = saved_refs.get(ref_key, {}).get("comment", "")

            rating_index = (
                ["Good", "Average", "Bad"].index(saved_rating)
                if saved_rating in ["Good", "Average", "Bad"]
                else None
            )

            rating = st.radio(
                f"How relevant was Reference {i} to the question/claim?",
                ["Good", "Average", "Bad"],
                index=rating_index,
                key=rating_key,
            )

            # clear comment if user changes choice
            prev_rating_key = f"prev_rating_{row['QID']}_{i}"
            if prev_rating_key not in st.session_state:
                st.session_state[prev_rating_key] = saved_rating

            if rating != st.session_state[prev_rating_key]:
                if comment_key in st.session_state:
                    st.session_state[comment_key] = ""

            st.session_state[prev_rating_key] = rating
            # require comment if not good
            if rating in ["Average", "Bad"]:
                comment = st.text_area(
                    f"Please explain why Reference {i} was {rating.lower()} (optional)",
                    value=saved_comment,
                    key=comment_key,
                    height=80,
                )
            else:
                comment = ""

            reference_ratings[ref_key] = {
                "rating": rating,
                "comment": comment,
            }

            st.markdown("---")

        # preferred reference
        options_pref = ["Reference 1", "Reference 2", "Reference 3", "Reference 4"]
        pref_index = options_pref.index(saved_pref) if saved_pref in options_pref else None

        preferred = st.radio(
            "Which reference do you prefer overall?",
            options_pref,
            index=pref_index,
            key=f"preferred_{row['QID']}",
        )

        cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1])
        with cols[0]:
            if st.button("Back"):
                new_refs = {}
                for i in range(1, 5):
                    ref_key = f"Reference{i}"
                    rating_key = f"ref_rating_{row['QID']}_{i}"
                    comment_key = f"ref_comment_{row['QID']}_{i}"

                    new_refs[ref_key] = {
                        "rating": st.session_state.get(rating_key),
                        "comment": st.session_state.get(comment_key, ""),
                    }

                st.session_state.current_responses["reference_ratings"] = new_refs
                st.session_state.current_responses["preferred_reference"] = st.session_state.get(
                    f"preferred_{row['QID']}"
                )

                st.session_state.answer_idx = 3
                st.rerun()


        with cols[7]:
            if st.button("Next"):
                valid = True
                errors = []

                # Validate all reference ratings
                for i in range(1, 5):
                    r = reference_ratings[f"Reference{i}"]["rating"]
                    c = reference_ratings[f"Reference{i}"]["comment"]

                    if r is None:
                        valid = False
                        errors.append(f"Please rate Reference {i}.")

                if preferred is None:
                    valid = False
                    errors.append("Please select your preferred reference.")

                if not valid:
                    for msg in errors:
                        st.error(msg)
                else:
                    # Save to session state
                    st.session_state.current_responses["reference_ratings"] = reference_ratings
                    st.session_state.current_responses["preferred_reference"] = preferred

                    st.session_state.answer_idx = 5
                    st.rerun()

    if idx == 5:
        st.markdown("### Select the Best Answers")
        st.markdown("You have reviewed all answers. Please select which answers you felt were the best.")

        # Summary of previous ratings
        st.markdown("#### Your Ratings Summary")
        responses = st.session_state.current_responses
        for i in range(1, 5):
            ans_data = responses.get(f"Answer{i}", {})
            acc = ans_data.get("accuracy", {}).get("rating", "—")
            comp = ans_data.get("comprehension", "—")
            novel = ans_data.get("novelty", "—")
            analysis = ans_data.get("analysis_logic", {}).get("category", "—")
            with st.expander(f"Answer {i} — Accuracy: {acc} | Comprehension: {comp}/5 | Novelty: {novel} | Analysis: {analysis}"):
                st.write(row[f"Answer{i}"])

        ref_ratings = responses.get("reference_ratings", {})
        pref_ref = responses.get("preferred_reference", "—")
        ref_summary_parts = []
        for i in range(1, 5):
            r = ref_ratings.get(f"Reference{i}", {}).get("rating", "—")
            ref_summary_parts.append(f"Ref {i}: {r}")
        st.markdown(f"**References:** {' | '.join(ref_summary_parts)} | Preferred: {pref_ref}")

        st.markdown("---")
        saved_best = st.session_state.current_responses.get("best_answers", [])
        best_answers_selected = st.multiselect(
            "Which answers were the best? (Select all that applies)",
            ["Answer 1", "Answer 2", "Answer 3", "Answer 4"],
            default=saved_best,
            key=f"best_answers_{row['QID']}"
        )

        cols = st.columns([1, 1, 1, 1, 1, 1, 1])
        with cols[0]:
            if st.button("Back", key=f"final_back_{row['QID']}"):
                st.session_state.current_responses["best_answers"] = best_answers_selected
                st.session_state.answer_idx = 4
                st.rerun()
        
        with cols[6]:
            is_edit = int(row["QID"]) in completed_qids
            submit_label = "Save Edit" if is_edit else "Submit"
            if st.button(submit_label):
                if not best_answers_selected:
                    st.error("Please select at least one answer before submitting.")
                else:
                    st.session_state.current_responses["best_answers"] = best_answers_selected
                    doc = {
                        "email": user_email,
                        "qid": int(row["QID"]),
                        "responses": st.session_state.current_responses,
                        "timestamp": datetime.datetime.utcnow()
                    }
                    if is_edit:
                        edits_collection.insert_one(doc)
                        st.success("Edit saved!")
                    else:
                        responses_collection.insert_one(doc)
                        st.success("Response submitted!")
                    st.session_state.answer_idx = 0
                    st.session_state.current_responses = {}
                    go_to_next_uncompleted()
                    st.rerun()

