# -*- coding: utf-8  -*-
import pywikibot, re, sys
from pywikibot import output
from pywikibot.exceptions import NoPage
from json import loads
from datetime import datetime

from include.wiki import newWiki, Wiki, InvalidWiki, ClosedWiki, _wikis as allWikis
from include import api, luad, tools

# Debug
from pprint import pprint

class Bot(pywikibot.bot.SingleSiteBot):
    availableOptions = {
        'always': False,
        'force': False,
        'skipdetails': False,
        'skipadmins': False,
    }
    
    languages = None
    
    __instance = None
    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(Bot, cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance
        
    def __init__(self):
        if(self.__initialized): return
        self.__initialized = True
        
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
            else: self.args.append(arg)
        
        self._site = pywikibot.Site()
        
        output('\n\r\n\r=== Working on \03{{lightaqua}}{0}\03{{default}} ===\n\r'.format(self.site.sitename, self.site.username()))
        self.today = datetime.now().strftime('%Y-%m-%d')
        
        self.site.login()
        
        api.languages = self.languages = ['pl']
    
    @property
    def current_page(self):
        return self._current_page
        
    @current_page.setter
    def current_page(self, page):
        if page != self._current_page:
            self._current_page = page
            output(u'\n\r\n\r>>> \03{{lightpurple}}{0}\03{{default}} <<<'.format(page.title()))
    
    # Lua data
    def getData(self, name):
        page = pywikibot.page.Page(self.site, name, ns = 828)
        return luad.loads(page.get())
        
    def saveData(self, name, data, summary = "Robot aktualizuje moduł z danymi", **kwargs):
        page = self.current_page = pywikibot.page.Page(self.site, name, ns = 828)
        
        newtext = 'return ' + luad.dumps(data, indent = 4)
        try:
            oldtext = page.get()
        except pywikibot.exceptions.NoPage:
            oldtext = ''
        
        if newtext == oldtext:
            return output('No changes')
        
        pywikibot.showDiff(oldtext, newtext)
        if self.getOption('always'):
            choice = 'y'
        else:
            choice = pywikibot.input_choice('Do you want to accept these changes?', [('Yes', 'y'), ('No', 'n')], default='N')
        
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
            # TODO: Walidacja i fallback do starszej wersji
            if isinstance(data, tuple):
                self._wikidata = data[0]
            else:
                self._wikidata = data
        return self._wikidata
    
    def getCurrentWikis(self):
        lst = [int(i) for i in self.wikidata]
        for id in lst:
            wiki = Wiki(id)
            wiki.updateFromDump(self.wikidata[id])
            wiki.onList = True
        return lst
        
    def getWAMWikis(self):
        if self.languages is None:
            return api.getWAMIndex()
        res = []
        for lang in self.languages:
            res += api.getWAMIndex(lang)
        return res
    
    def getQueuedWikis(self):
        # TODO: wiki oczekujące
        return [3, 4, 1407124, 12345, 652632] #1743907
    
    def run(self):
        api.languages = self.languages
        
        self.step1()
        self.step2()
        
        self.step3()
        self.step4()
        
        self.end()
        
    def step1(self):
        output('\n\r\03{lightyellow}Step 1\03{default}: Grabbing lists')
        
        output('\03{lightyellow}   1.1\03{default}: Current')
        A = set(self.getCurrentWikis())
        output('        Found \03{{lightaqua}}{:d}\03{{default}} wiki(s)'.format(len(A)))
        
        output('\n\r\03{lightyellow}   1.2\03{default}: WAM')
        B = set(self.getWAMWikis()) - A
        output('        Found \03{{lightaqua}}{:d}\03{{default}} more wiki(s)'.format(len(B)))
        
        output('\n\r\03{lightyellow}   1.3\03{default}: Queued list')
        C = set(self.getQueuedWikis()) - A - B
        output('        Found \03{{lightaqua}}{:d}\03{{default}} more wiki(s)'.format(len(C)))
        
        ids = A | B | C
        
        if len(ids) == 0:
            output('\n\r\03{lightyellow}No wikis to work with were found\03{default}')
            raise pywikibot.bot.QuitKeyboardInterrupt
        
        output('\n\rFound \03{{lightaqua}}{:d}\03{{default}} unique wiki id(s) overall'.format(len(ids)))
        
        for id in ids: Wiki(id)
    
    
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
            elif self.languages is not None and wiki.language not in self.languages:
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
    
    def runForAll(self, method):
        lst = sorted([(wiki.id, wiki) for wiki in self.toAdd | self.toUpdate])
        
        total = len(lst)
        i = 0
        print()
        tools.progressBar(0, 'Progress (0/{})'.format(total))
        try:
            for id, wiki in lst:
                getattr(wiki, method)()
                i += 1
                tools.progressBar(i/total, 'Progress ({}/{})'.format(i, total))
                import time
                time.sleep(1)
        finally:
            print()
    
    def step3(self):
        output('\n\r\03{lightyellow}Step 3\03{default}: Detailed wiki info')
        if self.getOption('skipdetails'):
            return output('        \03{lightyellow}skipping...\03{default}')
            
        output('\03{gray}  Note: This process is done on per-wiki basis.\n\r        It can be skipped using keyboard interrupt or via -skipdetails argument.\n\r        Doing so won\'t delete data that\'s already there, it just won\'t be updated\03{default}')
        
        try:
            self.runForAll('getWikiVariables')
        except KeyboardInterrupt:
            output('\n\r\03{lightblue}Task was finished partially.\03{default}')
            choice = pywikibot.input_choice('Do you want to keep partial data on save or ignore it?', [('Keep', 'k'), ('Ignore', 'i')], default='k')
            if choice == 'i':
                for wiki in self.toAdd | self.toUpdate:
                    wiki.dumpWikiVariables = False
            elif choice == 'q':
                raise pywikibot.bot.QuitKeyboardInterrupt
    
    def step4(self):
        output('\n\r\03{lightyellow}Step 4\03{default}: Active admin counts')
        if self.getOption('skipadmins'):
            return output('        \03{lightyellow}skipping...\03{default}')
        output('\03{gray}  Note: This process is done on per-wiki basis.\n\r        It can be skipped using keyboard interrupt or via -skipadmins argument.')
        
        try:
            self.runForAll('getAdminCount')
        except KeyboardInterrupt:
            output('\n\r\03{lightblue}Task was finished partially.\03{default}')
            choice = pywikibot.input_choice('Do you want to keep partial data on save or ignore it?', [('Keep', 'k'), ('Ignore', 'i')], default='k')
            if choice == 'i':
                for wiki in self.toAdd | self.toUpdate:
                    wiki.dumpAdminCount = False
            elif choice == 'q':
                raise pywikibot.bot.QuitKeyboardInterrupt
    
    def end(self):
        output('\n\r\03{lightyellow}Last step\03{default}: Saving data')
        
        cleanup = ['category'] # TODO: settings
        
        for wiki in self.toRemove:
            del self.wikidata[wiki.id]
            
        for wiki in self.toAdd:
            self.wikidata[wiki.id] = wiki.dump()
        
        for wiki in self.toUpdate:
            pass
            dump = wiki.dump()
                        
            for key, value in dump.items():
                if isinstance(value, dict):
                    try:
                        self.wikidata[wiki.id][key] = {**self.wikidata[wiki.id][key], **dump[key]}
                    except KeyError:
                        self.wikidata[wiki.id][key] = dump[key]
                else:
                    self.wikidata[wiki.id][key] = dump[key]
            
            for key in cleanup:
                try:
                    del self.wikidata[wiki.id][key]
                except KeyError:
                    pass
        
        self.saveData('Lista/wiki', self.wikidata)
        
        