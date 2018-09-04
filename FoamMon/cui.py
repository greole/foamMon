import urwid
from .version import __version__ as version

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
                                                                                          by Gregor Olenik, go@hpsim.de, hpsim.de, Version: {}
""".format(version)

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


CASE_CTR = 0
CASE_REFS = {}
MODE_SWITCH = False
FOCUS_ID = None
FILTER = None


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
        CASE_REFS[int(self.Id)] = self.case.case

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

class TableHeader():

    def __init__(self, lengths):
        self.lengths = lengths

    @property
    def header_text(self):
        width_folder =  self.lengths[1] + 2
        width_log =  self.lengths[2] + 2
        width_time =  self.lengths[3] + 2
        width_next_write =  max(12, self.lengths[4] + 2)
        width_finishes =  self.lengths[5] + 2
        # s = "{: ^{width_progress}}│"
        s = "{: ^{width_progress}}{: ^{width_folder}}{: ^{width_log}}"
        s += "{: ^{width_time}}{: ^{width_next_write}}{: ^{width_finishes}}"
        s = s.format(
                "Progress",
                "Folder", "Logfile",
                "Time", "Writeout", "Remaining",
                # width_progress=width_progress,
                width_progress=54,
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
            self.hide_inactive = not self.hide_inactive
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
        if not MODE_SWITCH:
            self.frame = self.frame.update()
            return self.frame
        else:
            if isinstance(self.frame, OverviewScreen):
                self.frame = FocusScreen(self.focus_id)
                MODE_SWITCH = False
                return self.frame
                # self._w = self.frame
            else:
                self.frame = OverviewScreen(self.cases, self.focus_id, self.mode_switch)
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
        self.animate_alarm = self.loop.set_alarm_in(0.01, self.animate)

def cui_main():

    cases = Cases(os.getcwd())

    frame = LogMonFrame(cases)
    mainloop = urwid.MainLoop(frame, palette)
    mainloop.screen.set_terminal_properties(colors=256)
    frame.loop = mainloop
    frame.animate()
    mainloop.run()

