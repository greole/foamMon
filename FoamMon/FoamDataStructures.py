from docopt import docopt
from colorama import Fore, Back, Style
# from datetime import datetime, timedelta
import datetime
import glob
import os
import re
import time

LEN_CACHE = 10000 # max lines of log header
LEN_CACHE_BYTES = 30*1024 # max lines of log header
CACHE_HEADER = None
CACHE_TAIL = None

def timedelta(seconds):
    return datetime.timedelta(seconds=int(max(0, seconds)))

class Cases():

    def __init__(self, path):
        self.path = path
        os.system("clear")
        print("Collecting Data")
        self.cases = self.find_cases()
        while True:
            case_stats = {}
            for r, cs in self.cases.items():
                for c in cs:
                    if (c.log.active):
                        c.log.refresh()
                case_stats[r] = {"active": [c.print_status_short() for c in cs
                        if (c.print_status_short() and c.log.active)],
                            "inactive": [c.print_status_short() for c in cs
                        if (c.print_status_short() and not c.log.active)]
                        }


            os.system("clear")
            self.print_header()
            # print(self.cases)
            for r, cs in case_stats.items():
                print(os.path.basename(r))
                for c in cs["active"]:
                        print(c)
                for c in cs["inactive"]:
                        print(c)
            self.print_legend()
            time.sleep(0.2)

    def find_cases(self):
        cases = {}
        top = self.path
        for r, dirs, _ in os.walk(self.path):
            dirs[:] = [d for d in dirs
                    if "processor" not in d
                    and "constant" not in d
                    and "postProcessing" not in d]
            level = r.count(os.sep) - top.count(os.sep)
            if level > 2:
                 continue
            # print(r)
            cases[r] = [Case(os.path.join(r, x)) for x in dirs]
        ret =  {r: [c for c in cs if c.is_valid]
                for r, cs in cases.items() if cs}
        return {r: c for r, c in ret.items() if c}

    def print_header(self):
        width_progress = 50
        width_folder =  25
        width_log =  10
        width_time =  10
        width_next_write =  16
        width_finishes =  16
        s = "{: ^{width_progress}}|{: ^{width_folder}}|{: ^{width_log}}|\
                {: ^{width_time}}|{: ^{width_next_write}}|{: ^{width_finishes}}".format(
                "Progress", "Folder", "Logfile", "Time", "Next write", "Finishes",
                width_progress=width_progress,
                width_folder=width_folder,
                width_log=width_log,
                width_time=width_time,
                width_next_write=width_next_write,
                width_finishes=width_finishes,
                )
        print(s)

    def print_legend(self):
        s = "\nLegend:\n\n"
        s += Fore.GREEN + "█" + Style.RESET_ALL + " Progress\n"
        s += Fore.YELLOW + "█"  + Style.RESET_ALL + " Start Sampling\n"
        s += Style.BRIGHT + "Active"  + Style.RESET_ALL  + "\n"
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
        return self.has_controlDict and self.log.is_valid


    @property
    def started_sampling(self):
        return self.simTime > self.startSampling

    @property
    def has_controlDict(self):
        ctDct =  os.path.exists(self.controlDict_file)
        return ctDct

    def status_bar(self, digits=100):
        prog_perc = int(self.log.progress(self.endTime)*digits)
        bar = (
                Fore.GREEN
                + "█" * prog_perc
                + Fore.RED
                # + "░" * (digits - prog_perc)
                + "█" * (digits - prog_perc)
                + Style.RESET_ALL
                )
        bar = list(bar)
        # FIXME
        # s = bar[int(self.startSamplingPerc*digits)]
        # cur_col = Fore.GREEN if self.started_sampling else Fore.RED
        # bar[int(self.startSamplingPerc*digits)] = Fore.YELLOW + s + cur_col
        return "".join(bar)


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
            return "{}{}{: ^25}|{: ^25}| {} |  {} | {} {}".format(
                    self.status_bar(digits=50),
                    Style.BRIGHT if self.log.active else Style.DIM,
                    self.basename,
                    os.path.basename(self.log.path),
                    self.log.sim_time,
                    timedelta(self.log.time_till_writeout()),
                    timedelta(self.log.timeleft()),
                    Style.RESET_ALL
                    )
        except Exception as e:
            import traceback
            print(traceback.print_exception(*exc_info))
            print(e)
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
        try:
            self.get_SimTime(self.cached_body)
            return True
        except Exception as e:
            print("Invalid Log", e)
            return False


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
        # for line in cache:
        #     if time == 'sim':
        #         if 'Time =' in line and not 'Clock' in line:
        #             return str_to_float(line)[0]
        #     else:
        #         if 'ClockTime =' in line:
        #             return str_to_float(line)[2]

    def print_log_body(self):
        sep_width = 120
        print(self.path)
        print("="*sep_width)
        body_str = ("".join(self.cached_body.split("\n")[-30:-1]))
        print(body_str)
        #print("="*sep_width)

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


