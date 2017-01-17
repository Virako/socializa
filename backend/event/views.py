from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from clue.views import attachClue
from clue.views import detachClue
from .models import Event
from .models import Membership
from .serializers import EventSerializer


def create_member(player, event):
    member = None
    if event.max_players != 0 and event.players.count() >= event.max_players:
        msg = "Maximum number of player in this event"
        st = status.HTTP_400_BAD_REQUEST
    else:
        member, created = Membership.objects.get_or_create(player=player, event=event)
        if not created:
            msg = "This player already is join at this event"
            st = status.HTTP_400_BAD_REQUEST
        else:
            if member.event.price == 0:
                member.status = 'payed'
                member.save()
            msg = "Joined correctly"
            st = status.HTTP_201_CREATED
    return member, msg, st


class JoinEvent(APIView):

    def post(self, request, event_id):
        if request.user.is_anonymous():
            return Response("Anonymous user", status=status.HTTP_401_UNAUTHORIZED)
        player = request.user.player
        try:
            event = Event.objects.get(pk=event_id)
        except:
            return Response("Event not exist", status=status.HTTP_400_BAD_REQUEST)
        member, msg, st = create_member(player, event)
        attachClue(player, event.game)
        return Response(msg, status=st)


class UnjoinEvent(APIView):

    def delete(self, request, event_id):
        if request.user.is_anonymous():
            return Response("Anonymous user", status=status.HTTP_401_UNAUTHORIZED)
        player = request.user.player
        try:
            event = Event.objects.get(pk=event_id)
        except ObjectDoesNotExist:
            return Response("Event not exist", status=status.HTTP_400_BAD_REQUEST)
        try:
            Membership.objects.get(player=player, event=event).delete()
        except ObjectDoesNotExist:
            return Response("You not join in this event.", status=status.HTTP_400_BAD_REQUEST)
        detachClue(player, event.game)
        return Response("Unjoined correctly.", status=status.HTTP_200_OK)


class MyEvents(APIView):

    def get(self, request):
        if request.user.is_anonymous():
            return Response("Anonymous user", status=status.HTTP_401_UNAUTHORIZED)
        events = request.user.player.event_set.all()
        serializer = EventSerializer(events, many=True)
        data = serializer.data
        return Response(data)


class AllEvents(APIView):

    def get(self, request):
        """ Get all new event from now to infinite. """
        if request.user.is_anonymous():
            return Response("Anonymous user", status=status.HTTP_401_UNAUTHORIZED)
        events = Event.objects.filter(end_date__gt=timezone.now())
        events = events.order_by('-pk')
        serializer = EventSerializer(events, many=True, context={'player': request.user.player})
        data = serializer.data
        return Response(data)


join_event = JoinEvent.as_view()
unjoin_event = UnjoinEvent.as_view()
my_events = MyEvents.as_view()
all_events = AllEvents.as_view()
