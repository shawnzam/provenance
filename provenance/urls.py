from django.contrib import admin
from django.urls import path
from core.views.graph import graph_view, graph_data, node_content

urlpatterns = [
    path("admin/", admin.site.urls),
    path("graph/", graph_view, name="graph"),
    path("graph/data/", graph_data, name="graph-data"),
    path("graph/node/<slug:slug>/", node_content, name="node-content"),
]
