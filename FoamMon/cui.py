import urwid
foamMonHeader = """
8 8888888888       ,o888888o.           .8.                   ,8.       ,8.                   ,8.       ,8.           ,o888888o.     b.             8
8 8888          . 8888     `88.        .888.                 ,888.     ,888.                 ,888.     ,888.       . 8888     `88.   888o.          8
8 8888         ,8 8888       `8b      :88888.               .`8888.   .`8888.               .`8888.   .`8888.     ,8 8888       `8b  Y88888o.       8
8 8888         88 8888        `8b    . `88888.             ,8.`8888. ,8.`8888.             ,8.`8888. ,8.`8888.    88 8888        `8b .`Y888888o.    8
8 888888888888 88 8888         88   .8. `88888.           ,8'8.`8888,8^8.`8888.           ,8'8.`8888,8^8.`8888.   88 8888         88 8o. `Y888888o. 8
8 8888         88 8888         88  .8`8. `88888.         ,8' `8.`8888' `8.`8888.         ,8' `8.`8888' `8.`8888.  88 8888         88 8`Y8o. `Y88888o8
8 8888         88 8888        ,8P .8' `8. `88888.       ,8'   `8.`88'   `8.`8888.       ,8'   `8.`88'   `8.`8888. 88 8888        ,8P 8   `Y8o. `Y8888
8 8888         `8 8888       ,8P .8'   `8. `88888.     ,8'     `8.`'     `8.`8888.     ,8'     `8.`'     `8.`8888.`8 8888       ,8P  8      `Y8o. `Y8
8 8888          ` 8888     ,88' .888888888. `88888.   ,8'       `8        `8.`8888.   ,8'       `8        `8.`8888.` 8888     ,88'   8         `Y8o.`
8 8888             `8888888P'  .8'       `8. `88888. ,8'         `         `8.`8888. ,8'         `         `8.`8888.  `8888888P'     8            `Yo
                                                                                                              by Gregor Olenik, go@hpsim.de, hpsim.de
"""

import os
from .FoamDataStructures import Cases
import threading
import time
import datetime

# Set up color scheme
palette = [
    ('titlebar', 'dark red', ''),
    ('refresh button', 'dark green,bold', ''),
    ('quit button', 'dark red', ''),
    ('getting quote', 'dark blue', ''),
    ('active', 'white,bold', ''),
    ('mode button', 'white,bold', ''),
    ('inactive ', 'light gray', ''),
    ('change negative', 'dark red', '')]

# class StatusWidget():

# Handle key presses
class CaseRow(urwid.WidgetWrap):

    def __init__(self, case, length=False, active=False):

        self.case = case
        self.active = active
        self.lengths = length

        mode_text = "active" if self.active else "inactive"
        urwid.WidgetWrap.__init__(self, urwid.Text((mode_text, self.status_text), "center"))

    @property
    def status_text(self):
        if not self.lengths:
            return "{} │ {} │ {} │ {} │ {} │ {}".format(self.case.bar, self.case.base, self.case.name, self.case.time, self.case.wo, self.case.tl)
        else:
            width_progress = self.lengths[0] + 2
            width_folder =  self.lengths[1] + 2
            width_log =  self.lengths[2] + 2
            width_time =  self.lengths[3] + 2
            width_next_write =  max(12, self.lengths[4] + 2)
            width_finishes =  self.lengths[5] + 2
            s = "{: ^{width_progress}}│"
            s += "{: ^{width_folder}}│{: ^{width_log}}│"
            s += "{: ^{width_time}}│{: ^{width_next_write}}│{: ^{width_finishes}}"
            s = s.format(
                    # index,
                    self.case.bar, self.case.base, self.case.name,
                    self.case.time, self.case.wo, self.case.tl,
                    width_progress=width_progress,
                    width_folder=width_folder,
                    width_log=width_log,
                    width_time=width_time,
                    width_next_write=width_next_write,
                    width_finishes=width_finishes,
                    )
            return s


class DisplaySub(urwid.WidgetWrap):

    def __init__(self, name, elems, lengths, hide_inactive):
        self.path = name
        self.elems = elems
        self.lengths = lengths
        self.hide_inactive = hide_inactive
        self.frame = self.draw()
        urwid.WidgetWrap.__init__(self, self.frame)

    def draw(self):
        items = [("pack", CaseRow(c, self.lengths, active=True)) for c in self.elems["active"]]
        if not self.hide_inactive:
            items += [("pack", CaseRow(c, self.lengths, active=False))
                    for c in self.elems["inactive"]]

        return urwid.BoxAdapter(urwid.Frame(
            header=urwid.Text(("casefolder", self.props_str)),
            body=urwid.Pile(items),
            footer=urwid.Divider("─")),
            height=len(items)+1)

    @property
    def props_str(self):
        num_active = len(self.elems["active"])
        num_inactive = len(self.elems["inactive"])
        return "Folder: {} total: {}, active: {}".format(
                self.path, num_inactive + num_active, num_active)

    def update(self):
        self._w = self.draw()
        return self

class CasesList(urwid.WidgetWrap):

    def __init__(self, cases, hide_inactive=False):
        self.cases = cases
        self.frame = self.draw()
        self.hide_inactive = hide_inactive
        urwid.WidgetWrap.__init__(self, self.frame)

    def draw(self):
        lengths, valid_cases = self.cases.get_valid_cases()
        items = [DisplaySub(path, elems, lengths, self.hide_inactive)
            for path, elems in valid_cases.items()]
        return urwid.ListBox(urwid.SimpleFocusListWalker(items))

    def update(self):
        self._w = self.draw()
        return self

class LogMonFrame(urwid.WidgetWrap):

    def __init__(self, cases):

        self.cases = cases
        self.hide_inactive = False
        self.bodyTxt = CasesList(cases, hide_inactive=self.hide_inactive) # urwid.Text("")
        self.frame = self.draw()
        urwid.WidgetWrap.__init__(self, self.frame)

    def keypress(self, size, key):
        if key == 'F' or key == 'f':
            pass
        elif key == 'T' or key == 't':
            self.bodyTxt.hide_inactive = not self.bodyTxt.hide_inactive
        elif key == 'Q' or key == 'q':
            self.cases.running = False
            raise urwid.ExitMainLoop()

    def draw(self):
        banner = urwid.Text(foamMonHeader, "center")

        body = urwid.LineBox(self.bodyTxt)

        menu = urwid.Text([
                u'Press (', ('mode button', u'T'), u') to toggle active. ',
                u'Press (', ('mode button', u'F'), u') to focus. ',
                    u'Press (', ('quit button', u'Q'), u') to quit.'],
                    align="right")

        return urwid.Frame(header=banner, body=body, footer=menu)

    def animate(self, loop=None, data=None):
        self.bodyTxt = self.bodyTxt.update()
        self.animate_alarm = self.loop.set_alarm_in(0.01, self.animate)

def cui_main():

    cases = Cases(os.getcwd())

    frame = LogMonFrame(cases)
    mainloop = urwid.MainLoop(frame, palette)
    mainloop.screen.set_terminal_properties(colors=256)
    frame.loop = mainloop
    frame.animate()
    mainloop.run()

