from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^near/$', views.near, name='near'),
    url(r'^near/(?P<event_id>\d+)/$', views.near, name='near'),
    url(r'^meeting/(?P<player_id>\d+)/$', views.meeting_create, name="meeting_create"),
    url(r'^meeting/(?P<player_id>\d+)/(?P<event_id>\d+)/$',
            views.meeting_create, name="meeting_create"),
    url(r'^meeting/(?P<player_id>\d+)/(?P<event_id>\d+)/captured/(?P<secret>\w+)/$',
            views.meeting_create, name="meeting_captured"),
    url(r'^meeting/(?P<player_id>\d+)/(?P<event_id>\d+)/qrclue/$',
            views.meeting_create, name="meeting_qrclue"),
    url(r'^set-pos/$', views.set_position, name="set_position"),
]
