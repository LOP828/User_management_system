from django.urls import path

from apps.recommendation.views import (
    BatchCloseView,
    CandidateSearchView,
    CandidateSelectView,
    RecommendationBatchListCreateView,
)

urlpatterns = [
    path("", RecommendationBatchListCreateView.as_view(), name="recommendation-batch-list-create"),
    path("candidate-search/", CandidateSearchView.as_view(), name="recommendation-candidate-search"),
    path("candidates/<int:candidate_id>/select/", CandidateSelectView.as_view(), name="recommendation-candidate-select"),
    path("<int:batch_id>/close/", BatchCloseView.as_view(), name="recommendation-batch-close"),
]
