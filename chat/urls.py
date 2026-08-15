from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("conversations/", views.ConversationListCreateView.as_view()),
    path("conversations/<uuid:pk>/", views.ConversationDetailView.as_view()),
    path("chat/", views.ChatStreamView.as_view()),
]
