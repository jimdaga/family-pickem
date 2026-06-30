from django.urls import path, re_path, include
from django.contrib.auth.views import LogoutView
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('families/create/', views.create_family, name='create_family'),
    path('families/join/', views.join_family, name='join_family'),
    path('families/', views.family_picker, name='family_picker'),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/',
        views.family_pool_home,
        name='family_pool_home',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/invites/create/',
        views.create_family_invite,
        name='create_family_invite',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/picks/',
        views.tenant_submit_game_picks,
        name='family_pool_game_picks',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/picks/edit/',
        views.tenant_edit_game_pick,
        name='family_pool_edit_game_pick',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/scores/',
        views.tenant_scores,
        name='family_pool_scores',
    ),
    re_path(
        r'^families/(?P<family_slug>[-a-zA-Z0-9_]+)/pools/(?P<pool_slug>[-a-zA-Z0-9_]+)/scores/competition/(?P<competition>[0-9]+)/season/(?P<gameseason>[0-9]+)/week/(?P<week>[0-9]+)$',
        views.tenant_scores_long,
        name='family_pool_scores_long',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/standings/',
        views.tenant_standings,
        name='family_pool_standings',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/rules/',
        views.tenant_rules,
        name='family_pool_rules',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/players/',
        views.tenant_players,
        name='family_pool_players',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/user/<int:user_id>/',
        views.tenant_user_profile,
        name='family_pool_user_profile',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/message-board/create-post/',
        views.tenant_create_post,
        name='family_pool_create_post',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/message-board/create-comment/',
        views.tenant_create_comment,
        name='family_pool_create_comment',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/message-board/vote-post/',
        views.tenant_vote_post,
        name='family_pool_vote_post',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/message-board/vote-comment/',
        views.tenant_vote_comment,
        name='family_pool_vote_comment',
    ),
    path(
        'families/<slug:family_slug>/pools/<slug:pool_slug>/message-board/comments/<int:post_id>/',
        views.tenant_get_post_comments,
        name='family_pool_get_post_comments',
    ),
    path('invites/<str:invite_code>/', views.accept_invite_link, name='accept_invite_link'),
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
