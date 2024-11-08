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

mysql_cursor.execute("SELECT class_id, class_name, class_order FROM classes")
classes = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT course_id, class_ids, course_name, course_order FROM courses")
courses = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT chapter_id, chapter, subject_id, class_id, sort_order FROM chapters")
chapters = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT subject_id, subject, class_id, course_id, sort_order FROM subjects")
subjects = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT topic_id, topic, chapter_id, class_id, sort_order FROM topics")
topics = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT stopic_id, sub_topic, topic_id, class_id, section_id FROM sub_topics")
sub_topics = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT id, question_id, et_question_id, sl_question_id, option, option_index FROM question_options")
question_options = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT qs_id, question_id, et_question_id, sl_question_id, solution FROM question_solutions")
questions_solutions = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT section_id, section_name, class_id FROM sections")
sections = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT id, et_question_id, sl_question_id, subject_id, topic_id, course_id, class_id FROM question")
ids = mysql_cursor.fetchall()

mysql_cursor.execute("SELECT question_id, et_question_id, sl_question_id, question, answer FROM question_info")
question_info = mysql_cursor.fetchall()


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

# Starting transactions
def process_data_in_batches(neo4j_session, courses, classes, sections, subjects, chapters, topics, sub_topics, ids, question_info, question_options, questions_solutions):
    
    # Step 1: Course nodes link to Class nodes
    with neo4j_session.begin_transaction() as tx:
        for course_row in courses:
            course_id, class_id, course_name, course_order = course_row
            create_node(tx, 'Course', 'id', course_id, {'course_name': course_name, 'course_order': course_order})
            class_ids = class_id.split(',')
            for class_id in class_ids:
                class_id = class_id.strip()
                class_row = next((c for c in classes if str(c[0]) == class_id), None)
                if class_row:
                    class_id, class_name, class_order = class_row
                    create_node(tx, 'Class', 'id', class_id, {'class_name': class_name, 'class_order': class_order})
                    create_relationship(tx, 'Course', course_id,'Class', class_id, 'HAS_CLASS')

    # Step 2: Class nodes link to Subject nodes
    with neo4j_session.begin_transaction() as tx:
        for subject_row in subjects:
            subject_id, subject_name, class_ids, course_id, sort_order = subject_row
            # Create Subject node
            create_node(tx, 'Subject', 'id', subject_id, {'subject_name': subject_name, 'sort_order': sort_order})
            
            # Handle multiple class_ids (assuming they are comma-separated)
            class_ids = class_ids.split(',')
            for class_id in class_ids:
                class_id = class_id.strip()  # Clean any extra spaces
                # Find corresponding class details from classes dataset
                class_row = next((c for c in classes if str(c[0]) == class_id), None)
                if class_row:
                    class_id, class_name, class_order = class_row
                    # Create Class node if it doesn't exist
                    create_node(tx, 'Class', 'id', class_id, {'class_name': class_name, 'class_order': class_order})
                    # Create the relationship between Class and Subject
                    create_relationship(tx, 'Class', class_id, 'Subject', subject_id, 'HAS_SUBJECT')
  

    # Step 3: Subject nodes link to Chapter nodes
    with neo4j_session.begin_transaction() as tx:
        for chapter_row in chapters:
            chapter_id, chapter_name, subject_id, class_id, sort_order = chapter_row
            create_node(tx, 'Chapter', 'id', chapter_id, {'chapter_name': chapter_name, 'sort_order': sort_order})
            create_relationship(tx, 'Subject', subject_id, 'Chapter', chapter_id, 'HAS_CHAPTER')

    # Step 4: Chapter nodes link them to Topic nodes 
    with neo4j_session.begin_transaction() as tx:
        for topic_row in topics:
            topic_id, topic_name, chapter_id, class_id, sort_order = topic_row
            create_node(tx, 'Topic', 'id', topic_id, {'topic_name': topic_name, 'sort_order': sort_order})
            create_relationship(tx, 'Chapter', chapter_id, 'Topic', topic_id, 'HAS_TOPIC')

    # Step 5: Topic nodes link to SubTopic nodes
    with neo4j_session.begin_transaction() as tx:
        for sub_topic_row in sub_topics:
            stopic_id, sub_topic_name, topic_id, class_id, section_id = sub_topic_row
            create_node(tx, 'SubTopic', 'id', stopic_id, {'sub_topic_name': sub_topic_name})
            create_relationship(tx, 'Topic', topic_id, 'SubTopic', stopic_id, 'HAS_SUBTOPIC')        

    # Step 6: ID nodes link to Topic nodes
    with neo4j_session.begin_transaction() as tx:
        for id_row in ids:
            main_id, et_question_id, sl_question_id, subject_id, topic_id, course_id, class_id = id_row
            create_node(tx, 'ID', 'id', main_id, {'et_question_id': et_question_id, 'sl_question_id': sl_question_id})
            create_relationship(tx, 'Topic', topic_id, 'ID', main_id, 'HAS_ID')


    # Step 7: Question nodes link to id nodes and establish relationships (HAS_QUESTION, HAS_ANSWER, HAS_OPTION, HAS_SOLUTION)
    with neo4j_session.begin_transaction() as tx:
        for question_row in question_info:
            question_id, et_question_id, sl_question_id, question, answer = question_row

            # Ensure question_text is a string
            if isinstance(question, dict):
                question = json.dumps(question)

            # Clean the question_text
            clean_question = clean_html(question)

            # Find the corresponding main_id from the ids dataset for this question
            id_row = next((id_data for id_data in ids if id_data[1] == et_question_id or id_data[2] == sl_question_id), None)
            if id_row:
                main_id = id_row[0]  # Extract the corresponding main_id for this question

                # Create Question node with clean_question_text
                create_node(tx, 'Question', 'id', question_id, {
                    'question_text': question,
                    'clean_question_text': clean_question,
                    'et_question_id': et_question_id,
                    'sl_question_id': sl_question_id
                })

                # Create relationship between ID and Question using the correct main_id
                create_relationship(tx, 'ID', main_id, 'Question', question_id, 'HAS_QUESTION')

                # Clean the answer text (though it's unclear if answer needs cleaning)
                #clean_answer = clean_html(answer) ,{'clean_answer_text': clean_answer}

                # Create Answer node and link to Question
                #! todo: fix it
                answer_id = f"{question_id}_answer"
                create_node(tx, 'Answer', 'id', answer_id, {'answer_text': answer})
                create_relationship(tx, 'Question', question_id, 'Answer', answer_id, 'HAS_ANSWER')

                # Link Options to Questions
                for option_row in question_options:
                    option_id, option_question_id, _, _, option, option_index = option_row
                    if option_question_id == question_id:  # Link to the correct question
                        clean_option = clean_html(option)  # Clean the option text
                        create_node(tx, 'Option', 'id', option_id, {
                            'option_text': option,
                            'clean_option_text': clean_option,
                            'option_index': option_index
                        })
                        create_relationship(tx, 'Question', question_id, 'Option', option_id, f'HAS_OPTION')

                # Link Solution to Question
                for solution_row in questions_solutions:
                    solution_id, solution_question_id, _, _, solution = solution_row
                    if solution_question_id == question_id:  # Link to the correct question
                        clean_solution = clean_html(solution)  # Clean the solution text
                        create_node(tx, 'Solution', 'id', solution_id, {
                            'solution_text': solution,
                            'clean_solution_text': clean_solution
                        })
                        create_relationship(tx, 'Question', question_id, 'Solution', solution_id, 'HAS_SOLUTION')


    # Step 8: Section nodes and link to Class nodes
    with neo4j_session.begin_transaction() as tx:
        for section_row in sections:
            section_id, section_name, class_id = section_row
            create_node(tx, 'Section', 'id', section_id, {'section_name': section_name})
            create_relationship(tx, 'Class', class_id, 'Section', section_id, 'HAS_SECTION')

# Now you can call this function with your session and data
process_data_in_batches(neo4j_session, courses, classes, sections, subjects, chapters, topics, sub_topics, ids, question_info, question_options, questions_solutions)


# Close connections
mysql_cursor.close()
mysql_connection.close()
neo4j_session.close()
neo4j_driver.close()

# Total execution time calculator
end_time = time.time()
execution_time = end_time - start_time
execution_hours = execution_time // 3600
execution_minutes = (execution_time % 3600) // 60  # Minutes after excluding full hours
execution_seconds = execution_time % 60   # Seconds after excluding full hours and minutes

print(f"Code executed successfully in {execution_hours:.0f} hours, {execution_minutes:.0f} minutes, and {execution_seconds:.2f} seconds.")