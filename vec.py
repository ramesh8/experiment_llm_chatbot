import streamlit as st
from llm import llm, embeddings
from graph import graph
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate

neo4jvector = Neo4jVector.from_existing_index(
    embeddings,  # (1)
    graph=graph,  # (2)
    index_name="moviePlots",  # (3)
    node_label="Movie",  # (4)
    text_node_property="plot",  # (5)
    embedding_node_property="plotEmbedding",  # (6)
    retrieval_query="""
RETURN
    node.plot AS text,
    score,
    {
        title: node.title,
        genres: node.genres,
        directors: [ (person)-[:DIRECTED]->(node) | person.name ],
        actors: [ (person)-[r:ACTED_IN]->(node) | [person.name, r.role] ],
        tmdbId: node.tmdbId,
        source: 'https://www.themoviedb.org/movie/'+ node.tmdbId
    } AS metadata
""",
)

from langchain_openai import ChatOpenAI
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph

chain = GraphCypherQAChain.from_llm(
    ChatOpenAI(temperature=0), graph=graph, verbose=True, allow_dangerous_requests=True
)

#query = "Where does Oliver Stone live?"
query = input("Enter Query: ") 

graph_result = chain.invoke(query)

vector_results = neo4jvector.similarity_search(query, k=1)
print(vector_results)
vector_result = vector_results[0].metadata["title"] +" is a movie directed by "+ vector_results[0].metadata["directors"][0]+", and the plot is "+vector_results[0].page_content
print(vector_result)

# Construct prompt for OpenAI
final_prompt = f"""You are a helpful question-answering agent. Your task is to analyze
and synthesize information from two sources: the top result from a similarity search
(unstructured information) and relevant data from a graph database (structured information).
Given the user's query: {query}, provide a meaningful and efficient answer based
on the insights derived from the following data:

Unstructured information: {vector_result}.
Structured information: {graph_result} """


from openai import OpenAI
client = OpenAI(
    # This is the default and can be omitted
    api_key=st.secrets["OPENAI_API_KEY"],
)

chat_completion = client.chat.completions.create(messages=[{"role": "user","content": final_prompt,  }],model="gpt-3.5-turbo",)

answer = chat_completion.choices[0].message.content.strip()
print(answer)
