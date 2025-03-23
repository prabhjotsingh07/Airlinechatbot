from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST  # Add this import
import json

from .chat_service import (
    process_text_query,
    handle_satisfaction_response,
    process_chat_query
)
from .forms import TextProcessorForm, UserCreationForm

@login_required
def text_processor(request):
    # Check if the user has sent "NO" in response to satisfaction question
    if request.method == 'POST' and request.POST.get('user_text', '').strip().upper() == 'NO':
        # Display support team message
        return render(request, 'text_processor/text_processor.html', {
            'form': TextProcessorForm(),
            'support_message': "Our support team will reach you within 12 hours"
        })
       
    print("Processing text request...")
    if request.method == 'POST':
        form = TextProcessorForm(request.POST)
        if form.is_valid():
            print("Form is valid, processing input...")
            user_text = form.cleaned_data['user_text']
            output_language = form.cleaned_data['output_language']
            
            results = process_text_query(user_text, output_language)
            
            return render(request, 'text_processor/text_processor.html', {
                'results': results,
                'original_query': user_text,
                'separate_satisfaction_prompt': True  # Flag to show the satisfaction prompt as a separate message
            })
    else:
        form = TextProcessorForm()
    
    return render(request, 'text_processor/text_processor.html', {'form': form})

def signup(request):
    print("Processing signup request...")
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            print("Form is valid, creating user...")
            user = form.save()
            login(request, user)
            print("User created and logged in successfully")
            return redirect('text_processor')
        else:
            print("Form validation failed")
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

def logout_view(request):
    print("Processing logout request...")
    logout(request)
    messages.success(request, 'Logged out successfully!')
    print("User logged out successfully")
    return redirect('login')

@csrf_exempt
def get_response(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('query')
            output_language = data.get('output_language', 'English')
            
            # Check if user is providing contact information (email/phone)
            if 'contact_info' in data:
                user_data = {
                    'email': data.get('contact_info', {}).get('email', ''),
                    'phone': data.get('contact_info', {}).get('phone', '')
                }
                
                # Process the NO response with the user's contact information
                response = handle_satisfaction_response(
                    "NO",  # The original query was NO
                    request.user.is_authenticated,
                    user_data
                )
                return JsonResponse(response)
            
            # Check if the user is responding with "YES" or "NO" to the satisfaction question
            if query.strip().upper() in ["YES", "NO"]:
                response = handle_satisfaction_response(
                    query, 
                    request.user.is_authenticated
                )
                return JsonResponse(response)
            
            if not query.strip():
                return JsonResponse({'error': 'Query cannot be empty'}, status=400)
            
            response = process_chat_query(
                query, 
                output_language, 
                request.user.is_authenticated
            )
            return JsonResponse(response)
            
        except Exception as e:
            print(f"Error in get_response: {e}")
            error_message = str(e)
            
            # Log the error if user is authenticated
            if 'query' in locals() and request.user.is_authenticated:
                from .chat_service import log_chat_history
                log_chat_history(query, f"Error: {error_message}")
            
            return JsonResponse({
                'error': error_message,
                'send_satisfaction_prompt': False  # Don't send satisfaction prompt on error
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@require_POST
def handle_satisfaction(request):
    """Handle satisfaction responses and contact information"""
    try:
        # Parse the JSON data
        data = json.loads(request.body)
        query = data.get('query', '')
        user_data = data.get('user_data', None)
        
        # Get user authentication status
        is_authenticated = request.user.is_authenticated
        
        # Process the satisfaction response
        result = handle_satisfaction_response(query, is_authenticated, user_data)
        
        # Return the response
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'response': f"Error processing request: {str(e)}",
            'source': "Error"
        })  