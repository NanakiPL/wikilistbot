# -*- coding: utf-8  -*-

import os, re
from pathlib import Path


from pprint import pprint   

def main():
    import pywikibot
    from include.bot import Bot
    try:
        bot = Bot()
        bot.run()
    except (pywikibot.bot.QuitKeyboardInterrupt, KeyboardInterrupt):
        pywikibot.output('\r\n\03{lightyellow}Quitting\03{default}')
        try:
            pywikibot.stopme()
        except KeyboardInterrupt:
            pass
    
if __name__ == '__main__':
    cfile = Path('user-config.py')
    if not cfile.is_file():
        print('user-config.py file is required to run the bot. See user-config.py.example ')
    else:
        main()