# -*- coding: utf-8  -*-

import re
from datetime import datetime
from collections import OrderedDict, Container

from include import api

#debug
from pprint import pprint

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
    def getAdminCount(self):
        # TODO
        
        self.has_admin_count = True

class WikiAPI:
    wiki = None
    script = '/api.php'
    
    def __init__(self, wiki):
        self.wiki = wiki
    
    @property
    def server(self):
        return self.wiki.domain
        
    def getActiveAdmins(self):
        return None

#def getJSON(url, tries = 5, delay = 2):
#    t, d = tries, delay
#    while t > 1:
#        try:
#            t -= 1
#            with urllib.request.urlopen(url) as response:
#                res = response.read().decode('utf-8')
#                return json.loads(res)
#        except urllib.error.HTTPError as e:
#            if e.code in [404, 410]: raise
#            print('{0}, retrying in {1} seconds'.format(str(e), d))
#            time.sleep(d)
#            d *= 2
#        except urllib.error.URLError as e:
#            e.url = url
#            if str(e).find('getaddrinfos') > -1:
#                print('Host not found, retrying in {0} seconds'.format(d))
#                time.sleep(d)
#                d *= 2
#            else:
#                raise
#        except socket_error as e:
#            print('{0}, retrying in {1} seconds'.format(str(e), d))
#            time.sleep(d)
#        except (ValueError, json.decoder.JSONDecodeError) as e:
#            if res.find('page-Special_CloseWiki') > -1:
#                raise ClosedWiki(url)
#            if res.find('page-Community_Central_Not_a_valid') > -1:
#                raise InvalidWiki(url)
#            raise JSONError('No JSON object could be decoded', url)
#    raise JSONError('Failed after {0} tries'.format(tries), url)

class InvalidWiki(Wiki):
    pass

class ClosedWiki(InvalidWiki):
    pass