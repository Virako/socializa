from rest_framework.decorators import api_view, renderer_classes
from rest_framework import response, schemas
from rest_framework_swagger.renderers import OpenAPIRenderer, SwaggerUIRenderer

from django.shortcuts import render
from django.shortcuts import redirect

from social.apps.django_app.utils import load_backend, load_strategy
from social.utils import requests
from rest_framework import exceptions
from rest_framework.authtoken.models import Token


@api_view()
@renderer_classes([OpenAPIRenderer, SwaggerUIRenderer])
def schema_view(request):
    generator = schemas.SchemaGenerator(title='Socializa API')
    return response.Response(generator.get_schema(request=request))


def oauth2callback(request):
    if not request.GET:
        return render(request, 'oauth2callback.html')
    else:
        token = request.GET['access_token']
        state = request.GET['state']
        backend = 'google-oauth2'

        strategy = load_strategy(request=request)

        backend = load_backend(strategy, backend, '')

        try:
            user = backend.do_auth(access_token=token)
        except requests.HTTPError as e:
            msg = e.response.text
            raise exceptions.AuthenticationFailed(msg)

        if not user:
            msg = 'Bad credentials.'
            raise exceptions.AuthenticationFailed(msg)

        token, created = Token.objects.get_or_create(user=user)

        return redirect(state + '?email=' + user.email + '&token=' + token.key)
