# Importing necessary packages 
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError
import openai

# Query to retrieve the properties of all node labels in the Neo4j database using APOC meta data procedures
node_properties_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE NOT type = "RELATIONSHIP" AND elementType = "node"
WITH label AS nodeLabels, collect(property) AS properties
RETURN {labels: nodeLabels, properties: properties} AS output
"""

# Query to retrieve the properties of all relationship types in the Neo4j database using APOC meta data procedures 
rel_properties_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE NOT type = "RELATIONSHIP" AND elementType = "relationship"
WITH label AS relType, collect(property) AS properties
RETURN {type: relType, properties: properties} AS output
"""

# Query to retrieve the source and target node labels along with their relationship types in the Neo4j database using APOC meta data procedures 
rel_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE type = "RELATIONSHIP" AND elementType = "node"
RETURN {source: label, relationship: property, target: other} AS output
"""

# Defining the schema text function 
def schema_text(node_props, rel_props, rels):
    return f"""
  This is the schema representation of the Neo4j database.
  Node properties are the following:
  {node_props}
  Relationship properties are the following:
  {rel_props}
  Relationship point from source to target nodes
  {rels}
  Make sure to respect relationship types and directions
  """

# To run the query 
class Neo4jGPTQuery:

    # Connection to Neo4j graph database and OpenAI API 
    def __init__(self, url, user, password, openai_api_key):

        self.driver = GraphDatabase.driver(url, auth=(user, password))
        openai.api_key = openai_api_key

        # Veryifing in terminal that everything is properly connected 
        print('Everything is connected, yay!')

        # Constructing Schema 
        self.schema = self.generate_schema()

    # Closing the Neo4j connection once program has finished 
    def close(self):
        self.driver.close()
        print('Connection closed, bye!')

    # Generating the schema 
    def generate_schema(self):
        node_props = self.query_database(node_properties_query)
        rel_props = self.query_database(rel_properties_query)
        rels = self.query_database(rel_query)
        return schema_text(node_props, rel_props, rels)

    # Refreshing the schema 
    def refresh_schema(self):
        self.schema = self.generate_schema()

    # Getting system message inputted in ChatGPT 
    def get_system_message(self):
        return f"""
        Task: Generate Cypher queries to query a Neo4j graph database based on the provided schema definition.
        
        Instructions:
        Use only the provided relationship types and properties.
        Do not use any other relationship types or properties that are not provided.
        If you cannot generate a Cypher statement based on the provided schema, explain the reason to the user.
        
        Schema:
        {self.schema}

        Note: Do not include any explanations or apologies in your responses. Also, do not prompt the user to enter another response. 
        """
    
    # Opens a session, executes the Cypher query, retrieves the result values, includes the column headers 
    # and returns the formatted output 
    def query_database(self, neo4j_query, params={}):
        with self.driver.session() as session:
            result = session.run(neo4j_query, params)
            output = [r.values() for r in result]
            output.insert(0, result.keys())
            return output

    # Converts results of Neo4j query into a human-readable English format to input into ChatGPT
    def results_to_english(self, results):
        output = []
        for result in results[1:]:  # Skip the header
            output.append(", ".join(str(item) for item in result))
        return "\n".join(output)

    # Constructs a Cypher query using GPT-4 by sending a conversation history (including system message and user question)
    # and returns the response content 
    def construct_cypher(self, question, history=None):
        messages = [
            {"role": "system", "content": self.get_system_message()},
            {"role": "user", "content": question},
        ]

        if history:
            messages.extend(history)

        # Note usage of gpt-4 over gpt-4o here as 4o repeatedly gets lost in loops
        completions = openai.chat.completions.create(
            model="gpt-4",
            temperature=0.0,
            max_tokens=1000,
            messages=messages
        )
        return completions.choices[0].message.content
    
    # Uses ChatGPT model to generate a coherent English explanation of the associated query result
    def translate_results_to_english(self, question, results):
        messages = [
            {"role": "system", "content": "Translate the following Cypher query results into general English format."},
            {"role": "user", "content": f"Question: {question}"},
            {"role": "user", "content": f"Results: {self.results_to_english(results)}"},
        ]

        # Again, note usage of gpt-4 over gpt-4o due to looping issues 
        completions = openai.chat.completions.create(
        model="gpt-4",
        temperature=0.7,
        max_tokens=500,
        messages=messages
        )
        return completions.choices[0].message.content
    
    # Run definition that allows for three attemps before the program terminates itself 
    def run(self, question, history=None, retry_attempts=3):
        attempts = 0
        while attempts < retry_attempts:
            cypher = self.construct_cypher(question, history)
            print(cypher)
            try:
                results = self.query_database(cypher)
                english_results = self.translate_results_to_english(question, results)
                return english_results
            except CypherSyntaxError as e:
                attempts += 1
                if attempts >= retry_attempts:
                    return "Invalid Cypher syntax after multiple attempts."
                print(f"Attempt {attempts} failed. Retrying...")
                messages = [
                    {"role": "system", "content": self.get_system_message()},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": cypher},
                    {
                        "role": "user",
                        "content": f"This query returns an error: {str(e)}. Give me an improved query that works without any explanations or apologies."
                    }
                ]
                cypher = self.construct_cypher(question, messages)



# Entering credentials for Neo4j query and secret OpenAI API key 
gds_db = Neo4jGPTQuery(
    openai_api_key = "ENTER-KEY-HERE",

    url = "ENTER-NEO4J-URL-HERE",
    user = "ENTER-NEO4J-USERNAME-HERE",
    password = "ENTER-NEO4j-PASSWORD-HERE",
)

# Try-finally block ensures that the closing steps (closing of neo4j connection and ending print statement) 
# are always executed 
try: 
    # User question input 
    example = gds_db.run("""

    *ENTER-QUESTION-HERE*

    """
    
    # Example question #1: What is the node that has the most connections in the database?
    # Example question #2: Can you give me the top 5 most popular keywords in the database?
    )

    # Printing result in terminal for user to view 
    print ("\n")
    print('Hi, here is your answer: ')
    print(example)
    print("\n")
finally:
    # Closing of program 
    # Note that closing of the OpenAI API connection is not necessary (there is no method associated with closing anyways)
    gds_db.close()
    print('Program has finished running and you should see all results!\n')
