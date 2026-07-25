import pandas as pd
import streamlit as st
from pymongo import MongoClient

# Read TSV, skip blank lines and repeated headers
df = pd.read_csv("Double Annotation - 2round.tsv", sep="\t", encoding="utf-8")
df = df.dropna(subset=["QID", "Question", "LoginName"])
df = df[df["QID"] != "QID"]  # drop repeated header rows

# Extract numeric QID from "QID:53" -> 53
df["QID"] = df["QID"].str.replace("QID:", "", regex=False).astype(int)

# Strip whitespace from LoginName
df["LoginName"] = df["LoginName"].str.strip()

MONGO_URI = st.secrets["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["database"]
evibench_collection = db["evibench"]

updated = 0
not_found = []

for _, row in df.iterrows():
    qid = row["QID"]
    question = row["Question"]
    login_name = row["LoginName"]

    result = evibench_collection.update_one(
        {"QID": qid, "Question": question},
        {"$set": {"Email": login_name}}
    )

    if result.matched_count > 0:
        updated += 1
        print(f"  Updated QID {qid} -> Email: {login_name}")
    else:
        not_found.append(qid)
        print(f"  NOT FOUND: QID {qid}")

print(f"\nDone. Updated: {updated}, Not found: {len(not_found)}")
if not_found:
    print(f"Missing QIDs: {not_found}")
