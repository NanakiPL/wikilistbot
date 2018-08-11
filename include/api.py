# -*- coding: utf-8  -*-
#from wiki import Wiki

import urllib.parse, urllib.request, urllib.error, json, time, re
from socket import error as socket_error
from include.wiki import Wiki, InvalidWiki, ClosedWiki

from pprint import pprint

__server = 'https://www.wikia.com/api/v1/'
languages = None

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

def call(path, query = {}):
    qs = urllib.parse.urlencode(query)
    url = ''.join([__server, path, '?' if qs else '', qs])
    
    return getJSON(url)


def prepWikis(l, langs = None):
    r = []
    for v in l:
        try:
            if v is None: raise InvalidWiki()
            if langs is not None and len(langs) and v['lang'] not in langs: continue
            r += [Wiki(v)]
        except (ClosedWiki, InvalidWiki) as e:
            r += [e]
    return r

def getDetails(ids):
    if isinstance(ids, int): ids = [ids]
    res = call('Wikis/Details', {
        'ids': ','.join(str(x) for x in ids),
        'expand': 1,
        'width': 123,
        'height': 456,
    })
    return prepWikis([res['items'][str(k)] if str(k) in res['items'] else None for k in ids])
    
def getTopWikis(hub = None):
    res = call('Wikis/List', {
        'hub': hub,
        'limit': 250,
        'expand': 1,
        'width': 123,
        'height': 456,
        #'lang': ','.join(languages), # returns nothing atm
    })
    return prepWikis(res['items'], languages)

def getWAMIndex(lang = None, limit = 200):
    l = []
    options = {
        'sort_column': 'wam',
        'sort_direction': 'DESC',
        'limit': 20,
        'offset': 0,
    }
    if lang is not None: options['wiki_lang'] = lang
    while True:
        res = call('WAM/WAMIndex', options)
        if len(res['wam_index']) == 0: break
        l += res['wam_index'].keys()
        if len(l) >= limit: break
        options['offset'] += options['limit']
    return l