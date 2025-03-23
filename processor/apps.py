from django.apps import AppConfig


from django.apps import AppConfig

class TextProcessorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'text_processor'  # Replace with your actual app name

    def ready(self):
        """
        This method is called when Django starts.
        We'll use it to clear the chat history when the server starts.
        """
        # Import your clear_chat_history function
        from .chat_service import clear_chat_history
        
        # Clear chat history when server starts
        clear_chat_history()

class ProcessorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'processor'
