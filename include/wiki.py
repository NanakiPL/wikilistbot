# -*- coding: utf-8  -*-
from pprint import pprint
from datetime import datetime
from collections import OrderedDict, Container

from pprint import pprint

class Wiki:
    id = None
    domain = None
    language = None
    name = None
    hub = None
    wordmark = None
    image = None
    
    api = None
    stats = None
    
    def __init__(self, data):
        try:
            if data['domain'] == '': raise ClosedWiki(data['url'])
            self.id = int(data['id'])
            self.domain = data['domain']
            
            self.language = data['lang']
            self.name = data['name']
            
            self.hub = data['hub']
            self.hasDiscussions = 'discussions' in data['stats']
            
        except AttributeError:
            raise ValueError('Only expanded Wikia API data is valid. There are inconsistencies between expanded and non-expanded results')
        
        self.api = WikiAPI(self)
        self.stats = WikiStats(self, data['stats'])
        
        if data['wordmark'] != '':
            self.wordmark = data['wordmark']
        if 'image' in data and data['image'] != '':
                self.image = data['image'].replace('/window-crop/width/123/x-offset/0/y-offset/0/window-width/124/window-height/456', '')
    
    def __repr__(self):
        return '{0}({1}, {2})'.format(self.__class__.__name__, self.domain, self.language)
    
    def dump(self):
        data = OrderedDict()
        
        data['id'] = self.id
        data['domain'] = self.domain
        data['name'] = self.name
        data['language'] = self.language
        data['hub'] = self.hub
        data['discussions'] = self.hasDiscussions
        data['wordmark'] = self.wordmark
        data['image'] = self.image
        
        today = datetime.now().strftime('%Y-%m-%d')
        data['stats'] = {
            today: OrderedDict({key: self.stats[key] for key in ['articles', 'images', 'videos', 'discussions', 'edits', 'activeUsers', 'admins', 'activeAdmins']})
        }
        return data

class WikiStats:
    wiki = None
    stats = {}
    
    def __init__(self, wiki, stats):
        self.wiki = wiki
        self.stats = stats
    
    def __getitem__(self, key):
        if key in self.stats:
            return self.stats[key]
        
        method = getattr(self.wiki.api, 'get{}'.format(key[0].upper() + key[1:]), None)
        if method: return method()
        return None

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

def getJSON(url, tries = 5, delay = 2):
    t, d = tries, delay
    while t > 1:
        try:
            t -= 1
            with urllib.request.urlopen(url) as response:
                res = response.read().decode('utf-8')
                return json.loads(res)
        except urllib.error.HTTPError as e:
            if e.code in [404, 410]: raise
            print('{0}, retrying in {1} seconds'.format(str(e), d))
            time.sleep(d)
            d *= 2
        except urllib.error.URLError as e:
            e.url = url
            if str(e).find('getaddrinfos') > -1:
                print('Host not found, retrying in {0} seconds'.format(d))
                time.sleep(d)
                d *= 2
            else:
                raise
        except socket_error as e:
            print('{0}, retrying in {1} seconds'.format(str(e), d))
            time.sleep(d)
        except (ValueError, json.decoder.JSONDecodeError) as e:
            print(res)
            if res.find('page-Special_CloseWiki') > -1:
                raise ClosedWiki(url)
            if res.find('page-Community_Central_Not_a_valid') > -1:
                raise InvalidWiki(url)
            raise JSONError('No JSON object could be decoded', url)
    raise JSONError('Failed after {0} tries'.format(tries), url)

class InvalidWiki(Exception):
    status = 'invalid'
    def __init__(self, url = None):
        self.url = url
    def __str__(self):
        return '{0} doesn\'t exist'.format(self.url or 'Wiki')
    def __repr__(self):
        return '{0}({1})'.format(self.__class__.__name__, self.url or '')

class ClosedWiki(InvalidWiki):
    status = 'closed'
    def __str__(self):
        return '{0} was closed'.format(self.url or 'Wiki')