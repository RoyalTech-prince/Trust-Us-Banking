from django.urls import path
from .views import UserListCreateView, UserProfileView, FlexibleLoginView

urlpatterns = [
    # This provides the GET (list) and POST (add) endpoints
    path('users/', UserListCreateView.as_view(), name='user-list-create'),
    
    # This provides the profile/balance view
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    
    # This provides the new multi-modal login
    path('login/flexible/', FlexibleLoginView.as_view(), name='flexible-login'),
]