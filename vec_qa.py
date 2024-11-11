import streamlit as st
from llm import llm, embeddings
from graph import graph
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
# from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.chains import GraphCypherQAChain
# from langchain_community.graphs import Neo4jGraph
from openai import OpenAI
class VECQA():
    neo4jvector = Neo4jVector.from_existing_index(
        embeddings,  # (1)
        graph=graph,  # (2)
        index_name="questionIndex",  # (3)
        node_label="Question",  # (4)
        text_node_property="clean_question_text",  # (5)
        embedding_node_property="embedding",  # (6)
        retrieval_query="""
    RETURN
        node.clean_question_text AS text,
        score,
        {
            title: node.question_text,
            subject: [(node)-[:FROM_SUBJECT]->(Subject) | Subject.subject_name ],
            topic: [(node)-[:FROM_TOPIC]->(Topic) | Topic.topic_name ],
            solution: [ (node)-[:HAS_SOLUTION]->(Solution) | Solution.solution_text ],
            answer: [(node)-[:HAS_ANSWER]->(Answer) | Answer.answer_text]
        } AS metadata
    """,
    )

    chain = GraphCypherQAChain.from_llm(
        ChatOpenAI(temperature=0), graph=graph, verbose=True, allow_dangerous_requests=True
    )

#query = "Where does Oliver Stone live?"
# query = input("Enter Query: ") 
    @staticmethod
    def getprompt(query):

        graph_result = VECQA.chain.invoke(query)

        vector_results = VECQA.neo4jvector.similarity_search(query, k=1)
        print(vector_results)

        title = vector_results[0].metadata["title"] 
        solution = " ".join(vector_results[0].metadata["solution"])
        subject = ", ".join(vector_results[0].metadata["subject"])
        topics = ", ".join(vector_results[0].metadata["topic"])
        answer = ", ".join(vector_results[0].metadata["answer"])


        vector_result = title +" is the question with solution "+ solution +", belongs to subject called "+ subject +" and topics named "+ topics +" and it's answer is "+ answer
        # print(vector_result)

        # Construct prompt for OpenAI
        final_prompt = f"""You are a helpful question-answering agent. Your task is to analyze
        and synthesize information from two sources: the top result from a similarity search
        (unstructured information) and relevant data from a graph database (structured information).

        Given the user's query: {query}, provide a meaningful and efficient answer based
        on the insights derived from the following data:

        Unstructured information: {vector_result}.
        Structured information: {graph_result} 
        Give the answer directly, don't include your thoughts or analysis in result.
        """

        return final_prompt

    @staticmethod
    def get_openai_result(prompt):
        client = OpenAI(
            # This is the default and can be omitted
            api_key=st.secrets["OPENAI_API_KEY"],
        )

        chat_completion = client.chat.completions.create(messages=[{"role": "user","content": prompt,  }],model="gpt-3.5-turbo",)

        answer = chat_completion.choices[0].message.content.strip()
        return answer
