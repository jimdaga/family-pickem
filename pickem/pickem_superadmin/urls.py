from django.urls import path

from pickem_superadmin import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.overview, name='overview'),
]
