
from django.urls import path, include
from . import views
from django.urls import path


urlpatterns = [
    path('', views.text_processor, name='text_processor'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/logout/', views.logout_view, name='logout'),  # Add this line
    path('accounts/', include('django.contrib.auth.urls')), 
    path('get_response/', views.get_response, name='get_response'),
    path('handle_satisfaction/', views.handle_satisfaction, name='handle_satisfaction'),

]