# -*- coding: utf-8  -*-

import urllib.parse, urllib.request, urllib.error, json, time, re
from socket import error as socket_error

__server = 'https://www.wikia.com/api/v1/'
languages = None

__cache = {}
def cached(fn):
    name = fn.__module__ + '.' + fn.__name__
    
    def decorator(*args, **kwargs):
        t = (name, hash(args), hash(hash(frozenset(kwargs.items()))))
        if t in __cache:
            return __cache[t]
        
        data = fn(*args, **kwargs)
        
        __cache[t] = data
        return data
    return decorator

def getJSON(url, tries = 5, delay = 3):
    t, d = tries, delay
    while t > 1:
        try:
            t -= 1
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code in [404, 410]: raise
            print('{0}, retrying in {1} seconds'.format(str(e), d))
            time.sleep(d)
            d *= 2
        except urllib.error.URLError as e:
            e.url = url
            if str(e).find('getaddrinfo') > -1:
                print('Host not found, retrying in {0} seconds'.format(d))
                time.sleep(d)
                d *= 2
            else:
                raise
        except socket_error as e:
            print('{0}, retrying in {1} seconds'.format(str(e), d))
            time.sleep(d)
        except (ValueError, json.decoder.JSONDecodeError) as e:
            raise JSONError('No JSON object could be decoded', url)
    raise JSONError('Failed after {0} tries'.format(tries), url)
        
class JSONError(Exception):
    def __init__(self, value, url):
        self.value = value
        self.url = url
    def __str__(self):
        return '%s (%s)' % (str(self.value), self.url)

def call(path, query = {}, server = None):
    qs = urllib.parse.urlencode(query)
    url = ''.join([server or __server, path, '?' if qs else '', qs])
    return getJSON(url)

@cached
def getWikiVariables(url):
    server = 'http://' + url + '/api/v1/'
    return call('Mercury/WikiVariables', server = server)['data']

def getDetails(ids):
    if isinstance(ids, (int, str)): ids = [ids]
    ids = [int(i) for i in ids]
    
    res = {}
    while len(ids):
        lst = ids[:250]
        ids = ids[250:]
        subres = call('Wikis/Details', {
            'ids': ','.join(str(x) for x in lst),
            'expand': 1,
            'width': 123,
            'height': 456,
        })
        res = {**res, **subres['items']}
    return res

def getWAMIndex(lang = None, limit = 20):
    limit = min(limit, 20) # API breaks when limit is above 20 atm
    lst = []
    options = {
        'sort_column': 'wam',
        'sort_direction': 'DESC',
        'limit': limit,
        'offset': 0,
    }
    if lang is not None: options['wiki_lang'] = lang
    while True:
        res = call('WAM/WAMIndex', options)
        if len(res['wam_index']) == 0: break
        lst += [int(i) for i in res['wam_index'].keys()]
        if len(lst) >= limit: break
        options['offset'] += options['limit']
    return lst