# -*- coding: utf-8  -*-

import re
import dateutil.parser
from datetime import datetime
from collections import OrderedDict, Container

from include import api

def newWiki(data):
    try:
        if data['domain'] == '':
            return ClosedWiki(data['id']).update(data)
        return Wiki(data['id']).update(data, True)
    except KeyError:
        return InvalidWiki(data['id']).update(data)

def getCode(text):
    return re.sub('\.(wikia\.com|wikia\.org|fandom\.com)(\/|$)', r'\2', text, flags = re.I)

_wikis = {}
class Wiki:
    id = None
    domain = None
    language = None
    name = None
    hub = None
    wordmark = None
    image = None
    
    discussions = False
    
    api = None
    stats = None
    
    onList = False
    status = None
    
    admin_groups = ['bureaucrat', 'sysop']
    mod_groups = ['threadmoderator', 'content-moderator', 'chatmoderator']
    
    def __new__(cls, id):
        id = int(id)
        if id in _wikis:
            return _wikis[id]
        
        _wikis[id] = self = object.__new__(cls)
        self.id = id
        self.api = WikiAPI(self)
        return self
    
    def __repr__(self):
        lst = [self.domain or '#{}'.format(self.id)]
        if self.language is not None:
            lst += [self.language]
        return '{}({})'.format(self.__class__.__name__, ', '.join(lst))
    
    def updateFromAPI(self, data):
        try:
            if data['domain'] == '':
                self.__class__ = ClosedWiki
                return
            self.name = data['name']
            try:
                self.domain = re.match('^(?:(?:https?\:)?\/\/)?(.*)$', data['url']).group(1)
            except AttributeError:
                self.domain = data['domain']
            self.domain = self.domain.rstrip('/')
            
            self.language = data['lang']
            
            self.hub = data['hub']
            self.stats = data['stats']
            del self.stats['users']
            
            self.discussions = 'discussions' in data['stats']
            
            if data['wordmark'] != '':
                self.wordmark = data['wordmark']
            if data['image'] != '':
                    self.image = data['image'].replace('/window-crop/width/123/x-offset/0/y-offset/0/window-width/124/window-height/456', '')
        except KeyError:
            raise ValueError('Only expanded Wikia API data is valid. There are inconsistencies between expanded and non-expanded results')
    
    def updateFromDump(self, data):
        for attr in ['name', 'domain', 'language', 'hub', 'discussions']:
            setattr(self, attr, data.get(attr, getattr(self, attr, None)))
    @property
    def code(self):
        return getCode(self.domain)
    
    def dump(self, detailed = False, load_missing = True):
        keys = ['id', 'name', 'domain', 'code', 'language', 'hub', 'discussions']
        noneKeys = ['wordmark', 'image']
        
        if detailed:
            if not self.has_details and load_missing:
                self.getWikiVariables()
            keys += ['mainpage', 'categories', 'anonediting', 'coppa', 'theme']
        
        data = {}
        for key in keys:
            try:
                val = getattr(self, key)
                if isinstance(val, dict):
                    data[key] = val.copy()
                elif val is not None:
                    data[key] = val
            except AttributeError:
                pass
        
        for key in noneKeys:
            data[key] = getattr(self, key, None)
        
        if detailed:
            today = datetime.now().strftime('%Y-%m-%d')
            data['stats'] = {
                today: self.stats.copy()
            }
            if self.has_admin_count:
                for key in ['active_bureaucrats', 'active_admins']:
                    data[key] = list(sorted([user['username'] for user in getattr(self, key, [])]))
        else:
            data['stats'] = self.stats.copy()
        
        return data
    
    has_details = False
    def getWikiVariables(self):
        vars = api.getWikiVariables(self.domain)
        
        self.mainpage = vars.get('mainPageTitle', None)
        self.categories = set(vars.get('wikiCategories', []))
        self.categories.add(self.hub.lower())
        
        self.favicon = vars.get('favicon', None)
        
        self.anonediting = not vars.get('disableAnonymousEditing', False)
        
        self.coppa = vars.get('isCoppaWiki', None)
        
        self.theme = {
            'isDark': vars.get('isDarkTheme', None),
            'headline': vars.get('siteMessage', None),
        }
        
        for key in [key for key in vars.get('theme', {}).keys() if key.startswith('color-')]:
            self.theme[key] = vars['theme'].get(key, None)
        
        self.has_details = True
        
    has_admin_count = False
    def getAdminCount(self, active_time):
        users = self.api.getUsers(groups = self.admin_groups + self.mod_groups, edits = 0, order = 'dtedit:desc')
        
        self.active_bureaucrats = []
        self.active_admins = []
        self.active_mods = []
        for user in users:
            if user['last_edit'] is None or (datetime.now() - user['last_edit']) > active_time:
                continue
            
            if any([x in user['groups'] for x in self.admin_groups]):
                self.active_admins += [user]
                if 'bureaucrat' in user['groups']:
                    self.active_bureaucrats += [user]
            elif any([x in user['groups'] for x in self.mod_groups]):
                self.active_mods += [user]
        
        self.stats['activeBureaucrats'] = len(self.active_bureaucrats)
        self.stats['activeAdmins'] = len(self.active_admins)
        self.stats['activeMods'] = len(self.active_mods)
        self.has_admin_count = True

class WikiAPI:
    wiki = None
    
    def __init__(self, wiki):
        self.wiki = wiki
    
    @property
    def server(self):
        return self.wiki.domain
    
    def getUsers(self, groups = [], edits = 5, order = 'revcnt:desc'):
        query = {
            'uselang': 'en',
            'action': 'ajax',
            'rs': 'ListusersAjax::axShowUsers',
            'groups': ','.join(groups),
            'edits': edits,
            'limit': '100',
            'order': order,
        }
        data = api.call('/index.php', query, server = 'https://' + self.wiki.domain)
        
        res = []
        cols = data['sColumns'].split(',')
        username_pattern = re.compile('\>([^<]+)\</a\>')
        date_pattern = re.compile('\>([^>]*(january|february|march|april|may|june|july|august|september|october|november|december)[^<]*)\<', flags = re.I)
        tag_pattern = re.compile('\<[^>]*\>')
        
        for row in data['aaData']:
            row = {cols[i]:v for i,v in enumerate(row)}
            
            user = {}
            user['username'] = username_pattern.search(row['username']).group(1)
            
            m = date_pattern.search(row['dtedit'])
            if m is not None:
                user['last_edit'] = dateutil.parser.parse(m.group(1))
            else:
                user['last_edit'] = None
            
            user['groups'] = [x.strip() for x in tag_pattern.sub('', row['groups']).split(',')]
            
            user['edits'] = int(tag_pattern.sub('', row['revcnt']))
            
            res += [user]
        return res

class InvalidWiki(Wiki):
    pass

class ClosedWiki(InvalidWiki):
    pass