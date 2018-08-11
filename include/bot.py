# -*- coding: utf-8  -*-
import pywikibot, re
from pywikibot import output
from pywikibot.exceptions import NoPage
from json import loads

from include.wiki import Wiki, InvalidWiki, ClosedWiki
from include import api, lua, lua2

from luaparser import ast

# Debug
from pprint import pprint
lua.show_repr = True

class Bot(pywikibot.bot.SingleSiteBot):
    availableOptions = {
        'always': False,
        'force': False,
    }
    
    __instance = None
    def __new__(cls, *args, **kwargs):
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
            if   arg == '-always':                         self.options['always'] = True
            if   arg == '-force':                          self.options['force'] = True
            else: self.args.append(arg)
        
        self._site = pywikibot.Site()
        
        output('\r\n\r\n=== Currently working on \03{{lightaqua}}{0}\03{{default}} ===\r\nAs: {1}'.format(self.site.sitename, self.site.username()))
        
        self.site.login()
        
    @property
    def current_page(self):
        return self._current_page
        
    @current_page.setter
    def current_page(self, page):
        if page != self._current_page:
            self._current_page = page
            output(u'\r\n\r\n>>> \03{{lightpurple}}{0}\03{{default}} <<<'.format(page.title()))
    
    def getData(self, name):
        page = pywikibot.page.Page(self.site, name, ns = 828)
        
        oldtext = page.get()
        
        return lua2.getData(oldtext)
        
        
    def saveData(self, name, data, summary = "Robot aktualizuje moduł z danymi", **kwargs):
        page = self.current_page = pywikibot.page.Page(self.site, name, ns = 828)
        
        newtext = 'return ' + lua.dumps(data)
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
    
    def run(self):
        api.languages = ['pl']
        
        data = self.getData('Module:Champion/Lissandra')
        pprint(data)
        
        data = {}
        ids = api.getWAMIndex('pl', 10)
        for i,wiki in enumerate(api.getDetails(ids)):
            try:
                if isinstance(wiki, Exception):
                    raise wiki
                data[wiki.id] = wiki.dump()
            except (InvalidWiki, ClosedWiki):
                pass
        
        self.saveData('Module:Lista/wiki', data)
        #print()