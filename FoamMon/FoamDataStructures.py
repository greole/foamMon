from docopt import docopt
from colorama import Fore, Back, Style
# from datetime import datetime, timedelta
import datetime
import glob
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from copy import deepcopy

LEN_CACHE = 10000 # max lines of log header
LEN_CACHE_BYTES = 100*1024 # max lines of log header
CACHE_HEADER = None
CACHE_TAIL = None

def timedelta(seconds):
    return datetime.timedelta(seconds=int(max(0, seconds)))

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


class Cases():

    def __init__(self, path):
        self.path = path
        os.system("clear")
        print("Searching Logfiles")
        self.cases = defaultdict(list)
        p = ThreadPoolExecutor(1)
        p.submit(self.find_cases)
        while True:
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

            os.system("clear")
            print(foamMonHeader)
            # print(self.cases)
            self.print_header(lengths)
            # print(self.cases)
            for r, cs in case_stats.items():
                print("subfolder: " + os.path.basename(r))
                for c in cs["active"]:
                        print(c.to_str(lengths))
                for c in cs["inactive"]:
                        print(c.to_str(lengths))
            self.print_legend()
            time.sleep(0.2)

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
        while True:
            # try:
            top = self.path
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

                level = r.count(os.sep) - top.count(os.sep)
                # if level > 2:
                #      continue
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
                        # print("innner", e, r, d)
                        pass
            # except Exception as e:
            #     pass
            #     print(e, r)

    def print_header(self, lengths):
        width_progress = lengths[0]
        width_folder =  lengths[1] + 2
        width_log =  lengths[2] + 2
        width_time =  lengths[3] + 2
        width_next_write =  max(12, lengths[4] + 2)
        width_finishes =  lengths[5] + 2
        s = "{: ^{width_progress}}|{: ^{width_folder}}|{: ^{width_log}}|"
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

    def __init__(self, path, summary=False):
        self.path = path
        self.basename = os.path.basename(self.path)
        self.log_fns = self.find_logs()
        self.log = Log(self.find_recent_log_fn(), self)

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
        bar = ColoredProgressBar(digits, self.log.progress(self.endTime))
        bar.add_event(self.startSamplingPerc, Fore.YELLOW)
        return bar.draw()


    def find_logs(self):
       """ returns a list of filenames and ctimes """
       # print(self.path)
       r, d, files = next(os.walk(self.path))
       # TODO use regex to find logs
       files = list(filter(lambda x: "log" in x, files))
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
            return max(ds)
        else:
            ts = []
            r, ds, _ = next(os.walk(self.path))
            for t in ds:
                try:
                    tsf = float(t)
                    ts.append(tsf)
                except:
                    pass
            return max(ts)

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

    @property
    def endTime(self):
        return float(self.get_key_controlDict("endTime"))

    @property
    def writeInterval(self):
        return float(self.get_key_controlDict("writeInterval"))

    @property
    def startSampling(self):
        return float(self.get_key_controlDict("timeStart"))

    @property
    def startSamplingPerc(self):
        return self.startSampling/self.endTime

    @property
    def simTime(self):
        return self.log.sim_time

    def print_status_short(self):
        import sys
        try:
            exc_info = sys.exc_info()
            return Status(
                    self.status_bar(digits=50),
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
                prog_prec = self.log.progress(case.endTime)*100.0
                print(self.case.status_bar())
                print("Case properties: ")
                print("Job start time: ", self.log.start_time)
                print("Job elapsed_ time: ", timedelta(seconds=self.log.wall_time))
                print("Active: ", self.log.active)
                print("Parallel: ", self.log.is_parallel)
                print("Case end time: ", self.endTime)
                print("Current sim time: ", self.log.sim_time)
                print("Last time step on disk: ", self.last_timestep)
                print("Time next writeout: ", timedelta(seconds=self.timeleft_writeout()))
                print("Progress: ", prog_prec)
                print("Timeleft: ", timedelta(seconds=self.log.timeleft(case.endTime)))
            except:
                pass
            self.log.refresh()
            time.sleep(0.2)
            os.system("clear")


class Status():

    def __init__(self, bar, digits, active, base, name, time, wo, tl):
        self.bar = str(bar)
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

    def to_str(self, lengths):
        width_progress = lengths[0] + 2
        width_folder =  lengths[1] + 2
        width_log =  lengths[2] + 2
        width_time =  lengths[3] + 2
        width_next_write =  max(12, lengths[4] + 2)
        width_finishes =  lengths[5] + 2
        style = Style.BRIGHT if self.active else Style.DIM
        s = "{: ^{width_progress}}|"
        s += style +  "{: ^{width_folder}}|{: ^{width_log}}|"
        s += "{: ^{width_time}}|{: ^{width_next_write}}|{: ^{width_finishes}}"
        s += Style.RESET_ALL
        s = s.format(
                self.bar, self.base, self.name, self.time, self.wo, self.tl,
                width_progress=width_progress,
                width_folder=width_folder,
                width_log=width_log,
                width_time=width_time,
                width_next_write=width_next_write,
                width_finishes=width_finishes,
                )
        return s


class Log():

    def __init__(self, path, case):
        self.path = path
        self.case = case
        if self.path:
            self.cached_header =  self.cache_header()
            self.cached_body = self.cache_body()
            self.log = True
        else:
            self.log = False

    @property
    def is_valid(self):
        # TODO Fails on decompose logs
        if not self.path:
            return False
        if (self.Exec == "decomposePar") or (self.Exec == "blockMesh") or (self.Exec == "mapFields"):
            return False
        try:
            self.get_SimTime(self.cached_body)
            return True
        except Exception as e:
            # print("Invalid Log", e)
            return False

    @property
    def Exec(self):
        return self.get_Exec(self.cached_header)

    @property
    def getctime(self):
        return os.path.getctime(self.path)

    @property
    def active(self):
        if not self.log:
            return False
        return (time.time() - self.getctime) < 60.0

    def cache_header(self):
        """ read LEN_HEADER lines from log """
        with open(self.path, "rb") as fh:
            header = fh.read(LEN_CACHE_BYTES).decode('utf-8')
            ctime = header.find("ClockTime")
            padding = min(ctime+100, len(header))
            header = header[0:padding] # use 100 padding chars
            return header #.split("\n")

    def cache_body(self):
        """ read LEN_HEADER lines from log """
        with open(self.path, "rb") as fh:
            fh.seek(fh.tell(), os.SEEK_END)
            fh.seek(max(0, fh.tell()-LEN_CACHE_BYTES), os.SEEK_SET)
            return fh.read(LEN_CACHE_BYTES).decode('utf-8') #.split("\n")

    def refresh(self):
        self.cached_body = self.cache_body()

    def get_ClockTime(self, chunk, last=True):
        return float(re.findall("ClockTime = ([0-9.]*) s", chunk)[-1])


    def get_SimTime(self, chunk):
        return float(re.findall("\nTime = ([0-9.e\-]*)", chunk)[-1])

    def get_Exec(self, chunk):
        return re.findall("Exec   : ([0-9A-Za-z]*)", chunk)[0]


    def print_log_body(self):
        sep_width = 120
        print(self.path)
        print("="*sep_width)
        body_str = ("".join(self.cached_body.split("\n")[-30:-1]))
        print(body_str)

    @property
    def start_time(self):
        return self.get_SimTime(self.cached_header)

    @property
    def sim_time(self):
        return self.get_SimTime(self.cached_body)

    @property
    def wall_time(self):
        return self.get_ClockTime(self.cached_body)

    def remaining_sim_time(self, endtime):
        return endtime - self.sim_time

    @property
    def elapsed_sim_time(self):
        return self.sim_time - self.start_time

    def progress(self, endtime):
        return (self.sim_time)/endtime

    @property
    def sim_speed(self):
        return max(1e-12, self.elapsed_sim_time/self.wall_time)

    @property
    def is_parallel(self):
        # TODO use regex
        for line in self.cached_header.split("\n"):
            if 'Exec' in line and "-parallel" in line:
                    return True
        return False

        return max(1e-12, self.elapsed_sim_time/self.wall_time)

    def timeleft(self):
        return self.time_till(self.case.endTime)

    def time_till_writeout(self):
        return self.time_till(
                self.case.last_timestep
              + self.case.writeInterval)

    def time_till(self, end):
        return self.remaining_sim_time(end)/(self.sim_speed)


