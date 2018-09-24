import urwid

from .header import foamMonHeader
import os
from .FoamDataStructures import Cases, default_elements
import threading
import time
import datetime

import cProfile, pstats
import sys
import json

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


CASE_CTR = 0
CASE_REFS = {}
MODE_SWITCH = False
FOCUS_ID = None
FILTER = None
FPS = 1.0
# TODO use COLUMNS for column width
COLUMNS = {}
FILTER = {}


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

class TableHeader():
    # TODO create a base class

    def __init__(self, lengths):
        self.lengths = lengths
        global COLUMNS
        global FILTER
        self.columns = [CaseColumn(name, self.lengths.get(name, 20), None)
                for name in default_elements
                if COLUMNS[name]
                ]
        self.columns += [CaseColumn(el, 20, None) for el in FILTER.keys()]

    @property
    def header_text(self):
        s = "".join([c.getName() for c in self.columns])
        return s


class CaseColumn():

    def __init__(self, name, length, reference):
        self.name = name
        self.length = length
        self.reference = reference

    def get_pack(self, mode):
        if isinstance(self.name, str):
            if self.name == "progressbar":
                return ("pack", urwid.Text(self.bar()))
            return ("pack", urwid.Text((mode, "{: ^{length}}".format(
                    getattr(self.reference, self.name), length=self.length+2))))
        else:
            return ("pack", urwid.Text((mode, "{: ^{length}}".format(
                    self.reference.custom_filter(self.name[1]),
                        length=self.length+2))))

    def bar(self):
        bar = ProgressBar(50, self.reference.progress)
        bar.add_event(self.reference.case.startSamplingPerc, "sampling")
        return bar.digits

    def getName(self):
        return "{: ^{length}}".format(self.name, length=self.length+2)


class CaseRow(urwid.WidgetWrap):

    def __init__(self, case, Id, length=False, active=False):

        self.case = case
        self.active = active
        self.lengths = length
        global CASE_CTR
        global CASE_REFS
        CASE_CTR +=  1
        self.Id = CASE_CTR
        CASE_REFS[int(self.Id)] = self.case.case

        mode_text = "active" if self.active else "inactive"
        global COLUMNS
        global FILTER
        if self.case:
            self.columns = [CaseColumn(name, self.lengths.get(name, 20), self.case)
                    for name in default_elements
                    if COLUMNS[name]
                    ]
            self.columns += [CaseColumn(el, 20, self.case) for el in FILTER.items()]

                       #  ["Temperature",
                       # "T gas min/max  = ([0-9,. ]*)"]]]

        else:
            self.columns = []

        urwid.WidgetWrap.__init__(self, urwid.Columns(
            [("pack", urwid.Text((mode_text, "{: ^2} ".format(self.Id))))]
            + self.status_packs(mode_text)))

    def status_packs(self, mode):
        return [c.get_pack(mode) for c in self.columns]


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


class CasesListFrame():

    def __init__(self, cases, hide_inactive):
        self.cases = cases
        self.hide_inactive = hide_inactive

    def draw(self):
        """ return a ListBox with all sub folder """
        lengths, valid_cases = self.cases.get_valid_cases()
        items = [urwid.Text(TableHeader(lengths).header_text)]
        items += [DisplaySub(i+1, path, elems, lengths, self.hide_inactive)
            for i, (path, elems) in enumerate(valid_cases.items())]
        return urwid.ListBox(urwid.SimpleFocusListWalker(items))

    def toggle_hide(self):
        self.hide_inactive = not self.hide_inactive


class ScreenParent(urwid.WidgetWrap):

    def __init__(self, frame, mode_switch):

        self._w = frame
        self.input_mode = False
        self.mode_switch = mode_switch
        self.input_txt = ""
        urwid.WidgetWrap.__init__(self, self._w)

    def update(self):
        self._w = self.draw()
        return self

    def keypress_parent(self, size, key):
        global FOCUS_ID
        global FILTER
        if key == 'Q' or key == 'q':
            self.cases.running = False
            raise urwid.ExitMainLoop()
            # sys.exit(1)
        elif self.input_mode:
            if key != "enter" and key != "backspace":
                self.input_txt += key
                self.input_mode_footer_txt += key
                self._w = self.draw()
            elif key == "backspace":
                self.input_txt = self.input_txt[0:-1]
                self.input_mode_footer_txt = self.input_mode_footer_txt[0:-1]
                self._w = self.draw()
            elif "enter" in key and self.input_mode == "Focus":
                # self.focus_mode = True
                FOCUS_ID = self.input_txt
                global MODE_SWITCH
                MODE_SWITCH = True
                FILTER = None
                self.input_mode = False
            elif "enter" in key and self.input_mode == "Filter":
                # self.focus_mode = True
                FILTER = self.input_txt
                self.input_mode = False


class OverviewScreen(ScreenParent):

    def __init__(self, cases, focus_id, mode_switch, hide_inactive=False):
        self.cases = cases
        self.focus_id = focus_id
        self.hide_inactive = hide_inactive
        self.cases_list_frame = CasesListFrame(self.cases, self.hide_inactive)
        self.input_mode_footer_txt = "Case ID: "

        # Draw empty screen first to construct base class
        self._w = urwid.Text("")
        self.mode_switch = mode_switch
        ScreenParent.__init__(self, self._w, self.mode_switch)
        self._w = self.draw()

    @property
    def footer(self):
        if not self.input_mode:
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
            return urwid.Columns([legend, menu])
        else:
            return urwid.Edit(self.input_mode_footer_txt)

    def draw(self):

        banner = urwid.Text(foamMonHeader, "center")
        body = urwid.LineBox(self.cases_list_frame.draw())
        footer = self.footer

        return urwid.Frame(header=banner, body=body, footer=footer)

    def keypress(self, size, key):
        if key == 'F' or key == 'f':
            self.input_mode = "Focus"
            self._w = self.draw()
        elif key == 'T' or key == 't':
            self.cases_list_frame.toggle_hide()
            self._w = self.draw()
        else:
            self.keypress_parent(size, key)


class FocusScreen(ScreenParent):

    def __init__(self, focus_id):
        self.focus_id = focus_id
        self.hide_inactive = False
        self.input_mode_footer_txt = "Filter: "
        self._w = urwid.Text("")
        ScreenParent.__init__(self, self._w, False)
        self._w = self.draw()

    def draw(self):

        global CASE_REFS
        global FOCUS_ID
        banner = urwid.Text(foamMonHeader, "center")
        # body = urwid.LineBox(self.cases_list_frame.draw())
        global FILTER
        body = urwid.Pile([
            ("pack", urwid.Text(CASE_REFS[int(FOCUS_ID)].path)),
            ("pack", urwid.Text(CASE_REFS[int(FOCUS_ID)].log.text(FILTER)))])
        footer = self.footer

        return urwid.Frame(header=banner, body=body, footer=footer)


    @property
    def footer(self):
        if not self.input_mode:
            menu = urwid.Text([
                    u'Press (', ('mode button', u'O'), u') for overview mode, ',
                    u'(', ('mode button', u'/'), u') to filter, ',
                    u'(', ('quit button', u'Q'), u') to quit,'],
                        align="right")
            legend = urwid.Text(["Legend: ",
                ("progress", " "), " Progress ",
                ("active", "Active"), " ",
                ("inactive", "Inactive"), " ",
                ("sampling", " "), " Sampling Start"])
            return urwid.Columns([legend, menu])
        else:
            return urwid.Edit(self.input_mode_footer_txt)

    def keypress(self, size, key):
        global IN
        if key == '/':
            self.input_mode = "Filter"
            self._w = self.draw()
        elif key == 'O' or key == 'o' and not self.input_mode:
            global MODE_SWITCH
            MODE_SWITCH = True
        else:
            self.keypress_parent(size, key)


class LogMonFrame(urwid.WidgetWrap):

    def __init__(self, cases):
        self.cases = cases
        self.focus_mode = False
        self.focus_id = None
        self.mode_switch = False
        self.frame = OverviewScreen(self.cases, self.focus_id, self.mode_switch)
        self._w = self.frame
        urwid.WidgetWrap.__init__(self, self._w)

    def draw(self):
        """ returns either a FocusScreen or OverviewScreen instance """
        global MODE_SWITCH
        global FPS
        if not MODE_SWITCH:
            self.frame = self.frame.update()
            return self.frame
        else:
            if isinstance(self.frame, OverviewScreen):
                self.frame = FocusScreen(self.focus_id)
                MODE_SWITCH = False
                FPS = 30.0
                return self.frame
                # self._w = self.frame
            else:
                self.frame = OverviewScreen(self.cases, self.focus_id, self.mode_switch)
                FPS = 1.0
                MODE_SWITCH = False
                return self.frame

    def keypress(self, size, key):
        """ delegates keypress to the actual screen """
        self._w.keypress(size, key)

    def animate(self, loop=None, data=None):
        # Reset the case display number counter
        global  CASE_CTR
        CASE_CTR = 0

        self.frame = self.draw() # bodyTxt.update()
        self._w = self.frame
        global FPS
        self.animate_alarm = self.loop.set_alarm_in(1.0/FPS, self.animate)

def cui_main(arguments):

    # pr = cProfile.Profile()
    # pr.enable()  # start profilin

    cases = Cases(os.getcwd())

    global COLUMNS
    COLUMNS = {c: False if arguments.get("--" + c) == "False" else True
               for c in ["progressbar", "folder", "logfile",
                   "time", "writeout", "remaining"]
            }

    global FILTER
    FILTER = json.loads(arguments.get("--custom_filter"))

    frame = LogMonFrame(cases)
    mainloop = urwid.MainLoop(frame, palette, handle_mouse=False)
    mainloop.screen.set_terminal_properties(colors=256)
    frame.loop = mainloop
    frame.animate()
    mainloop.run()

    # pr.disable()  # end profiling
    # sortby = 'cumulative'
    # ps = pstats.Stats(pr).sort_stats(sortby)
    # ps.print_stats()

