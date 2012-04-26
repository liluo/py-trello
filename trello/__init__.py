from httplib2 import Http
from urllib import urlencode
import exceptions
import json
import oauth2 as oauth
import os
import random
import time
import urlparse

class ResourceUnavailable(Exception):
    """Exception representing a failed request to a resource"""

    def __init__(self, msg):
        Exception.__init__(self)
        self._msg = msg

    def __str__(self):
        print "Resource unavailable: %s" % (self._msg, )

class TrelloClient(object):
    """ Base class for Trello API access """

    def __init__(self, api_key, token, api_secret = None, token_secret = None):
        """
        Constructor

        :api_key: API key generated at https://trello.com/1/appKey/generate
        :oauth_token: OAuth token generated by the user
        """

        if api_key and api_secret and token and token_secret:
            # oauth
            self.oauth_consumer = oauth.Consumer(key = api_key, secret = api_secret)
            self.oauth_token = oauth.Token(key = token, secret = token_secret)
            self.client = oauth.Client(self.oauth_consumer, self.oauth_token)

        elif api_key and token:
            self.client = Http()

        self.api_key = api_key
        self.auth_token = token

    def logout(self):
        """Log out of Trello. This method is idempotent."""

        # TODO: refactor
        pass
        #if not self._cookie:
            #return

        #headers = {'Cookie': self._cookie, 'Accept': 'application/json'}
        #response, content = self.client.request(
                #'https://trello.com/logout',
                #'GET',
                #headers = headers,
                #)

        ## TODO: error checking
        #self._cookie = None

    def build_url(self, path, query = {}):
        """
        Builds a Trello URL.

        :path: URL path
        :params: dict of key-value pairs for the query string
        """
        url = 'https://api.trello.com/1'
        if path[0:1] != '/':
            url += '/'
        url += path

        if hasattr(self, 'oauth_token'):
            url += '?'
            url += "key="+self.oauth_token.key
            url += "&token="+self.oauth_consumer.key
        else:
            url += '?'
            url += "key="+self.api_key
            url += "&token="+self.auth_token

        if len(query) > 0:
            url += '&'+urlencode(query)

        return url

    def list_boards(self):
        """
        Returns all boards for your Trello user

        :return: a list of Python objects representing the Trello boards. Each board has the 
        following noteworthy attributes:
            - id: the board's identifier
            - name: Name of the board
            - desc: Description of the board
            - closed: Boolean representing whether this board is closed or not
            - url: URL to the board
        """
        json_obj = self.fetch_json('/members/me/boards/all')
        boards = list()
        for obj in json_obj:
            board             = Board(self, obj['id'], name=obj['name'].encode('utf-8'))
            board.description = obj['desc']
            board.closed      = obj['closed']
            board.url         = obj['url']
            boards.append(board)

        return boards

    def fetch_json(self,
                   uri_path,
                   http_method = 'GET',
                   headers = {},
                   query_params = {},
                   post_args = {}):
        """ Fetch some JSON from Trello """

        headers['Accept'] = 'application/json'
        url = self.build_url(uri_path, query_params)
        response, content = self.client.request(
                                url,
                                http_method,
                                headers = headers,
                                body = json.dumps(post_args))

        # error checking
        if response.status != 200:
            raise ResourceUnavailable(url)
        return json.loads(content)


class Board(object):
    """Class representing a Trello board. Board attributes are stored as normal Python attributes;
    access to all sub-objects, however, is always an API call (Lists, Cards).
    """

    def __init__(self, client, board_id, name=''):
        """Constructor.
        
        :trello: Reference to a Trello object
        :board_id: ID for the board
        """
        self.client = client
        self.id     = board_id
        self.name   = name

    def __repr__(self):
        return '<Board %s>' % self.name

    def fetch(self):
        """Fetch all attributes for this board"""
        json_obj         = self.client.fetch_json('/boards/'+self.id)
        self.name        = json_obj['name']
        self.description = json_obj['desc']
        self.closed      = json_obj['closed']
        self.url         = json_obj['url']

    def save(self):
        pass
        
    def all_lists(self):
        """Returns all lists on this board"""
        return self.get_lists('all')

    def open_lists(self):
        """Returns all open lists on this board"""
        return self.get_lists('open')

    def closed_lists(self):
        """Returns all closed lists on this board"""
        return self.get_lists('closed')

    def get_lists(self, list_filter):
        # error checking
        json_obj = self.client.fetch_json(
                       '/boards/'+self.id+'/lists',
                       query_params = {'cards': 'none', 'filter': list_filter})
        lists = list()
        for obj in json_obj:
            l = List(self, obj['id'], name=obj['name'].encode('utf-8'))
            l.closed = obj['closed']
            lists.append(l)

        return lists

class List(object):
    """Class representing a Trello list. List attributes are stored on the object, but access to 
    sub-objects (Cards) require an API call"""

    def __init__(self, board, list_id, name=''):
        """Constructor

        :board: reference to the parent board
        :list_id: ID for this list
        """
        self.board  = board
        self.client = board.client
        self.id     = list_id
        self.name   = name

    def __repr__(self):
        return '<List %s>' % self.name

    def fetch(self):
        """Fetch all attributes for this list"""
        json_obj    = self.client.fetch_json('/lists/'+self.id)
        self.name   = json_obj['name']
        self.closed = json_obj['closed']

    def list_cards(self):
        """Lists all cards in this list"""
        json_obj = self.client.fetch_json('/lists/'+self.id+'/cards')
        cards = list()
        for c in json_obj:
            card             = Card(self, c['id'], name=c['name'].encode('utf-8'))
            card.description = c['desc']
            card.closed      = c['closed']
            card.url         = c['url']
            cards.append(card)
        return cards

    def add_card(self, name, desc = None):
        """Add a card to this list

        :name: name for the card
        :return: the card
        """
        json_obj = self.client.fetch_json(
                       '/lists/'+self.id+'/cards',
                       http_method = 'POST',
                       headers = {'Content-type': 'application/json'},
                       post_args = {'name': name, 'idList': self.id, 'desc': desc},)

        card             = Card(self, json_obj['id'])
        card.name        = json_obj['name']
        card.description = json_obj['desc']
        card.closed      = json_obj['closed']
        card.url         = json_obj['url']
        return card

class Card(object):
    """ 
    Class representing a Trello card. Card attributes are stored on 
    the object
    """

    def __init__(self, trello_list, card_id, name=''):
        """Constructor

        :trello_list: reference to the parent list
        :card_id: ID for this card
        """
        self.trello_list = trello_list
        self.client      = trello_list.client
        self.id          = card_id
        self.name        = name

    def __repr__(self):
        return '<Card %s>' % self.name

    def fetch(self):
        """Fetch all attributes for this card"""
        json_obj = self.client.fetch_json(
                       '/cards/'+self.id,
                       query_params = {'badges': False})

        self.name        = json_obj['name']
        self.description = json_obj['desc']
        self.closed      = json_obj['closed']
        self.url         = json_obj['url']
        self.member_ids  = json_obj['idMembers']
        self.short_id    = json_obj['idShort']
        self.list_id     = json_obj['idList']
        self.board_id    = json_obj['idBoard']
        self.attachments = json_obj['attachments']
        self.labels      = json_obj['labels']
        self.badges      = json_obj['badges']
