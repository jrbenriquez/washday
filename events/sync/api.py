import hashlib
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import (
    ObjectDoesNotExist,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import IntegrityError
from django.http import Http404
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import shop_context
from events.models import HubCredential

from . import catalog, server


@dataclass
class HubPrincipal:
    is_authenticated: bool = True


class HubAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        if settings.APP_ROLE != "cloud":
            raise Http404()
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            raise AuthenticationFailed("A hub key is required.")
        credential = (
            HubCredential.unscoped.select_related("branch__shop")
            .filter(
                key_hash=hashlib.sha256(parts[1]).hexdigest(),
                state__in=["prepared", "active", "frozen"],
                shop__archived_at=None,
            )
            .first()
        )
        if not credential:
            raise AuthenticationFailed("Invalid hub key.")
        return HubPrincipal(), credential


class HubAPI(APIView):
    authentication_classes = [HubAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser]

    def handle_exception(self, error):
        if isinstance(
            error,
            (
                DjangoValidationError,
                ValueError,
                KeyError,
                TypeError,
                IntegrityError,
                ObjectDoesNotExist,
            ),
        ):
            return Response(
                {
                    "detail": " ".join(error.messages)
                    if isinstance(error, DjangoValidationError)
                    else "Invalid replication batch."
                },
                status=409,
            )
        return super().handle_exception(error)


class FrameSerializer(serializers.Serializer):
    protocol = serializers.IntegerField(min_value=1, max_value=1)
    epoch = serializers.IntegerField(min_value=0)
    job_seq = serializers.IntegerField(min_value=0)
    event = serializers.DictField()
    records = serializers.ListField(child=serializers.DictField())


class PushSerializer(serializers.Serializer):
    events = FrameSerializer(many=True, max_length=500)
    retire = serializers.BooleanField(default=False)
    last_seq = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class Push(HubAPI):
    def post(self, request):
        data = PushSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        with shop_context(request.auth.shop_id):
            return Response(
                server.push(
                    request.auth,
                    values["events"],
                    values["retire"],
                    values.get("last_seq"),
                )
            )


class Pull(HubAPI):
    def get(self, request):
        with shop_context(request.auth.shop_id):
            document = catalog.configuration(request.auth.branch)
            document["active"] = (
                request.auth.state == "active"
                and request.auth.branch.mode == "hub"
                and request.auth.epoch == request.auth.branch.writer_epoch
            )
            if request.query_params.get("since") == str(document["version"]):
                return Response(
                    {
                        "protocol": 1,
                        "unchanged": True,
                        "version": document["version"],
                        "branch_id": document["branch"]["id"],
                        "epoch": document["branch"]["writer_epoch"],
                        "active": document["active"],
                    }
                )
            return Response(document)


class Bootstrap(HubAPI):
    def get(self, request):
        with shop_context(request.auth.shop_id):
            return Response(catalog.bootstrap(request.auth))
