import pandas as pd
import streamlit as st
from pymongo import MongoClient

df = pd.read_csv("EviBench-Final.csv", encoding="latin1")

MONGO_URI = st.secrets["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["database"]
evibench_collection = db["evibench"]
evibench_collection.delete_many({})
data = df.to_dict(orient="records") 
evibench_collection.insert_many(data)

print("CSV uploaded to MongoDB!")
