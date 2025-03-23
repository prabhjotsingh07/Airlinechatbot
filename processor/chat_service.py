import ollama
import os
import mysql.connector  # Changed to MySQL connector
from .pdf_processor import (
    initialize_pdf_collection, 
    split_text, 
    get_embedding, 
    get_llama_response
)
from .email_system import send_support_email, get_chat_history

# Initialize the collection once at module level
global_collection = initialize_pdf_collection()

def log_chat_history(user_message, bot_message, source=""):
    """
    Log chat history to a file, preserving previous conversations
    until a new session is started.
    """
    # Create logs directory if it doesn't exist
    log_dir = "chat_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Use a consistent filename for each user
    filename = os.path.join(log_dir, "userhistory.txt")

    # Append to the file instead of overwriting
    with open(filename, "a") as f:
        f.write(f"USER: {user_message}\n")
        f.write(f"BOT: {bot_message}")
        if source and source != "Support System":
            f.write(f" (Source: {source})")
        f.write("\n\n")

# Add a new function to clear history at the start of a new session
def clear_chat_history():
    """
    Clear the chat history file when a new session starts.
    Call this function when initializing your application.
    """
    log_dir = "chat_logs"
    filename = os.path.join(log_dir, "userhistory.txt")
    
    if os.path.exists(filename):
        os.remove(filename)
        print("Chat history cleared for new session")

def initialize_collection():
    """Ensure the collection is initialized"""
    global global_collection
    if global_collection is None:
        print("Collection is None, reinitializing...")
        global_collection = initialize_pdf_collection()
    return global_collection

def process_text_query(user_text, output_language):
    """Process a text query and return results"""
    # Ensure collection is initialized
    collection = initialize_collection()
    if collection is None:
        return [{'query': user_text, 
                'response': 'Database initialization failed. Please contact an administrator.',
                'matches': [],
                'source_pdf': 'Error'}]

    client = ollama.Client()
    print("Ollama client initialized")

    query_chunks = split_text(user_text)
    results = []

    for i, query_text in enumerate(query_chunks, 1):
        print(f"Processing chunk {i} of {len(query_chunks)}")
        try:
            source_pdf, closest_matches = query_collection(query_text, client)
            context = " ".join(closest_matches)
            llama_response = get_llama_response(context, query_text, output_language, client)
            
            # Log the conversation
            log_chat_history(query_text, llama_response, source_pdf)
            
            # Create result entry
            results.append({
                'query': query_text,
                'response': llama_response,
                'matches': [(match, 0) for match in closest_matches],  # Adding dummy distances
                'source_pdf': source_pdf
            })
        except Exception as e:
            print(f"Error during query processing: {e}")
            # Add an error result
            error_response = f"Error processing this section: {str(e)}"
            log_chat_history(query_text, error_response, "Error")
            
            results.append({
                'query': query_text,
                'response': error_response,
                'matches': [],
                'source_pdf': "Error"
            })

    return results

def query_collection(query_text, client):
    """Query the collection and return results"""
    global global_collection
    
    # Ensure collection is initialized
    if global_collection is None:
        global_collection = initialize_pdf_collection()
        if global_collection is None:
            raise Exception("Failed to initialize database connection")
    
    query_embedding = get_embedding(query_text, client)
    
    query_results = global_collection.query(
        query_embeddings=[query_embedding],
        n_results=2,
        include=["documents", "distances", "metadatas"]
    )
    
    closest_matches = query_results["documents"][0]
    distances = query_results["distances"][0]
    metadatas = query_results["metadatas"][0]
    
    # Get source from first metadata
    source_pdf = metadatas[0].get("source", "Unknown source") if metadatas else "Unknown source"
    
    # Debug info
    for idx, (match_doc, distance, metadata) in enumerate(zip(closest_matches, distances, metadatas), start=1):
        print(f"\nClosest Match {idx}:")
        print(f"Matched Chunk: {match_doc}")
        print(f"Distance: {distance}")
        print(f"Source PDF: {source_pdf}")
    
    return source_pdf, closest_matches

def get_last_user_query():
    """Extract the last user query from history file"""
    try:
        filename = os.path.join("chat_logs", "userhistory.txt")
        if os.path.exists(filename):
            with open(filename, "r") as f:
                content = f.read()
                # Find the last USER entry
                user_entries = [line.strip() for line in content.split('\n') if line.strip().startswith("USER:")]
                if user_entries:
                    last_user_query = user_entries[-1][6:].strip()  # Remove "USER: " prefix
                    return last_user_query
    except Exception as e:
        print(f"Error reading user history: {e}")
    return None

def categorize_department(query, client):
    """Categorize which department should handle the query using direct department names"""
    
    # Define departments and their responsibilities with a clear instruction
    department_info = """
    Please determine which department should handle this customer query. Choose exactly one department from the list below:
    
    Baggage Services Department:
    - Questions regarding carry-on and checked baggage limits
    - Lost, delayed, or damaged baggage inquiries
    - Prohibited item clarification and excess baggage charges
    
    Customer Experience Department:
    - Booking changes, cancellations, and refund processing
    - Assistance with check-in procedures and upgrades
    - Loyalty program inquiries and point redemptions
    
    Flight Operations Department:
    - Flight cancellations, delays, and rebooking requests
    - Emergency guidelines and onboard safety instructions
    - Compensation for disrupted flights
    
    Special Services Department:
    - Wheelchair requests and assistance for passengers with disabilities
    - Medical equipment handling and medical condition accommodations
    - Pet travel arrangements and service animal guidelines
    
    Security and Compliance Department:
    - Passenger data protection and privacy concerns
    - Identity verification and security checks
    - Emergency contact support and crisis management
    
    Customer query: {query}
    
    Respond ONLY with the full name of the ONE most appropriate department.
    Do not include any explanation or additional text, just the department name.
    """
    
    prompt = department_info.format(query=query)
    
    # Send to llama for department categorization
    response = client.generate(
        model="llama_rag_model:latest",
        prompt=prompt
    )
    
    # Extract the department name from the response
    raw_response = response['response'].strip()
    print(f"Raw model response: '{raw_response}'")
    
    # List of valid department names for validation
    valid_departments = [
        "Baggage Services Department",
        "Customer Experience Department",
        "Flight Operations Department",
        "Special Services Department",
        "Security and Compliance Department"
    ]
    
    # Check if the response directly matches a department name
    department = None
    for valid_dept in valid_departments:
        if valid_dept.lower() in raw_response.lower():
            department = valid_dept
            print(f"Found department name in response: {department}")
            print(f"blalbalblalbmaelkgnaekbaekrnfaerfebergbae")
            break
    
    # Fallback: Direct keyword matching for common queries
    if not department:
        print("Department name not found in response. Using keyword matching...")
        query_lower = query.lower()
        
        # Baggage related keywords
        if any(word in query_lower for word in ["baggage", "luggage", "bag", "suitcase", "carry-on", "baggage limit", "weight"]):
            department = "Baggage Services Department"
            print("Keyword match: Routing to Baggage Services Department")
        
        # Customer Experience related keywords
        elif any(word in query_lower for word in ["booking", "reservation", "cancel", "refund", "check-in", "upgrade", "loyalty"]):
            department = "Customer Experience Department"
            print("Keyword match: Routing to Customer Experience Department")
        
        # Flight Operations related keywords
        elif any(word in query_lower for word in ["delay", "cancel flight", "cancelled flight", "compensation", "disruption"]):
            department = "Flight Operations Department"
            print("Keyword match: Routing to Flight Operations Department")
        
        # Special Services related keywords
        elif any(word in query_lower for word in ["wheelchair", "disability", "medical", "assistance", "pet", "animal"]):
            department = "Special Services Department"
            print("Keyword match: Routing to Special Services Department")
        
        # Security related keywords
        elif any(word in query_lower for word in ["privacy", "security", "identity", "emergency contact"]):
            department = "Security and Compliance Department"
            print("Keyword match: Routing to Security and Compliance Department")
        
        # Default to Customer Experience if no keywords match
        else:
            department = "Customer Experience Department"
            print("No keyword match found. Defaulting to Customer Experience Department")
    
    # Get the email ID for the department
    email = get_department_email(department)
    
    # Print department and email to terminal
    print(f"\nROUTING TICKET TO: {department} ({email})")
    
    return department, email

def get_department_email(department_name):
    """Get department email from MySQL database"""
    try:
        # Connect to the MySQL database
        conn = mysql.connector.connect(
            host="localhost",  # Replace with your MySQL host
            user="root",  # Replace with your MySQL username
            password="admin",  # Replace with your MySQL password
            database="airline_db"
        )
        cursor = conn.cursor()
        
        # Add debug prints
        print(f"Searching for email of: '{department_name}'")
        
        # Execute the query with exact match
        sql = "SELECT email FROM processor_departmentemail WHERE LOWER(department_name) = LOWER(%s)"
        print(f"Executing SQL: {sql} with parameter: {department_name}")
        
        cursor.execute(sql, (department_name,))
        result = cursor.fetchone()
        
        # Print the raw result
        print(f"Database query result: {result}")
        
        # If no exact match, try partial match
        if not result:
            sql = "SELECT email FROM processor_departmentemail WHERE LOWER(department_name) LIKE LOWER(%s)"
            search_term = f"%{department_name.split()[0]}%"
            cursor.execute(sql, (search_term,))
            result = cursor.fetchone()
            print(f"Partial match query with '{search_term}' result: {result}")
        
        # Close the database connection
        cursor.close()
        conn.close()
        
        if result:
            print(f"Found email for department '{department_name}': {result[0]}")
            return result[0]  # Return the email ID
        else:
            print(f"WARNING: No email found for department: '{department_name}'")
            return "support@airline.com"  # Default email if department not found
    except Exception as e:
        print(f"Database error: {e}")
        return "support@airline.com"  # Changed default error email

def handle_satisfaction_response(query, is_authenticated, user_data=None):
    """
    Handle YES/NO responses to satisfaction questions
    
    Args:
        query (str): User's query ('YES' or 'NO')
        is_authenticated (bool): Whether the user is authenticated
        user_data (dict, optional): User's contact information, includes:
            - email (str): User's email address
            - phone (str): User's phone number
    """
    client = ollama.Client()
    
    if query.strip().upper() == 'NO':
        # When user says NO, extract their previous query and categorize it
        last_user_query = get_last_user_query()
        
        if not user_data or not user_data.get('email'):
            # If user data not provided, ask for contact information
            response_message = "I understand you need additional assistance. Please provide your email address and phone number in the format: email: your@email.com, phone: 1234567890"
            
            # Log the conversation
            if is_authenticated:
                log_chat_history(query, response_message, "Support System")
            
            return {
                'response': response_message,
                'source': "Support System",
                'is_support_message': True,
                'needs_contact_info': True  # Flag that we need contact info
            }
        
        # We have user data, proceed with department routing and email
        if last_user_query:
            # Categorize department
            department, department_email = categorize_department(last_user_query, client)
            
            # Get the full chat history
            chat_history = get_chat_history()
            
            # Send email to department
            email_sent = send_support_email(
                department_email,
                user_data.get('email', 'Not provided'),
                user_data.get('phone', 'Not provided'),
                chat_history
            )
            clear_chat_history()
            
            if email_sent:
                response_message = f"Thank you. Your request has been forwarded to our {department}. They will contact you at {user_data.get('email')} within 12 hours."
            else:
                # If email sending fails, still acknowledge the request but note the technical issue
                response_message = f"Thank you. Your request has been recorded for our {department}. However, due to a technical issue, there may be a delay in response. They will aim to contact you at {user_data.get('email')} within 12 hours."
                # Log the email failure for internal tracking
                print(f"ALERT: Failed to send support email to {department_email} for user {user_data.get('email')}")
        else:
            response_message = "Thank you. Our support team will reach you within 12 hours."
        
        # Log the conversation
        if is_authenticated:
            log_chat_history(f"Contact information provided: {user_data}", response_message, "Support System")
        
        return {
            'response': response_message,
            'source': "Support System",
            'is_support_message': True
        }
    else:  # YES
        response_message = "Thank you for your feedback! Is there anything else I can help you with?"
        
        # Log the conversation
        if is_authenticated:
            log_chat_history(query, response_message, "Support System")
        
        return {
            'response': response_message,
            'source': "Support System"
        }

def process_chat_query(query, output_language, is_authenticated):
    """Process a chat query and return the response"""
    client = ollama.Client()
    
    # Query collection and get response
    try:
        source_pdf, closest_matches = query_collection(query, client)
        context = " ".join(closest_matches)
        llama_response = get_llama_response(context, query, output_language, client)
        
        # Log the conversation
        if is_authenticated:
            log_chat_history(query, llama_response, source_pdf)
        
        return {
            'response': llama_response,
            'source': source_pdf,
            'send_satisfaction_prompt': True  # Flag to send a separate satisfaction message
        }
    except Exception as e:
        raise Exception(f"Error processing query: {str(e)}")