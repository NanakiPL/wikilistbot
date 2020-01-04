# -*- coding: utf-8  -*-
import pywikibot, re, sys
from pywikibot import output
from pywikibot.exceptions import NoPage
from json import loads
from datetime import datetime, timedelta
from time import time
from math import floor

from include.wiki import newWiki, getCode as getWikiCode, Wiki, InvalidWiki, ClosedWiki, _wikis as allWikis
from include import api, luad, tools

class Bot(pywikibot.bot.SingleSiteBot):
    availableOptions = {
        'always': False,
        'force': False,
        'skipdetails': False,
        'skipadmins': False,
        'skipwam': False,
        'skipqueue': False,
    }
    settings = {
        'languages': None,
        
        'article_threshold': 5,
        'image_threshold': 0,
        
        'list_module': 'Wikis/list',
        'queue_module': 'Wikis/queue',
        'aliases_module': 'Wikis/aliases',
        'removed_module': 'Wikis/removed',
        
        'remove_keys': None,
        
        'keep_days': 14,
        
        'active_days': 60,
    }
    summaries = {
        'default': 'Bot updates data module',
        
        'list_create': 'Bot creates the list of wikis',
        'list_update': 'Bot updates the list of wikis',
        
        'wiki_create': 'Bot creates wiki data module',
        'wiki_update': 'Bot updates wiki data module',
        
        'queue_create': 'Bot creates the queue',
        'queue_update': 'Bot clears the queue',
        
        'aliases_create': 'Bot creates the list of aliases',
        'aliases_update': 'Bot updates the list of aliases',
        
        'removed_create': 'Bot creates the list of removals',
        'removed_update': 'Bot updates the list of removals',
    }
    
    __instance = None
    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(Bot, cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance
        
    def __init__(self):
        if(self.__initialized): return
        self.__initialized = True
        
        start = time()
        
        self.options = {
            'always': False,
            'force': False,
        }
        
        self.args = []
        for arg in pywikibot.handle_args():
            if   arg == '-always':        self.options['always'] = True
            elif arg == '-force':         self.options['force'] = True
            elif arg == '-skipdetails':   self.options['skipdetails'] = True
            elif arg == '-skipadmins':    self.options['skipadmins'] = True
            elif arg == '-skipwam':       self.options['skipwam'] = True
            elif arg == '-skipqueue':     self.options['skipqueue'] = True
            else: self.args.append(arg)
        
        self._site = pywikibot.Site()
        
        output('\n\r\n\r=== Working on \03{{lightaqua}}{0}\03{{default}} ===\n\r'.format(self.site.sitename, self.site.username()))
        
        self.site.login()
        
        self.getSettings()
        
        output('  Initialization time: {:.2f}s'.format(time() - start))
    
    @property
    def time(self):
        try:
            return self._time
        except AttributeError:
            self._time = floor(time())
        return self._time
    
    @property
    def current_page(self):
        return self._current_page
        
    @current_page.setter
    def current_page(self, page):
        if page != self._current_page:
            self._current_page = page
            output(u'\n\r\n\r>>> \03{{lightpurple}}{0}\03{{default}} <<<'.format(page.title()))
    
    def getSettings(self):
        title = self._site.mediawiki_message('custom-list-bot-module')
        data = self.getData(title)
        
        for key in ['languages', 'remove_keys']:
            self.settings[key] = data.get(key, self.settings[key])
        
        for key in ['keep_days', 'active_days']:
            self.settings[key] = max(1, data.get(key, self.settings[key]))
        
        api.languages = self.settings['languages']
        
        for key in ['article', 'image']:
            self.settings[key + '_threshold'] = data.get('thresholds', {}).get('list_' + key + 's', self.settings[key + '_threshold'])
        
        for key in ['list', 'queue', 'aliases', 'removed']:
            self.settings[key + '_module'] =  pywikibot.page.Page(self.site, data.get('modules', {}).get(key, self.settings[key + '_module']), ns = 828)
        
    # Lua data
    def getData(self, name):
        page = name if isinstance(name, pywikibot.page.Page) else pywikibot.page.Page(self.site, name, ns = 828)
        
        try:
            history = page.getVersionHistory(forceReload = True, getAll = True)
        except pywikibot.exceptions.NoPage:
            return None
        
        for rev in history:
            text = page.getOldVersion(rev.revid)
            try:
                return luad.loads(text)
            except Exception:
                output('Skipping revision #{0.revid:d} by {0.user:s} - invalid Lua code'.format(rev))
        return None
        
    def saveData(self, name, data, summary = None, summary_key = None, **kwargs):
        page = self.current_page = name if isinstance(name, pywikibot.page.Page) else pywikibot.page.Page(self.site, name, ns = 828)
        
        summary = summary or self.summaries.get(summary_key, self.summaries['default'])
        
        newtext = 'return ' + luad.dumps(data, indent = 4)
        try:
            oldtext = page.get()
        except pywikibot.exceptions.NoPage:
            oldtext = ''
        
        if re.sub('\[\'updated_timestamp\'\]\s*=\s*\d+,', '', newtext) == re.sub('\[\'updated_timestamp\'\]\s*=\s*\d+,', '', oldtext):
            return output('No changes')
        
        pywikibot.showDiff(oldtext, newtext)
        output('Summary: {}'.format(summary))
        
        if self.getOption('always'):
            choice = 'y'
        else:
            choice = pywikibot.input_choice('Do you want to accept these changes?', [('Yes', 'y'), ('Yes to all', 'a'), ('No', 'n')], default='N')
        
        if choice == 'a':
            self.options['always'] = True
            choice = 'y'
        if choice == 'y':
            page.put(newtext, summary, **kwargs)
    
    
    # Wiki table
    _wikitable = set()
    def addToTable(self, color, id, wiki):
        self._wikitable.add((id, color, wiki))
    def printLogTable(self):
        lst = sorted(self._wikitable)
        cols = [
            ('ID', 'id'),
            ('Lang', 'language'),
            ('Name', 'name'),
            ('URL', 'domain'),
            ('', 'status'),
        ]
        cols = list(map(lambda x, y: (x[0], x[1], max(y, len(x[0]))), cols, [max(len(str(getattr(row[2], attr) or '-')) for row in lst) for label, attr in cols]))
        
        output('')
        output('  ' + '   '.join(['\03{{{{lightyellow}}}}{{:<{:d}}}\03{{{{default}}}}'.format(width).format(label) for label, attr, width in cols]) +  '  ')
        output('+-' + '-+-'.join(['-'*width for label, attr, width in cols]) +  '-+')
        
        for row in lst:
            cells = ['\03{{{{{{1}}}}}}{{0:<{:d}}}\03{{{{default}}}}'.format(width).format(getattr(row[2], attr) or '-', row[1]) for label, attr, width in cols]
            output('| ' + ' | '.join(cells) +  ' |')
        
        output('+-' + '-+-'.join(['-'*width for label, attr, width in cols]) +  '-+')
        output('New wikis:     {:d}'.format(len(self.toAdd)))
        output('Removed wikis: {:d}'.format(len(self.toRemove)))
        output('New total:     {:d}'.format(len(self.toAdd | self.toUpdate)))
    
    _wikidata = None
    @property
    def wikidata(self):
        if self._wikidata is None:
            data = self.getData('Module:Lista/wiki')
            if isinstance(data, tuple):
                data = data[0]
            if isinstance(data, dict) and 'wikis' in data:
                self._wikidata = data['wikis']
            else:
                self._wikidata = {}
        return self._wikidata
    
    def getCurrentWikis(self):
        lst = [int(i) for i in self.wikidata]
        for id in lst:
            wiki = Wiki(id)
            wiki.updateFromDump(self.wikidata[id])
            wiki.onList = True
        return lst
        
    def getWAMWikis(self):
        if self.settings['languages'] is None:
            return api.getWAMIndex()
        res = []
        for lang in self.settings['languages']:
            res += api.getWAMIndex(lang)
        return res
    
    def getQueuedWikis(self):
        lst = []
        lst2 = []
        try:
            for id in self.getData(self.settings['queue_module']):
                try:
                    lst += [int(id)]
                except ValueError:
                    lst2 += [id]
        except TypeError:
            pass
        
        total = len(lst2)
        if total > 0:
            output('Found {} urls in the queue.'.format(total))
            i = 0
            tools.progressBar(0, 'Progress (0/{})'.format(total))
            try:
                for url in lst2:
                    data = api.getWikiVariables(url)
                    lst += [int(data['id'])]
                    i += 1
                    tools.progressBar(i/total, 'Progress ({}/{})'.format(i, total))
            finally:
                print()
        
        #lst += [3, 4, 1407124, 12345, 652632, 1743907, 1,2,3,4,5,6,7,8,9]
        # TODO: stare metody
        return lst
    
    def run(self):
        start = time()
        
        self.step1()
        self.step2()
        
        self.step3()
        self.end()
        
        output('\n  Run time: {:.2f}s'.format(time() - start))
    
    def step1(self):
        output('\n\r\03{lightyellow}Step 1\03{default}: Grabbing lists')
        
        output('\03{lightyellow}   1.1\03{default}: Current')
        A = set(self.getCurrentWikis())
        output('        Found \03{{lightaqua}}{:d}\03{{default}} wiki(s)'.format(len(A)))
        
        output('\n\r\03{lightyellow}   1.2\03{default}: WAM')
        if not self.getOption('skipwam'):
            B = set(self.getWAMWikis()) - A
            output('        Found \03{{lightaqua}}{:d}\03{{default}} more wiki(s)'.format(len(B)))
        else:
            B = set()
            output('        \03{lightyellow}skipping...\03{default}')
        
        output('\n\r\03{lightyellow}   1.3\03{default}: Queued list')
        if not self.getOption('skipqueue'):
            C = set(self.getQueuedWikis()) - A - B
            output('        Found \03{{lightaqua}}{:d}\03{{default}} more wiki(s)'.format(len(C)))
        else:
            C = set()
            output('        \03{lightyellow}skipping...\03{default}')
        
        ids = A | B | C
        
        if len(ids) == 0:
            output('\n\r\03{lightyellow}No wikis to work with were found\03{default}')
            raise pywikibot.bot.QuitKeyboardInterrupt
        
        output('\n\rFound \03{{lightaqua}}{:d}\03{{default}} unique wiki id(s) overall'.format(len(ids)))
        
        for id in ids:
            Wiki(id)
    
    
    toAdd = set()
    toUpdate = set()
    toRemove = set()
    def step2(self):
        output('\n\r\03{lightyellow}Step 2\03{default}: Fetching base info and processing')
        
        ids = [id for id in allWikis]
        lst = api.getDetails(ids)
        
        for id in ids:
            wiki = Wiki(id)
            try:
                wiki.updateFromAPI(lst[str(id)])
            except KeyError:
                wiki.__class__ = ClosedWiki if wiki.onList else InvalidWiki
            
            if isinstance(wiki, ClosedWiki):
                if wiki.onList:
                    self.toRemove.add(wiki)
                wiki.status = 'closed'
                self.addToTable('lightred', id, wiki)
            elif isinstance(wiki, InvalidWiki):
                wiki.status = 'invalid'
                self.addToTable('gray', id, wiki)
            elif self.settings['languages'] is not None and wiki.language not in self.settings['languages']:
                if wiki.onList:
                    self.toRemove.add(wiki)
                wiki.status = 'badlang'
                self.addToTable('lightpurple', id, wiki)
            elif not wiki.onList:
                self.toAdd.add(wiki)
                wiki.status = 'new'
                self.addToTable('lightgreen', id, wiki)
            else:
                self.toUpdate.add(wiki)
                wiki.status = ' '
                self.addToTable('default', id, wiki)
        
        self.printLogTable()
    
    def runForAll(self, method, *args, **kwargs):
        lst = sorted([(wiki.id, wiki) for wiki in self.toAdd | self.toUpdate])
        
        total = len(lst)
        i = 0
        print()
        tools.progressBar(0, 'Progress (0/{})'.format(total))
        try:
            for id, wiki in lst:
                getattr(wiki, method)(*args, **kwargs)
                i += 1
                tools.progressBar(i/total, 'Progress ({}/{})'.format(i, total))
        finally:
            print()
    
    def step3(self):
        output('\n\r\03{lightyellow}Step 3\03{default}: Active admin counts')
        
        if self.getOption('skipadmins'):
            return output('        \03{lightyellow}skipping...\03{default}')
        output('\03{gray}  Note: This process is done on per-wiki basis.\n\r        It can be skipped using keyboard interrupt or via -skipadmins argument.')
        
        try:
            self.runForAll('getAdminCount', timedelta(days = self.settings['active_days']))
        except KeyboardInterrupt:
            output('\n\r\03{lightblue}Task was finished partially.\03{default}')
            choice = pywikibot.input_choice('Do you want to keep partial data on save or ignore it?', [('Keep', 'k'), ('Ignore', 'i')], default='k')
            if choice == 'i':
                for wiki in self.toAdd | self.toUpdate:
                    wiki.dumpAdminCount = False
            elif choice == 'q':
                raise pywikibot.bot.QuitKeyboardInterrupt
    
    def saveList(self):
        self.current_page = self.settings['list_module']
        
        for wiki in self.toRemove:
            del self.wikidata[wiki.id]
            
        for wiki in self.toAdd:
            self.wikidata[wiki.id] = wiki.dump()
        
        for wiki in self.toUpdate:
            dump = wiki.dump()
                        
            for key, value in dump.items():
                if isinstance(value, dict):
                    try:
                        self.wikidata[wiki.id][key] = {**self.wikidata[wiki.id][key], **dump[key]}
                    except KeyError:
                        self.wikidata[wiki.id][key] = dump[key]
                else:
                    self.wikidata[wiki.id][key] = dump[key]
            
            try:
                for key in self.settings['remove_keys']:
                    try:
                        del self.wikidata[wiki.id][key]
                    except KeyError:
                        pass
            except TypeError:
                pass
        
        self.saveData(self.settings['list_module'], { 'wikis': self.wikidata, 'updated_timestamp': self.time}, summary_key = 'list_update' if self.settings['list_module'].exists() else 'list_create')
        
    
    def saveQueue(self):
        self.current_page = self.settings['queue_module']
        
        self.saveData(self.settings['queue_module'], [], summary_key = 'queue_update' if self.settings['queue_module'].exists() else 'queue_create')
    
    def saveAliases(self):
        self.current_page = self.settings['aliases_module']
        
        data = self.getData(self.settings['aliases_module']) or {}
        
        for alias in list(data.keys()):
            if data[alias] not in self.wikidata:
                del data[alias]
                continue
            
            code = getWikiCode(alias)
            if alias != code:
                data[code] = data[alias]
                del data[alias]
            
        for id in self.wikidata:
            data[self.wikidata[id]['code']] = id
        
        self.saveData(self.settings['aliases_module'], data, summary_key = 'aliases_update' if self.settings['aliases_module'].exists() else 'aliases_create')
    
    def saveRemoved(self):
        self.current_page = self.settings['removed_module']
        
        data = self.getData(self.settings['removed_module']) or {}
        
        for wiki in self.toRemove:
            if wiki.id not in data:
                data[wiki.id] = {
                    'id': wiki.id,
                    'domain': wiki.domain,
                    'timestamp': self.time,
                    'reason': wiki.status
                }
        
        self.saveData(self.settings['removed_module'], data, summary_key = 'removed_update' if self.settings['removed_module'].exists() else 'removed_create')

    def saveWikis(self):
        tpl = '{}/{{}}'.format(self.settings['list_module'].title(with_ns = False))
        wikis = sorted([(wiki.id, wiki) for wiki in self.toAdd | self.toUpdate])
        
        i = 0
        total = len(wikis)
        for id, wiki in wikis:
            page = pywikibot.page.Page(self.site, tpl.format(id), ns = 828)
            self.current_page = page
            
            data = self.getData(page) or {}
            data['updated_timestamp'] = self.time
            
            stats = data['stats']
            
            dump = wiki.dump(True, not self.getOption('skipdetails'))
            
            for key, value in dump.items():
                if isinstance(value, dict):
                    try:
                        data[key] = {**data[key], **dump[key]}
                    except KeyError:
                        data[key] = dump[key]
                else:
                    data[key] = dump[key]
            
            data['stats'] = {key: {**stats[key], **data['stats'][key]} for key in sorted(data['stats'].keys())[-self.settings['keep_days']:]}
            try:
                for key in self.settings['remove_keys']:
                    try:
                        del data[key]
                    except KeyError:
                        pass
            except TypeError:
                pass
            
            self.saveData(page, data, summary_key = 'wiki_update' if self.settings['removed_module'].exists() else 'wiki_create')
            
            i += 1
            output('Finished {} out of {} ({:.1%})'.format(i, total, i/total))
        
    
    def end(self):
        output('\n\r\03{lightyellow}Last step\03{default}: Saving data')
        
        self.saveList()
        self.saveQueue()
        self.saveAliases()
        self.saveRemoved()
        self.saveWikis()