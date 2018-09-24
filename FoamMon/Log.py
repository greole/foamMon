# Log.py
import os
import re
import time

LEN_CACHE = 10000 # max lines of log header
LEN_CACHE_BYTES = 100*1024 # max lines of log header

CACHE_HEADER = None
CACHE_TAIL = None

class Log():

    def __init__(self, path, case):
        self.path = path
        self.case = case
        if self.path:
            self.mdate = os.path.getmtime(self.path)
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
        return self.get_header_value("exec")

    @property
    def nProcs(self):
        return self.get_header_value("nProcs")

    @property
    def Host(self):
        return self.get_header_value("Host")

    @property
    def build(self):
        return self.get_header_value("build")

    @property
    def Case(self):
        return self.get_header_value("Case")

    @property
    def PID(self):
        return self.get_header_value("PID")

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
        cur_mdate = os.path.getmtime(self.path)
        if self.mdate < cur_mdate:
            self.cached_body = self.cache_body()
            self.mdate = cur_mdate

    def get_values(self, regex, chunk):
        return re.findall(regex, chunk)

    def get_latest_value(self, regex, chunk):
        return self.get_values(regex, chunk)[-1]

    def get_latest_value_or_default(self, regex, chunk, default):
        try:
            return self.get_values(regex, chunk)[-1]
        except IndexError:
            return default

    def get_ClockTime(self, chunk, last=True):
        # NOTE some solver print only the ExecutionTime, thus both times are searched
        # if Execution and Clocktime are presented both are found and ExecutionTime
        # is discarded later
        regex = "(?:Execution|Clock)Time = ([0-9.]*) s"
        return float(self.get_latest_value_or_default(regex, chunk, 0.0))

    def get_SimTime(self, chunk):
        regex = "\nTime = ([0-9.e\-]*)"
        return float(self.get_latest_value_or_default(regex, chunk, 0.0))

    def get_header_value(self, key):
        ret =  re.findall("{: <7}: ([0-9A-Za-z]*)".format(key), self.cached_header)
        if ret:
            return ret[0]
        else:
            return None

    def text(self, filter_):
        lines = self.cache_body().split("\n")
        if filter_:
            return "\n".join([l for l in lines if filter_ in l])
        else:
            return "\n".join(lines)

    def print_log_body(self):
        sep_width = 120
        print(self.path)
        print("="*sep_width)
        if self.case.log_filter:
            lines = self.cached_body.split("\n")
            filt_lines = [l for l in lines if self.case.log_filter in l][-30:-1]
            body_str = ("\n".join(filt_lines))
        else:
            body_str = ("\n".join(self.cached_body.split("\n")[-30:-1]))
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
        return max(1e-12, self.elapsed_sim_time/max(1.0, self.wall_time))

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
                self.case.last_timestep_ondisk
              + self.case.writeInterval)

    def time_till(self, end):
        return self.remaining_sim_time(end)/(self.sim_speed)


