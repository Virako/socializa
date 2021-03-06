import re
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from time import sleep

from event.utils import manage_ais
from player.models import Player
from player.test_client import JClient
from .models import Event
from .models import Membership
from .models import PlayingEvent


anonymous_user = {'detail': 'Authentication credentials were not provided.'}


class EventTestCase(APITestCase):
    """
    Inside event.json fixture have:
    - 3 event, 3 game and 17 challenges:
      - general event (pk=1) with general game (pk=1) with general challenge (pk=1). Max_player = 0
      - event 2 (pk=2) with game 2 (pk=2) with challenges (pk=[2,3,4,5,6,7,8]). Event have solution,
            and Challenges no have solutions. Max_player = 3
      - event 3 (pk=3) with game 3 (pk=3) with general challenge (pk=[9,10,11,12,13]). Event and
            Challenges have solution. Max_player = 10
    - membership:
        player 3 ('test3') in event 3
        player 5 ('test5') in event 1 and 3
    """
    fixtures = ['player-test.json', 'event.json']

    def setUp(self):
        self.client = JClient()
        event_pk = 2
        self.event = Event.objects.get(pk=event_pk)

    def tearDown(self):
        self.client = None
        self.event.players.clear()

    def authenticate(self, username, pwd='qweqweqwe'):
        response = self.client.authenticate(username, pwd)
        self.assertEqual(response.status_code, 200)

    @classmethod
    def get_username_by_player(cls, pk):
        return Player.objects.get(pk=pk).user.username

    def test_join_an_event_unauthorized(self):
        event_pk = 2
        response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 401)

    def test_join_an_event_not_exist(self):
        self.authenticate('test1')
        response = self.client.post('/api/event/join/{0}/'.format(999), {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'detail': "Event doesn't exists"})

    def test_join_an_event(self):
        event_pk = 2
        response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 401)
        self.authenticate('test1')
        response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 201)

    def test_join_an_event_repeat(self):
        event_pk = 2
        self.authenticate('test1')
        response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 201)
        response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'This player already is join at this event')

    def test_join_an_event_max(self):
        event_pk = 2
        repeat = 1
        max_player_ev2 = Event.objects.get(pk=2).max_players
        while repeat <= max_player_ev2:
            username = 'test{0}'.format(repeat)
            self.authenticate(username)
            response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
            self.assertEqual(response.status_code, 201)
            repeat += 1
        response = self.client.post('/api/event/join/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Maximum number of player in this event')

    def test_unjoin_event_anonymous(self):
        event_pk = 3
        response = self.client.delete('/api/event/unjoin/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), anonymous_user)

    def test_unjoin_event(self):
        event_pk = 3
        self.authenticate('test3')
        response = self.client.delete('/api/event/unjoin/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 200)

    def test_unjoin_event_no_join(self):
        event_pk = 3
        self.authenticate('test1')
        response = self.client.delete('/api/event/unjoin/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), "You aren't joined to this event.")

    def test_unjoin_event_no_exist(self):
        event_pk = 5
        self.authenticate('test1')
        response = self.client.delete('/api/event/unjoin/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'detail': "Event doesn't exists"})

    def test_get_my_events_unauth(self):
        response = self.client.get('/api/event/my-events/', {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), anonymous_user)

    def test_get_my_events(self):
        player5_joined_event = Player.objects.get(pk=5).membership_set.count()
        self.authenticate('test5')
        response = self.client.get('/api/event/my-events/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), player5_joined_event)

    def test_get_all_events_unauth(self):
        response = self.client.get('/api/event/all/', {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), anonymous_user)

    @override_settings(
        task_eager_propagates=True,
        task_always_eager=True,
        broker_url='memory://',
        backend='memory'
    )
    def test_get_all_events(self):
        self.authenticate('test5')
        response = self.client.get('/api/event/all/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)
        # Edit an event for tomorrow
        self.event.start_date = timezone.now() + timezone.timedelta(days=1)
        self.event.end_date = timezone.now() + timezone.timedelta(days=2)
        self.event.save()
        response = self.client.get('/api/event/all/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    @override_settings(
        task_eager_propagates=True,
        task_always_eager=True,
        broker_url='memory://',
        backend='memory'
    )
    def test_get_all_events_paginated(self):
        self.authenticate('test5')
        response = self.client.get('/api/event/all/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

        # Adding a lot of events
        evs = []
        for i in range(35):
            ev = Event(name="test-%s" % i, game=self.event.game)
            ev.start_date = timezone.now() + timezone.timedelta(days=1 + i)
            ev.end_date = timezone.now() + timezone.timedelta(days=2 + i)
            ev.save()
            evs.append(ev.pk)

        response = self.client.get('/api/event/all/?page=a', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 20)
        self.assertEqual(response.json()[0]['name'], 'test-34')

        response = self.client.get('/api/event/all/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 20)
        self.assertEqual(response.json()[0]['name'], 'test-34')

        response = self.client.get('/api/event/all/?page=1', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 15)
        self.assertEqual(response.json()[0]['name'], 'test-14')

        response = self.client.get('/api/event/all/?q=test-0', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['name'], 'test-0')

        response = self.client.get('/api/event/all/?q=test-38', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    @override_settings(
        task_eager_propagates=True,
        task_always_eager=True,
        broker_url='memory://',
        backend='memory'
    )
    def test_get_events_filtered(self):
        self.authenticate('test5')
        response = self.client.get('/api/event/all/', {'filter': 'mine'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

        response = self.client.get('/api/event/all/?q=test-38', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

        p = Player.objects.get(pk='5')
        # Adding a lot of events
        evs = []
        from django.db import transaction
        for i in range(35):
            ev = Event(name="test-%s" % i, game=self.event.game)
            ev.start_date = timezone.now() + timezone.timedelta(days=1+i)
            ev.end_date = timezone.now() + timezone.timedelta(days=2+i)
            ev.save()
            evs.append(ev)

        with transaction.atomic():
            for ev in evs[0:5]:
                ev.owners.add(p.user)

        with transaction.atomic():
            for ev in evs[5:11]:
                m = Membership(event=ev, player=p)
                m.save()

        response = self.client.get('/api/event/all/', {'filter': 'admin'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 5)

        response = self.client.get('/api/event/all/', {'filter': 'mine'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 6)

    @override_settings(
        task_eager_propagates=True,
        task_always_eager=True,
        broker_url='memory://',
        backend='memory'
    )
    def test_get_event_detail(self):
        self.authenticate('test5')
        # Edit an event for tomorrow
        self.event.start_date = timezone.now() + timezone.timedelta(days=1)
        self.event.end_date = timezone.now() + timezone.timedelta(days=2)
        self.event.save()

        pk = self.event.pk
        response = self.client.get('/api/event/%s/' % pk, {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['pk'], pk)

        # event that doesn't exist
        response = self.client.get('/api/event/523/', {})
        self.assertEqual(response.status_code, 403)

    def test_solve_event_unauthorized(self):
        """ User try solve event with event_id unauthorized. """
        event_id = 1
        player = 3
        data = {'solution': 'solution'}
        self.authenticate(self.get_username_by_player(player))
        response = self.client.post('/api/event/solve/{0}/'.format(event_id), data)
        self.assertEqual(response.status_code, 403)

    def test_solve_event_no_data(self):
        """ Event's solution is incorrect. """
        event_id = 3
        player = 3
        data = {}
        self.authenticate(self.get_username_by_player(player))
        response = self.client.post('/api/event/solve/{0}/'.format(event_id), data)
        self.assertEqual(response.status_code, 400)

    def test_solve_event_empty(self):
        """ Event's solution is incorrect. """
        event_id = 3
        player = 3
        data = {'solution': ''}
        self.authenticate(self.get_username_by_player(player))
        response = self.client.post('/api/event/solve/{0}/'.format(event_id), data)
        self.assertEqual(response.status_code, 400)

    def test_solve_event_incorrect(self):
        """ Event's solution is incorrect. """
        event_id = 3
        player = 3
        data = {'solution': 'solution'}
        self.authenticate(self.get_username_by_player(player))
        response = self.client.post('/api/event/solve/{0}/'.format(event_id), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': "incorrect"})

    def test_solve_event_correct(self):
        """ Event's solution is correct. """
        event_id = 3
        player = 3
        event = Event.objects.get(pk=event_id)
        solution = event.game.solution
        data = {'solution': solution}
        self.authenticate(self.get_username_by_player(player))
        response = self.client.post('/api/event/solve/{0}/'.format(event_id), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': "correct"})
        player = Player.objects.get(pk=player)
        membership_status = Membership.objects.filter(event=event, player=player).first().status
        self.assertEqual(membership_status, 'solved')


class PlayerEventTestCase(APITestCase):
    """
    Inside event.json fixture have:
    - 3 event, 3 game and 17 challenges:
      - general event (pk=1) with general game (pk=1) with general challenge (pk=1). Max_player = 0
      - event 2 (pk=2) with game 2 (pk=2) with challenges (pk=[2,3,4,5,6,7,8]). Event have solution,
            and Challenges no have solutions. Max_player = 3
      - event 3 (pk=3) with game 3 (pk=3) with general challenge (pk=[9,10,11,12,13]). Event and
            Challenges have solution. Max_player = 10
    - membership:
        player 3 ('test3') in event 3
        player 5 ('test5') in event 1 and 3
        all player are in event 4: 4 inside and 1 outside place
        In event 3:
            player 1 is near to player 2 and player 3
            player 1 is near to player 5 but player 5 is outside place
            player 1 is far player 4
    """
    fixtures = ['player-test.json', 'event.json']

    def setUp(self):
        self.client = JClient()

    def tearDown(self):
        self.client = None

    def authenticate(self, username, pwd='qweqweqwe'):
        response = self.client.authenticate(username, pwd)
        self.assertEqual(response.status_code, 200)

    def test_players_near_in_event2(self):
        event_pk = 4
        near_player4_ev4 = 0
        self.authenticate('test4')
        response = self.client.get('/api/player/near/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 200)
        players = [d for d in response.json() if not d.get('ptype') is 'ai']
        self.assertEqual(len(players), near_player4_ev4)

    def test_players_near_in_event3(self):
        event_pk = 4
        self.authenticate('test5')
        response = self.client.get('/api/player/near/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Your player is outside of place.')

    def test_players_near_in_unauth_event(self):
        event_pk = 2
        self.authenticate('test5')
        response = self.client.get('/api/player/near/{0}/'.format(event_pk), {})
        self.assertEqual(response.status_code, 401)

    def test_players_meeting_in_event(self):
        event_pk = 4
        player_pk = 2
        self.authenticate('test1')
        response = self.client.post('/api/player/meeting/{0}/{1}/'.format(player_pk, event_pk), {})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {'status': 'step1'})

    def test_players_meeting_in_event_unauth_event(self):
        event_pk = 2
        player_pk = 3
        self.authenticate('test5')
        response = self.client.post('/api/player/meeting/{0}/{1}/'.format(player_pk, event_pk), {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), 'Unauthorized event')

    def test_players_meeting_in_event_with_player2_outside_event(self):
        event_pk = 1
        player_pk = 3
        self.authenticate('test5')
        response = self.client.post('/api/player/meeting/{0}/{1}/'.format(player_pk, event_pk), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Other player not join at this event')

    def test_players_meeting_in_event_with_himself(self):
        event_pk = 3
        player_pk = 5
        self.authenticate('test5')
        response = self.client.post('/api/player/meeting/{0}/{1}/'.format(player_pk, event_pk), {})
        self.assertEqual(response.json(), 'narcissistic: you cannot connect with yourself')
        self.assertEqual(response.status_code, 400)


class PlayingEventTestCase(APITestCase):
    """
    Two events and general events
    player 1 and 2 in None event
    player 3 and 4 in event 1
    player 5 in event 2

    Players in the same current event, can be see it.
    Players in the different current event, can't be see it.
    """
    fixtures = ['player-test.json', 'event.json', 'playing_event.json']

    def setUp(self):
        self.event1 = 1
        self.event2 = 2
        self.client = JClient()

    def tearDown(self):
        self.client = None

    def authenticate(self, username, pwd='qweqweqwe'):
        response = self.client.authenticate(username, pwd)
        self.assertEqual(response.status_code, 200)

    def test_players_playing_event_with_event_none(self):
        """
        Player 1 and 2 in event None: visible
        Player 1 and 3 in event None: no visible
        """
        username = 'test2'
        self.authenticate('test1')
        response = self.client.get('/api/player/near/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0].get('username'), username)

    def test_players_playing_event_with_event_id(self):
        """
        Player 3 and 4 in event 1: visible. Player 3 is far to player 4
        Player 3 and 5 in event 1: no visible
        """
        event = Event.objects.get(pk=self.event1)
        prev_vd = event.vision_distance
        event.vision_distance = 9999
        event.save()

        self.authenticate('test3')
        response = self.client.get('/api/player/near/{0}/'.format(self.event1), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        username = 'test4'
        self.assertEqual(response.json()[0].get('username'), username)

        event.vision_distance = prev_vd
        event.save()

    def test_playing_event_not_exits(self):
        self.authenticate('test1')
        response = self.client.post('/api/event/current/{0}/'.format(self.event1), {})
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/api/event/current/', {})
        self.assertEqual(response.status_code, 200)

        self.authenticate('test2')
        response = self.client.post('/api/event/current/1/', {})
        self.assertEqual(response.status_code, 201)

    def test_playing_event_exits(self):
        self.authenticate('test5')
        response = self.client.post('/api/event/current/{0}/'.format(self.event1), {})
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/api/event/current/', {})
        self.assertEqual(response.status_code, 200)


class EventTasksTestCase(APITestCase):
    """ Test tasks for check taht work well """
    fixtures = ['player-test.json', 'event.json']

    def setUp(self):
        self.client = JClient()
        self.event2 = Event.objects.get(pk=2)
        self.event2.start_date = timezone.now() - timezone.timedelta(hours=2)
        self.event2.end_date = timezone.now() + timezone.timedelta(hours=2)
        self.event3 = Event.objects.get(pk=3)
        self.event3.start_date = timezone.now() - timezone.timedelta(hours=2)
        self.event3.end_date = timezone.now() + timezone.timedelta(hours=2)
        self.ini_players = Player.objects.count()

    def authenticate(self, username, pwd='qweqweqwe'):
        response = self.client.authenticate(username, pwd)
        self.assertEqual(response.status_code, 200)

    def get_member_players(self, event):
        return Membership.objects.filter(event=event).count()

    def get_playing_players(self, event):
        return PlayingEvent.objects.filter(event=event).count()

    def get_need_players(self, event):
        return event.game.challenges.count() - event.players.count()

    def test_manage_ais_not_change(self):
        """ test manage_ais fails:
            * event is None
            * event have date out of current date
            * event haven't place
        """
        event1 = Event.objects.get(pk=1)
        ini_member_players = self.get_member_players(event1)
        ini_playing_players = self.get_playing_players(event1)

        manage_ais(None)
        manage_ais(event1)
        event1.start_date = timezone.now() - timezone.timedelta(hours=2)
        event1.end_date = timezone.now() + timezone.timedelta(hours=2)
        manage_ais(event1)

        end_players = Player.objects.count()
        end_member_players = self.get_member_players(event1)
        end_playing_players = self.get_playing_players(event1)

        self.assertEqual(self.ini_players, end_players)
        self.assertEqual(ini_member_players, end_member_players)
        self.assertEqual(ini_playing_players, end_playing_players)

    def test_manage_ais_fill_event(self):
        """ Check that add players and these are add like member and like playing in event """
        ini_member_players = self.get_member_players(self.event2)
        ini_playing_players = self.get_playing_players(self.event2)
        need_players = self.get_need_players(self.event2)

        manage_ais(self.event2)

        end_players = Player.objects.count()
        end_member_players = self.get_member_players(self.event2)
        end_playing_players = self.get_playing_players(self.event2)

        self.assertEqual(self.ini_players + need_players, end_players)
        self.assertEqual(ini_member_players + need_players, end_member_players)
        self.assertEqual(ini_playing_players + need_players, end_playing_players)

    def test_join_player_sustitute_ia(self):
        """ Fill event with ai players, and join new player that sustitute onw ai. """
        available = self.event3.max_players - self.event3.players.count()
        manage_ais(self.event3, amount=available)
        self.assertEqual(self.event3.max_players, self.event3.players.count())

        self.authenticate('test1')
        response = self.client.post('/api/event/join/{0}/'.format(self.event3.pk), {})
        self.assertEqual(response.status_code, 201)


    def test_manage_ais_amount(self):
        """ Check that add players and these are add like member and like playing in event.
            And You can't create more players than max_players in event.
        """
        ini_member_players = self.get_member_players(self.event2)
        ini_playing_players = self.get_playing_players(self.event2)
        need_players = 2

        manage_ais(self.event2, amount=need_players)

        end_players = Player.objects.count()
        end_member_players = self.get_member_players(self.event2)
        end_playing_players = self.get_playing_players(self.event2)

        self.assertEqual(self.ini_players + need_players, end_players)
        self.assertEqual(ini_member_players + need_players, end_member_players)
        self.assertEqual(ini_playing_players + need_players, end_playing_players)

    def test_manage_ais_amount_max_players(self):
        """ Check that add players and these are add like member and like playing in event """
        ini_member_players = self.get_member_players(self.event2)
        ini_playing_players = self.get_playing_players(self.event2)
        need_players = 20

        available = self.event2.max_players - self.event2.players.count()
        players_are_created = need_players if available >= need_players else available

        manage_ais(self.event2, amount=need_players)

        end_players = Player.objects.count()
        end_member_players = self.get_member_players(self.event2)
        end_playing_players = self.get_playing_players(self.event2)

        self.assertEqual(self.ini_players + players_are_created, end_players)
        self.assertEqual(ini_member_players + players_are_created, end_member_players)
        self.assertEqual(ini_playing_players + players_are_created, end_playing_players)


class EventAdminTestCase(APITestCase):
    """ Test event admin views """
    fixtures = ['player-test.json', 'event.json']

    def authenticate(self, username, pwd='qweqweqwe'):
        response = self.client.authenticate(username, pwd)
        self.assertEqual(response.status_code, 200)

    def setUp(self):
        self.event2 = Event.objects.get(pk=2)
        self.event2.start_date = timezone.now() - timezone.timedelta(hours=2)
        self.event2.end_date = timezone.now() + timezone.timedelta(hours=2)
        self.ini_players = Player.objects.count()
        self.client = JClient()

        p = Player.objects.get(pk=5)
        self.event2.owners.add(p.user)

    def test_admin_event_challenges(self):
        response = self.client.get('/api/event/admin/challenges/1/', {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), anonymous_user)

        self.authenticate('test4')
        response = self.client.get('/api/event/admin/challenges/2/', {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'detail': 'Non admin user'})

        self.authenticate('test5')
        response = self.client.get('/api/event/admin/challenges/2/', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), self.event2.game.challenges.count())

    def test_admin_update(self):
        options = {
            'vision_distance': 523,
            'meeting_distance': 32,
        }

        response = self.client.post('/api/event/admin/1/', options)
        self.assertEqual(response.status_code, 401)

        self.authenticate('test4')
        response = self.client.post('/api/event/admin/2/', options)
        self.assertEqual(response.status_code, 403)

        self.authenticate('test5')
        response = self.client.post('/api/event/admin/2/', options)
        self.assertEqual(response.status_code, 200)

        ev = Event.objects.get(pk=2)
        self.assertEqual(ev.vision_distance, 523)
        self.assertEqual(ev.meeting_distance, 32)


class EventCeleryTestCase(APITestCase):
    """ Test event celery tasks """
    fixtures = ['player-test.json', 'event.json', 'celery-event.json']

    def setUp(self):
        self.client = JClient()

    @classmethod
    def get_event(cls, pk):
        return Event.objects.get(pk=pk)

    @override_settings(
        task_eager_propagates=True,
        task_always_eager=True,
        broker_url='memory://',
        backend='memory'
    )
    def test_exec_task_manage_ias(self):
        # When load fixture task, if datetime is less than now, not generate task
        event = self.get_event(10)
        self.assertFalse(event.task_id)

        # Update start_date and end_date. When save, create the task, that run in 2 seconds
        ini_players = event.players.count()
        event.start_date = timezone.now() + timezone.timedelta(seconds=2)
        event.end_date = timezone.now() + timezone.timedelta(days=1)
        event.save()

        # Check create task
        event = self.get_event(10)
        self.assertTrue(event.task_id)

        # Wait more than 2 seconds for check if manage_ias exec
        sleep(3)
        event = Event.objects.get(pk=10)
        end_players = event.players.count()
        self.assertEqual(ini_players + event.max_players, end_players)


class EventSolveDropdownTestCase(APITestCase):
    """ New event with descriptions for solve with dropdown. """
    fixtures = ['event-solve-dropdown.json']

    GAME_PK = 1

    def setUp(self):
        self.client = JClient()

    def tearDown(self):
        self.client = None

    def authenticate(self, username, pwd='qweqweqwe'):
        response = self.client.authenticate(username, pwd)
        self.assertEqual(response.status_code, 200)

    def test_convert_challengue_description(self):
        self.authenticate('username@test.com')
        response = self.client.get('/api/clue/my-clues/{0}/'.format(self.GAME_PK), {})
        self.assertEqual(response.status_code, 200)
        qregex = re.compile("#\[[\d]+\]\[([^#]*)\]")
        for res in response.json():
            desc = res.get('challenge').get('desc')
            self.assertFalse(qregex.search(desc))

    def test_convert_game_description(self):
        self.authenticate('username@test.com')
        response = self.client.get('/api/event/my-events/', {})
        self.assertEqual(response.status_code, 200)
        qregex = re.compile("#\[[\d]+\]\[(?:option|text)\]\[([^#]*)\]")
        for res in response.json():
            desc = res.get('game').get('desc')
            self.assertFalse(qregex.search(desc))

    def test_get_possible_solutions(self):
        self.authenticate('username@test.com')
        response = self.client.get('/api/event/{}/'.format(self.GAME_PK), {})
        self.assertEqual(response.status_code, 200)
        solution = response.json().get('solution')
        self.assertTrue(isinstance(solution, list))
        self.assertTrue(isinstance(solution[0], dict))
        self.assertEqual(sorted(solution[0].keys()), ["answers", "question", "type"])
