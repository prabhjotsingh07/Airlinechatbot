import getpass
import smtplib
import traceback
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Gmail SMTP settings
HOST = "smtp.gmail.com"
PORT = 587

# Email credentials - replace with your Gmail account
FROM_EMAIL = "prabhjotsingh0423@gmail.com"  # Replace with your Gmail address
PASSWORD = getpass.getpass("Enter your Gmail app password: ")  # You need to create an app password in your Google account

def send_support_email(department_email, user_email, user_phone, chat_history):
    """
    Send an email to the department's email address with the user's chat history
    and contact information using Gmail SMTP.
    """
    try:
        TO_EMAIL = department_email   # Keep your recipient
        
        # Create a proper MIME message
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        msg['Subject'] = "Mail sent using Python"
        
        body = f"""
        New support request received:
        
        User Contact Information:
        Email: {user_email}
        Phone: {user_phone}
        
        Chat History:
        {chat_history}
        """
        
        msg.attach(MIMEText(body, 'plain'))

        # Create SMTP session
        smtp = smtplib.SMTP(HOST, PORT)
        
        # Debug output
        smtp.set_debuglevel(1)
        
        # Identify ourselves to the server
        smtp.ehlo()
        print("[*] Connected to server")
        
        # Start TLS encryption
        smtp.starttls()
        print("[*] TLS encryption started")
        
        # Re-identify ourselves over TLS connection
        smtp.ehlo()
        
        # Login to server
        smtp.login(FROM_EMAIL, PASSWORD)
        print("[*] Logged in successfully")
        
        # Send email
        smtp.send_message(msg)
        print("[*] Email sent successfully!")
        
        # Close connection
        smtp.quit()
        print("[*] Connection closed")
        
        return True

        
    except Exception as e:
        print(f"Failed to send support email: {e}")
        traceback.print_exc()  # Print full stack trace for debugging
        return False

def get_chat_history():
    """
    Read the chat history from the log file.
    
    Returns:
        str: The content of the chat history or an error message
    """
    try:
        filepath = os.path.join("chat_logs", "userhistory.txt")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()
        return "No chat history available."
    except Exception as e:
        print(f"Error reading chat history: {e}")
        return f"Error retrieving chat history: {str(e)}"