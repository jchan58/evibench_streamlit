import pandas as pd
import streamlit as st
from pymongo import MongoClient

df = pd.read_csv("new_question_1214_chi.csv")

MONGO_URI = st.secrets["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["database"]
evibench_collection = db["evibench"]
data = df.to_dict(orient="records")
evibench_collection.insert_many(data)
print("CSV appended to MongoDB!")