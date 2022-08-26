from django.urls import path, include
from django.contrib.auth.views import LogoutView
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('scores/', views.scores, name='scores'),
    path('accounts/', include('allauth.urls')),
    path('logout', LogoutView.as_view()),
]
