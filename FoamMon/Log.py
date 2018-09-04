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
        self.cached_body = self.cache_body()

    def get_ClockTime(self, chunk, last=True):
        try:
            return float(re.findall("ClockTime = ([0-9.]*) s", chunk)[-1])
        except:
            return 0.0


    def get_SimTime(self, chunk):
        try:
            return float(re.findall("\nTime = ([0-9.e\-]*)", chunk)[-1])
        except:
            return 0.0

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
                self.case.last_timestep
              + self.case.writeInterval)

    def time_till(self, end):
        return self.remaining_sim_time(end)/(self.sim_speed)


