from django.urls import path

from apps.matchcard.views import (
    MatchCardAdvanceStageView,
    MatchCardDetailView,
    MatchCardEndView,
    MatchCardListCreateView,
    MatchCardSetRiskView,
)

urlpatterns = [
    path("", MatchCardListCreateView.as_view(), name="match-card-list-create"),
    path("<int:pk>/", MatchCardDetailView.as_view(), name="match-card-detail"),
    path("<int:pk>/advance-stage/", MatchCardAdvanceStageView.as_view(), name="match-card-advance-stage"),
    path("<int:pk>/set-risk/", MatchCardSetRiskView.as_view(), name="match-card-set-risk"),
    path("<int:pk>/end/", MatchCardEndView.as_view(), name="match-card-end"),
]
