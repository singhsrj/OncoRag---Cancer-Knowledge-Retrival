from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("topics/", views.topics, name="topics"),
    path("query/", views.query, name="query"),
]
