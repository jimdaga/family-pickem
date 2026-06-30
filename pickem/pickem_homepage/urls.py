from django.urls import path, re_path, include
from django.contrib.auth.views import LogoutView
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('scores/', views.scores, name='scores'),
    path('standings/', views.standings, name='standings'),
    path('rules/', views.rules, name='rules'),
    path('accounts/', include('allauth.urls')),
    path('logout', LogoutView.as_view()),
    re_path(
        r'^scores/competition/(?P<competition>[0-9]+)/season/(?P<gameseason>[0-9]+)/week/(?P<week>[0-9]+)$', views.scores_long, name='scores_long'),
    path('picks/', views.submit_game_picks, name='game_picks'),
    path('picks/edit/', views.edit_game_pick, name='edit_game_pick'),
    path('profile/', views.profile, name='profile'),
    path('user/<int:user_id>/', views.user_profile, name='user_profile'),
    path('check-username/', views.check_username, name='check_username'),
    path('toggle-theme/', views.toggle_theme, name='toggle_theme'),
    
    # Message Board URLs
    path('message-board/create-post/', views.create_post, name='create_post'),
    path('message-board/create-comment/', views.create_comment, name='create_comment'),
    path('message-board/vote-post/', views.vote_post, name='vote_post'),
    path('message-board/vote-comment/', views.vote_comment, name='vote_comment'),
    path('message-board/comments/<int:post_id>/', views.get_post_comments, name='get_post_comments'),
    
    # Commissioner URLs
    path('commissioners/', views.commissioners, name='commissioners'),
    path('commissioners/set-week-winner/', views.set_week_winner, name='set_week_winner'),
    path('commissioners/manage-banner/', views.manage_banner, name='manage_banner'),
    path('commissioners/deactivate-banner/', views.deactivate_banner, name='deactivate_banner'),
    path('commissioners/submit-manual-pick/', views.submit_manual_pick, name='submit_manual_pick'),
    path('commissioners/get-user-picks/', views.get_user_picks, name='get_user_picks'),
]
