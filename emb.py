import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.graphs import Neo4jGraph
import pandas as pd
from typing import List
import os
import neo4j
from neo4j import GraphDatabase
from langchain_community.graphs import Neo4jGraph

os.environ["OPENAI_API_KEY"] =st.secrets["OPENAI_API_KEY"]

# Connect to Neo4j database
neo4j_uri = "neo4j://localhost:7687"
neo4j_user = "ramesh"
neo4j_password = "12345678"

# Initialize Neo4j driver
neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

# Initialize Neo4jGraph (Check documentation for the exact parameters needed)
neo4j_graph = Neo4jGraph(
    url=neo4j_uri,
    username=neo4j_user,
    password=neo4j_password
)

# Initialize OpenAI Embeddings
embeddings = OpenAIEmbeddings()

vector_index = Neo4jVector.from_existing_graph(
 
    embedding=embeddings,
 
    search_type="hybrid",
 
    node_label="Solution",
 
    text_node_properties=["clean_solution_text"],
 
    embedding_node_property="embedding",
 
    url=neo4j_uri,
 
    username=neo4j_user,
 
    password=neo4j_password
 
)

# next step is to create indexes on embeddings.