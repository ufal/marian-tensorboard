#!/usr/bin/env python3

import tensorboardX as tb
import sys
import time
import calendar
import os
import pickle

def get_wall_time(date_str, time_str):
    return calendar.timegm(time.strptime(date_str+" "+time_str,
            "%Y-%m-%d %H:%M:%S"))

class JobMonitor():

    def __init__(self, job_path):

        self.job_path = job_path
        self.tb_logdir = job_path + "/tb"

        self.train_log = job_path + "/model/train.log"
        self.last_update_time = 0
        self.last_update_line = -1
        self.gpus = 0
        self.sen_last = 0
        self.last_wall_time = None
        self.gaps = 0
        self.avg_gaps = 0
        self.gaps_num = 0

        self.avg_status = {}

        self.pickle_file = self.tb_logdir + "/monitor-status.pickle"
        if os.path.exists(self.pickle_file):
            with open(self.pickle_file, "rb") as f:
                self.last_update_time, self.last_update_line, self.gpus, self.sen_last, self.avg_status, self.last_wall_time, self.gaps, self.avg_gaps, self.gaps_num = pickle.load(f)

        self.writer = tb.SummaryWriter(self.tb_logdir)

    def wall_time_minus_gaps(self, wall_time):
        if self.last_wall_time is None:
            self.last_wall_time = wall_time
            return wall_time
        thisgap = wall_time - self.last_wall_time


        if thisgap > 1200: # 20 minutes
            self.gaps += (thisgap - self.avg_gaps)
        else:
            self.gaps_num += 1
            self.avg_gaps = ((self.avg_gaps*(self.gaps_num-1)) + thisgap) / self.gaps_num

        self.last_wall_time = wall_time
        return wall_time - self.gaps

    def parse_train(self, line):
        strdate, strtime, *_ = line.split()
        wall_time = get_wall_time(strdate[1:], strtime[:-1])
        real_wall_time = wall_time
        wall_time = self.wall_time_minus_gaps(wall_time)

        words = line.split()
        strdate, strtime, _ep, ep, _, _up, up, *rest = words
        ep = int(ep)
        up = int(up)
        self.writer.add_scalar("train/epoch",ep,up, wall_time)

        self.writer.add_scalar("train/wall-clock",real_wall_time, up, real_wall_time)

        _, _sen, sen, _, _cost, cost, *rest = rest
        sen = sen.replace(",","")
        sen = int(sen)
        cost = float(cost)

        self.writer.add_scalar("train/sentences",sen, up, wall_time)
        self.writer.add_scalar("train/sentences-diff",sen-self.sen_last, up, wall_time)
        self.sen_last = sen

        self.writer.add_scalar("train/cost",cost, up, wall_time)

        _, _time, t, _, speed, _words_per_sec, *rest = rest
        t = float(t[:-1])
        self.writer.add_scalar("train/time[sec]", t, up, wall_time)

        speed = float(speed)

        self.writer.add_scalar("train/speed[words per sec]", speed, up, wall_time)

        try:
            _, _g_norm, g_norm, _, _lr, lr = rest
            lr = float(lr)
            self.writer.add_scalar("train/learning_rate", lr, up, wall_time)
        except ValueError:
            _, _g_norm, g_norm = rest

        g_norm = float(g_norm)
        self.writer.add_scalar("train/g-norm", g_norm, up, wall_time)
        self.writer.add_scalar("train/gpus", self.gpus, up, wall_time)

        return up

    def parse_valid(self, line):
        strdate, strtime, *_ = line.split()
        wall_time = get_wall_time(strdate[1:], strtime[:-1])
        wall_time = self.wall_time_minus_gaps(wall_time)

        _, _, _, _ep, ep, _, _up, up, _, metric, _, value, _, _stalled, x, *_times = line.split()
        up = int(up)
        value = float(value)
        self.writer.add_scalar("valid/"+metric, value, up, wall_time)
        if x == "best":
            x = 0
        else:
            x = int(x)
        self.writer.add_scalar("valid/"+metric+"_stalled", x, up, wall_time)

    def save_last_update(self):
        t = os.path.getmtime(self.train_log)
        self.last_update_time = t

        with open(self.pickle_file, "wb") as f:
            pickle.dump((self.last_update_time, self.last_update_line, self.gpus, self.sen_last, self.avg_status, self.last_wall_time, self.gaps, self.avg_gaps, self.gaps_num),f)


    def update_needed(self):
        t = os.path.getmtime(self.train_log)
        if t > self.last_update_time:
            print(" current modification time:",t, "last:", self.last_update_time)
            return True
        return False




    def update_loop(self):

        self.update_all_avg()

        if not self.update_needed():
            #print("  no update needed")
            return

        with open(self.train_log, "r") as f:
            for i,line in enumerate(f):
                if i <= self.last_update_line:
                    continue
#                print("processing line ",i, self.train_log)

                if "--devices" in line:
                    self.gpus = 0
                    words = line.split()
                    for w in words[words.index("--devices")+1:]:
                        try:
                            int(w)
                        except:
                            break
                        self.gpus += 1
                elif "] Ep. " in line and "[valid]" not in line:
                    up = self.parse_train(line)
                elif "] Ep. " in line and "[valid]" in line:
                    self.parse_valid(line)
        self.last_update_line = i
        print("last line id:",self.last_update_line)
        self.save_last_update()



    # This assumes some files like "avg-8.log" exist in model directory. If not, this does nothing.
    def update_all_avg(self):

        for fn in os.listdir(self.job_path+"/model"):
            if not fn.startswith("avg-"): continue
            if not fn.endswith(".log"): continue

            name = fn.replace(".log","")

            with open(self.job_path+"/model/"+fn) as f:
                if name not in self.avg_status:
                    self.avg_status[name] = -1
                for line in f:
                    label, *score = line.split()
                    try:
                        step = int(label.split("-")[2])
                    except:
                        continue
                    if step <= self.avg_status[name]:
                        continue
                    if not score:
                        continue
                    score = float(score[0])
                    self.writer.add_scalar("valid-avg/"+name+"_bleu", score, step)
                    self.avg_status[name] = step





monitors = {}

while True:
    with open("tb-monitored-jobs","r") as f:
        monitored = set()
        # create new monitors
        for line in f:
            line = line.strip()
            if line not in monitors:
                if os.path.exists(line+"/model/train.log"):
                    m = JobMonitor(line)
                    monitors[line] = m
                else:
                    print("path %s does not exist, skipping" % (line+"/model/train.log"))

            monitored.add(line)
        # delete unregistered monitors
        for k in list(monitors.keys()):
            if k not in monitored:
                del monitors[k]

    # update all monitors
    for j,m in monitors.items():
        print("update loop", j)
        m.update_loop()

#    break
    time.sleep(5)

