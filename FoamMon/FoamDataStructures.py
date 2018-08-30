from docopt import docopt
from colorama import Fore, Back, Style
# from datetime import datetime, timedelta
import datetime
import os
import time
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from copy import deepcopy
from .Log import Log
from .cui import foamMonHeader

import sys


def timedelta(seconds):
    return datetime.timedelta(seconds=int(max(0, seconds)))

class ColoredProgressBar():


    events = []

    def __init__(self, size, progress=0):
        self.size = size
        self.done_char = Fore.GREEN + "█" + Style.RESET_ALL
        self.undone_char = Fore.BLUE + "█" + Style.RESET_ALL
        self.digits = [self.done_char
                for _ in range(int(progress*size))]
        self.digits.extend([self.undone_char
                for _ in range(size - int(progress*size))])


    def add_event(self, percentage, color):
        index = int(percentage*self.size)
        self.digits[index] = color + "█" + Style.RESET_ALL

    def draw(self):
        return "".join(self.digits)

class ProgressBar():


    events = []

    def __init__(self, size, progress=0):
        self.size = size
        self.done_char = "█"
        self.undone_char = "░"
        self.digits = [self.done_char
                for _ in range(int(progress*size))]
        self.digits.extend([self.undone_char
                for _ in range(size - int(progress*size))])


    def add_event(self, percentage, color):
        index = int(percentage*self.size)
        self.digits[index] = "█"

    def draw(self):
        return "".join(self.digits)


class Cases():

    def __init__(self, path):
        self.path = path
        os.system("clear")
        self.cases = defaultdict(list)
        p = ThreadPoolExecutor(1)
        self.running = True
        p.submit(self.find_cases)

    def get_valid_cases(self):
        case_stats = {}
        cases = deepcopy(self.cases)
        for r, cs in cases.items():
            for c in cs:
                if (c.log.active):
                    c.log.refresh()
            case_stats[r] = {"active": [c.print_status_short() for c in cs
                    if (c.print_status_short() and c.log.active)],
                        "inactive": [c.print_status_short() for c in cs
                    if (c.print_status_short() and not c.log.active)]
                    }
        lengths = self.get_max_lengths(case_stats)
        return lengths, case_stats

    def get_max_lengths(self, statuses):
        lengths = [0 for _ in range(6)]
        for n, folder in statuses.items():
            for s in folder.get("active", []):
                for i in range(len(lengths)):
                    lengths[i] = max(lengths[i], s.lengths[i])

            for s in folder.get("inactive", []):
                for i in range(len(lengths)):
                    lengths[i] = max(lengths[i], s.lengths[i])
        return lengths

    def find_cases(self):

        while self.running:
            # try:
            top = self.path

            c = Case(top)
            subfold = top.split("/")[-1]
            if c.is_valid:
                exists = False
                for existing in self.cases[subfold]:
                    if c.path == existing.path:
                        exists = True
                if not exists:
                    self.cases[subfold].append(c)

            for r, dirs, _ in os.walk(self.path):

                ignore = [
                    "boundaryData",
                    "uniform",
                    "processor",
                    "constant",
                    "lagrangian",
                    "postProcessing",
                    "dynamicCode",
                    "system"]

                for d in deepcopy(dirs):
                    for i in ignore:
                        if d.startswith(i):
                            dirs.remove(d)

                for d in dirs:
                    try:
                        c = Case(os.path.join(r, d))
                        subfold = r.split("/")[-1]
                        if c.is_valid:
                            exists = False
                            for existing in self.cases[subfold]:
                                if c.path == existing.path:
                                    exists = True
                            if not exists:
                                self.cases[subfold].append(c)
                    except Exception as e:
                        print("innner", e, r, d)
                        pass

    def print_header(self, lengths):
        width_progress = lengths[0]
        width_folder =  lengths[1] + 2
        width_log =  lengths[2] + 2
        width_time =  lengths[3] + 2
        width_next_write =  max(12, lengths[4] + 2)
        width_finishes =  lengths[5] + 2
        s = "  {: ^{width_progress}}|{: ^{width_folder}}|{: ^{width_log}}|"
        s +="{: ^{width_time}}|{: ^{width_next_write}}|{: ^{width_finishes}}"
        s = s.format("Progress", "Folder", "Logfile", "Time", "Next write", "Finishes",
                width_progress=width_progress,
                width_folder=width_folder,
                width_log=width_log,
                width_time=width_time,
                width_next_write=width_next_write,
                width_finishes=width_finishes,
                )
        print(s)

    def print_legend(self):
        s = "\nLegend: "
        s += Fore.GREEN + "█" + Style.RESET_ALL + " Progress "
        s += Fore.YELLOW + "█"  + Style.RESET_ALL + " Start Sampling "
        s += Style.BRIGHT + "Active"  + Style.RESET_ALL  + " "
        s += Style.DIM + "Inactive"  + Style.RESET_ALL + "\n"
        print(s)

    def print_status(self):
        str_ = "\n".join([c.print_status_short()
            for c in self.cases
            if (c.print_status_short and c.log.active)])
        print(str_)


class Case():

    def __init__(self, path, log_format="log", summary=False, log_filter=None):
        self.path = path
        self.basename = os.path.basename(self.path)
        self.log_format = log_format
        self.log_fns = self.find_logs(self.log_format)
        self.log = Log(self.find_recent_log_fn(), self)
        self.log_filter = log_filter

        if summary:
            if self.log.active:
                ret = self.print_status_short()
                if ret:
                    print(ret)

    @property
    def is_valid(self):
        # print("check if valid", self.path)
        return self.has_controlDict and self.log.is_valid


    @property
    def started_sampling(self):
        return self.simTime > self.startSampling

    @property
    def has_controlDict(self):
        ctDct =  os.path.exists(self.controlDict_file)
        return ctDct

    def status_bar(self, digits=100):
        bar = ProgressBar(digits, self.log.progress(self.endTime))
        bar.add_event(self.startSamplingPerc, Fore.YELLOW)
        return bar.draw()


    def find_logs(self, log_format):
       """ returns a list of filenames and ctimes """
       # print(self.path)
       r, d, files = next(os.walk(self.path))
       # TODO use regex to find logs
       files = list(filter(lambda x: log_format in x, files))
       files = [os.path.join(r, f) for f in files]
       ctimes = [os.path.getctime(os.path.join(self.path, f)) for f in files]
       # print(self.path, files)
       return list(zip(ctimes, files))

    @property
    def last_timestep(self):
        if self.log.is_parallel:
            proc_dir = os.path.join(self.path, "processor0")
            if not os.path.exists(proc_dir):
                return 0
            r, ds, _ = next(os.walk(proc_dir))
            ds = [float(d) for d in ds if "constant" not in d]
            if ds:
                return max(ds)
            else:
                return 0
        else:
            ts = []
            r, ds, _ = next(os.walk(self.path))
            for t in ds:
                try:
                    tsf = float(t)
                    ts.append(tsf)
                except:
                    pass
            if ts:
                return max(ts)
            else:
                return 0.0

    def find_recent_log_fn(self):
        try:
            ctimes, files = zip(*self.log_fns)
            latest_index = ctimes.index(max(ctimes))
            return files[latest_index]
        except:
            return False

    @property
    def controlDict_file(self):
        return os.path.join(self.path, "system/controlDict")

    def get_key_controlDict(self, key):
        """ find given key in controlDict """
        # TODO cach controlDict to avoid reopening file
        separator = " "
        key += separator
        if self.has_controlDict:
            with open(self.controlDict_file) as f:
                for i, line in enumerate(f.readlines()):
                    if key in line:
                        # TODO use regex to sanitise
                        return (line.replace(key, '')
                                .replace(' ', '')
                                .replace(';', '')
                                .replace('\n', ''))
        else:
            return None

    def get_float_controlDict(self, key):
        ret = self.get_key_controlDict(key)
        if ret:
            return float(ret)
        else:
            return 0

    @property
    def endTime(self):
        return self.get_float_controlDict("endTime")

    @property
    def writeControl(self):
        return self.get_key_controlDict("writeControl")

    @property
    def writeInterval(self):
        if self.writeControl == "runTime":
            return self.get_float_controlDict("writeInterval")
        else:
            return (self.get_float_controlDict("writeInterval") *
                    self.get_float_controlDict("deltaT"))

    @property
    def startSampling(self):
        return self.get_float_controlDict("timeStart")

    @property
    def startSamplingPerc(self):
        return self.startSampling/self.endTime

    @property
    def simTime(self):
        return self.log.sim_time

    def print_status_short(self):
        try:
            exc_info = sys.exc_info()
            return Status(
                    self,
                    self.log.progress(self.endTime),
                    # Style.BRIGHT if self.log.active else Style.DIM,
                    50,
                    self.log.active,
                    self.basename,
                    os.path.basename(self.log.path),
                    self.log.sim_time,
                    timedelta(self.log.time_till_writeout()),
                    timedelta(self.log.timeleft()),
                    # Style.RESET_ALL
                    )
        except Exception as e:
            import traceback
            print(e, self.path)
            print(traceback.print_exception(*exc_info))
            return False

    def print_status_full(self):
        while True:
            self.log.print_log_body()
            try:
                prog_prec = self.log.progress(self.endTime)*100.0
                print(self.status_bar(100))
                print("Case properties: ")
                print("Job start time: ", self.log.start_time)
                print("Job elapsed_ time: ", timedelta(seconds=self.log.wall_time))
                print("Active: ", self.log.active)
                print("Parallel: ", self.log.is_parallel)
                print("Case end time: ", self.endTime)
                print("Current sim time: ", self.log.sim_time)
                print("Last time step on disk: ", self.last_timestep)
                print("Time next writeout: ", timedelta(self.log.time_till_writeout()))
                print("Progress: ", prog_prec)
                print("Timeleft: ", timedelta(self.log.timeleft()))
            except Exception as e:
                print(e)
                pass
            self.log.refresh()
            time.sleep(0.2)
            os.system("clear")


class Status():
    """ Handle status of single case for simple printing  """

    def __init__(self, case, progress, digits, active, base, name, time, wo, tl):
        self.case = case
        self.progress = progress
        self.digits = digits
        self.active = active
        self.base = base
        self.name = name
        self.time = str(time)
        self.wo = str(wo)
        self.tl = str(tl)

    @property
    def lengths(self):
        return [self.digits, len(self.base), len(self.name),
                len(self.time), len(self.wo), len(self.tl)]
