from django.urls import path

from pickem_superadmin import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('users/', views.users, name='users'),
    path('users/<int:user_id>/block/', views.user_block, name='user_block'),
    path('users/<int:user_id>/unblock/', views.user_unblock, name='user_unblock'),
    path('users/<int:user_id>/update/', views.user_update, name='user_update'),
    path('pools/', views.pools, name='pools'),
    path('pools/save/', views.pools_save, name='pools_save'),
    path('families/', views.families, name='families'),
    path('families/save/', views.families_save, name='families_save'),
    path('teams/', views.teams, name='teams'),
    path('teams/save/', views.teams_save, name='teams_save'),
]
