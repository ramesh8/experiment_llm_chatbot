#create relationships between subject/topic to question

import time
import json
import re
import mysql.connector
from neo4j import GraphDatabase
from py2neo import Graph, Node, Relationship
from mysql.connector import connect

# start time
start_time = time.time()

mysql_connection = mysql.connector.connect(
    host="localhost",         # Change if your database is hosted elsewhere
    user="ramesh",     # Your MySQL username
    password="12345678", # Your MySQL password
    database="etutor"  # The name of your database
)

mysql_cursor = mysql_connection.cursor()

# Step 2: Connect to the Neo4j database
neo4j_driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("ramesh", "12345678"))
neo4j_session = neo4j_driver.session()

# Function to create a node if it doesn't exist, and update it if it does
def create_node(tx, label, id_key, id_value, properties=None):

    # Ensure that all properties are strings (especially for HTML content)
    if properties:
        for key, value in properties.items():
            if isinstance(value, dict):  # If the property is a dict, serialize it to a JSON string
                properties[key] = json.dumps(value)
            elif not isinstance(value, str):  # If it's not a string, convert it to a string
                properties[key] = str(value)

    node = tx.run(f"MATCH (n:{label} {{{id_key}: $id_value}}) RETURN n", id_value=id_value).single()
    
    if node:
        # If node exists, update it with new properties
        props_str = ', '.join([f"n.{key} = ${key}" for key in properties.keys()])
        query = f"MATCH (n:{label} {{{id_key}: $id_value}}) SET {props_str}"
        tx.run(query, id_value=id_value, **properties)
        print(f"Updated node {label} with {id_key} = {id_value} and properties {properties}")
    else:
        # If node doesn't exist, create it
        props_str = ', '.join([f"{key}: ${key}" for key in properties.keys()]) if properties else ''
        query = f"CREATE (n:{label} {{{id_key}: $id_value"
        if props_str:
            query += f", {props_str}"
        query += "})"
        tx.run(query, id_value=id_value, **properties)
        print(f"Created node {label} with {id_key} = {id_value} and properties {properties}")

# Function to create a relationship if it doesn't exist
def create_relationship(tx, node1_label, node1_id, node2_label, node2_id, relationship):

    node1_exists = tx.run(f"MATCH (n:{node1_label} {{id: $node1_id}}) RETURN n", node1_id=node1_id).single()
    node2_exists = tx.run(f"MATCH (n:{node2_label} {{id: $node2_id}}) RETURN n", node2_id=node2_id).single()

    if node1_exists and node2_exists:
        rel_exists = tx.run(f"""
            MATCH (n1:{node1_label} {{id: $node1_id}})-[r:{relationship}]->(n2:{node2_label} {{id: $node2_id}}) 
            RETURN r
        """, node1_id=node1_id, node2_id=node2_id).single()

        if not rel_exists:
            tx.run(f"""
                MATCH (n1:{node1_label} {{id: $node1_id}}), (n2:{node2_label} {{id: $node2_id}})
                CREATE (n1)-[:{relationship}]->(n2)
            """, node1_id=node1_id, node2_id=node2_id)
            print(f"Created relationship {relationship} between {node1_label}({node1_id}) and {node2_label}({node2_id})")
        else:
            print(f"Relationship {relationship} already exists between {node1_label}({node1_id}) and {node2_label}({node2_id})")
    else:
        print(f"Cannot create relationship {relationship}: Node(s) missing -> {node1_label}({node1_id}), {node2_label}({node2_id})")

# Function to remove HTML tags and handle bytes-like objects
def clean_html(raw_html):
    # Check if the input is in bytes format and decode to string
    if isinstance(raw_html, bytes):
        raw_html = raw_html.decode('utf-8')  # Decode bytes to string using UTF-8
    
    clean_re = re.compile('<.*?>')  # Regular expression to find HTML tags
    clean_text = re.sub(clean_re, '', raw_html)  # Apply regex to clean HTML tags
    return clean_text   

mysql_cursor.execute("SELECT id, subject_id, topic_id FROM question")
ids = mysql_cursor.fetchall()

with neo4j_session.begin_transaction() as tx:
    for id_row in ids:
        qid, sid, tid = id_row
        
        # #approach 1: either topic or subject
        # if tid==0 or tid==None:
        #     if sid!=0 and sid!=None :
        #         print(f"{qid} is missing topic, so linking it to subject {sid}.")
        #     else:
        #         print(f"{qid} is missing both topic and subject, so skipping it.")
        # else:
        #     print(f"{qid} has topic {tid}, so linking.")
        #
        # #approach 2: both topic and subject
        if tid != 0 and tid != None:
            print(f"linking question {qid} to topic {tid}")
            # create_relationship(tx, 'ID', main_id, 'Question', question_id, 'HAS_QUESTION')
            create_relationship(tx, 'Question', qid, 'Topic', tid, 'FROM_TOPIC')
        if sid != 0 and sid != None:
            print(f"linking question {qid} to subject {sid}")
            create_relationship(tx, 'Question', qid, 'Subject', sid, 'FROM_SUBJECT')

# Fixing issues
# 1. query to fix option relationships

# MATCH (q:Question)-[oldr:HAS_OPTION_A|HAS_OPTION_B|HAS_OPTION_C|HAS_OPTION_D|HAS_OPTION_E]-(o:Option) 
# CREATE (q:Question)-[newr:HAS_OPTION]-(o:Option)
# DELETE oldr 

# 2. query to store answer text in Answer node instead of option index
# MATCH (q:Question)-[r1:HAS_OPTION]-(o:Option)
# MATCH (q:Question)-[r2:HAS_ANSWER]-(a:Answer)
# WHERE a.answer_text=o.option_index
# SET a.answer_text=o.option_text, a.clean_option_text = o.clean_option_text, a.option_index=o.option_index
#

# check for issues
# MATCH (q:Question)-[r1:HAS_OPTION]-(o:Option)
# MATCH (q)-[r2:HAS_SOLUTION]-(so:Solution)
# MATCH (q)-[r3:HAS_ANSWER]-(a:Answer)
# MATCH (q)-[r4:FROM_SUBJECT]-(su:Subject)-[r6:HAS_SUBJECT]-(c:Class)-[r7:HAS_CLASS]-(co:Course)
# MATCH (q)-[r5:FROM_TOPIC]-(t:Topic)
# WHERE q.question_text CONTAINS 'natural numbers'
# RETURN q,r1,o,r2,so,r3,a,r4,su,r6,c,r7,co,r5,t LIMIT 10

# create indexes
"""
CREATE VECTOR INDEX questionIndex IF NOT EXISTS                
        FOR (o:Question)
        ON o.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }
        }

CREATE VECTOR INDEX answerIndex IF NOT EXISTS                
        FOR (o:Answer)
        ON o.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }
        }

CREATE VECTOR INDEX solutionIndex IF NOT EXISTS                
        FOR (o:Solution)
        ON o.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }
        }
"""