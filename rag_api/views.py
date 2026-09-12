import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(request):
    """Liveness/readiness probe for the load balancer / ECS / App Runner."""
    return Response({"status": "ok"})


@api_view(["GET"])
def topics(request):
    """List the cancer-topic files the router can choose between."""
    try:
        return Response({"topics": services.list_topics()})
    except services.RagServiceError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Failed to list topics")
        return Response(
            {"error": "Internal error building the topic manifest."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def query(request):
    """
    Body: {"query": "What are the risk factors for lung cancer?", "top_k": 3}
    Response: {"query", "topic", "answer", "sources": [{section, source, page}]}
    """
    data = request.data or {}
    q = str(data.get("query", "")).strip()
    try:
        top_k = int(data.get("top_k", 3))
    except (TypeError, ValueError):
        return Response({"error": '"top_k" must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    top_k = max(1, min(top_k, 10))

    try:
        result = services.answer_query(q, top_k=top_k)
    except services.RagServiceError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Query failed for query=%r", q)
        return Response(
            {"error": "Internal error answering the query."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(result)
