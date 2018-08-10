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
    ('progress', '', 'dark green'),
    ('unprogressed', '', 'dark blue'),
    ('sampling', '', 'yellow'),
    ('quit button', 'dark red,bold', ''),
    ('getting quote', 'dark blue', ''),
    ('active', 'white,bold', ''),
    ('mode button', 'white,bold', ''),
    ('inactive ', 'light gray', ''),
    ('change negative', 'dark red', '')]

# class StatusWidget():

# class CaseElem(urwid.WidgetWrap):
#
#     def __init__(self, text, size):
#

CASE_CTR = 0
CASE_REFS = []

class ProgressBar():


    events = []

    def __init__(self, size, progress=0):
        self.size = size
        self.done_char = ("progress", " ")  # "█"
        self.undone_char = ("unprogressed", " ")  #"█"
        self.digits_done = [self.done_char
                for _ in range(int(progress*size))]
        self.digits_undone = [self.undone_char
                for _ in range(size - int(progress*size))]
        self.digits = self.digits_done + self.digits_undone


    def add_event(self, percentage, color):
        index = int(percentage*self.size)
        self.digits[index] = (color, " ")

    def draw(self):
        return "".join(self.digits)

    def render(self):
        return urwid.Text(self.digits)


class CaseRow(urwid.WidgetWrap):

    def __init__(self, case, Id, length=False, active=False):

        self.case = case
        self.active = active
        self.lengths = length
        global CASE_CTR
        global CASE_REFS
        CASE_CTR +=  1
        self.Id = CASE_CTR
        CASE_REFS.append(self.case.case)

        mode_text = "active" if self.active else "inactive"

        bar = ProgressBar(50, self.case.progress)
        bar.add_event(self.case.case.startSamplingPerc, "sampling")
        bar = bar.render()
        urwid.WidgetWrap.__init__(self, urwid.Columns(
            [("pack", urwid.Text((mode_text, "{: ^2} ".format(self.Id)))),
                ("pack", bar),
                ("pack", urwid.Text((mode_text, self.status_text)))]))

    @property
    def status_text(self):
        width_folder =  self.lengths[1] + 2
        width_log =  self.lengths[2] + 2
        width_time =  self.lengths[3] + 2
        width_next_write =  max(12, self.lengths[4] + 2)
        width_finishes =  self.lengths[5] + 2
        # s = "{: ^{width_progress}}│"
        s = "{: ^{width_folder}}{: ^{width_log}}"
        s += "{: ^{width_time}}{: ^{width_next_write}}{: ^{width_finishes}}"
        s = s.format(
                # index,
                self.case.base, self.case.name,
                self.case.time, self.case.wo, self.case.tl,
                # width_progress=width_progress,
                width_folder=width_folder,
                width_log=width_log,
                width_time=width_time,
                width_next_write=width_next_write,
                width_finishes=width_finishes,
                )
        return s


class DisplaySub(urwid.WidgetWrap):

    def __init__(self, Id, name, elems, lengths, hide_inactive):
        self.path = name
        self.elems = elems
        self.lengths = lengths
        self.Id = Id
        self.hide_inactive = hide_inactive
        self.frame = self.draw()
        urwid.WidgetWrap.__init__(self, self.frame)

    @property
    def active(self):
        return self.elems["active"]

    @property
    def inactive(self):
        return self.elems["inactive"]

    def draw(self):
        items = [("pack", CaseRow(c, (i+1)*self.Id, self.lengths, active=True))
                for i, c in enumerate(self.active)]

        if not self.hide_inactive:
            items += [("pack", CaseRow(c, (i+1+len(self.active))*self.Id, self.lengths, active=False))
                    for i, c in enumerate(self.inactive)]

        return urwid.BoxAdapter(urwid.Frame(
            header=urwid.Text(("casefolder", self.props_str)),
            body=urwid.Pile(items),
            footer=urwid.Divider("─")),
            height=len(items) + 2) # items + 1 and header and footer

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
        items = [DisplaySub(i+1, path, elems, lengths, self.hide_inactive)
            for i, (path, elems) in enumerate(valid_cases.items())]
        return urwid.ListBox(urwid.SimpleFocusListWalker(items))

    def update(self):
        self._w = self.draw()
        return self

class LogText(urwid.WidgetWrap):

    def __init__(self, cases):
        self.cases = cases
        self.hide_inactive = False
        self.frame = self.draw()
        urwid.WidgetWrap.__init__(self, self.frame)

    def draw(self):
        global CASE_REFS
        return urwid.Pile([
            ("pack", urwid.Text(CASE_REFS[0].path)),
            ("pack", urwid.Text(CASE_REFS[0].log.cache_body()))])

    def update(self):
        self._w = self.draw()
        return self


class LogMonFrame(urwid.WidgetWrap):

    def __init__(self, cases):

        self.cases = cases
        self.hide_inactive = False
        self.focus_mode = False
        self.focus_case = 1
        self.bodyTxt = CasesList(cases, hide_inactive=self.hide_inactive) # urwid.Text("")
        self.frame = self.draw()
        urwid.WidgetWrap.__init__(self, self.frame)

    def keypress(self, size, key):
        if key == 'F' or key == 'f':
            self.focus_mode = True
            self.bodyTxt = LogText(self.cases)
            self.frame = self.draw()
            self._w = self.frame
        elif key == 'T' or key == 't':
            self.bodyTxt.hide_inactive = not self.bodyTxt.hide_inactive
        elif key == 'Q' or key == 'q':
            self.cases.running = False
            raise urwid.ExitMainLoop()

    def draw(self):
        banner = urwid.Text(foamMonHeader, "center")

        body = urwid.LineBox(self.bodyTxt)

        menu = urwid.Text([
                u'Press (', ('mode button', u'T'), u') to toggle active, ',
                u'(', ('mode button', u'F'), u') to focus, ',
                u'(', ('quit button', u'Q'), u') to quit,'],
                    align="right")
        legend = urwid.Text(["Legend: ",
            ("progress", " "), " Progress ",
            ("active", "Active"), " ",
            ("inactive", "Inactive"), " ",
            ("sampling", " "), " Sampling Start"])
        footer = urwid.Columns([legend, menu])


        return urwid.Frame(header=banner, body=body, footer=footer)

    def animate(self, loop=None, data=None):
        # Reset counter
        global  CASE_CTR
        # global CASE_REFS
        CASE_CTR = 0
        # CASE_REFS = []
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

