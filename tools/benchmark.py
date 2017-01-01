from __future__ import print_function
import sys
import json
import time
import numpy as np
import re
import shutil
import os
import glob
from matplotlib import pyplot as plt
from tf_ec2 import tf_ec2_run, Cfg

def load_cfg_from_file(cfg_file):
    cfg_f = open(cfg_file, "r")
    return eval(cfg_f.read())

def shutdown_and_launch(cfg):
    shutdown_args = "tools/tf_ec2.py shutdown"
    tf_ec2_run(shutdown_args.split(), cfg)

    launch_args = "tools/tf_ec2.py launch"
    tf_ec2_run(launch_args.split(), cfg)

def run_tf_and_download_files(run_time_sec, cfg, evaluator_file_name="out_evaluator", master_file_name="out_master", outdir="result_dir"):

    kill_args = "tools/tf_ec2.py kill_all_python"
    tf_ec2_run(kill_args.split(), cfg)
    time.sleep(10)

    run_args = "tools/tf_ec2.py run_tf"
    cluster_specs = tf_ec2_run(run_args.split(), cfg)
    cluster_string = cluster_specs["cluster_string"]

    time.sleep(run_time_sec)

    tf_ec2_run(kill_args.split(), cfg)

    time.sleep(10)

    download_evaluator_file_args = "tools/tf_ec2.py download_file %s %s %s" % (cluster_string, evaluator_file_name, outdir)
    tf_ec2_run(download_evaluator_file_args.split(), cfg)

    download_master_file_args = "tools/tf_ec2.py download_file %s %s %s" % (cluster_string, master_file_name, outdir)
    tf_ec2_run(download_master_file_args.split(), cfg)

def extract_compute_times(fname):
    f = open(fname)

    compute_times = []
    for line in f:
        m = re.match(".*ELAPSED TIMES (.*)", line)
        if m:
            compute_times = json.loads(m.group(1))
    f.close()
    return compute_times

def extract_times_losses_precision(fname):
    f = open(fname)

    times, losses, precisions, steps = [], [], [], []
    for line in f:
        m = re.match("Num examples: ([0-9]*)  Precision @ 1: ([\.0-9]*) Loss: ([\.0-9]*) Time: ([\.0-9]*)", line)
        step_match = re.match(".* step=([0-9]*)", line)
        if m:
            examples, precision, loss, time = int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
            times.append(time)
            losses.append(loss)
            precisions.append(precision)
        if step_match:
            step = int(step_match.group(1))
            steps.append(step)
    f.close()
    min_length = min([len(x) for x in [times, losses, precisions, steps]])
    return times[:min_length], losses[:min_length], precisions[:min_length], steps[:min_length]

def plot_time_precision(outdir):
    plt.cla()
    plt.xlabel("time (s)")
    plt.ylabel("precision (%)")
    files = glob.glob(outdir + "/*evaluator*")
    cmap = plt.get_cmap('jet')
    colors = cmap(np.linspace(0, 1.0, len(files)))
    for i, fname in enumerate(files):
        label = fname.split("/")[-1]
        times, losses, precisions, steps = extract_times_losses_precision(fname)
        plt.plot(times, precisions, linestyle='solid', label=label, color=colors[i])
    plt.legend(loc="upper right", fontsize=8)
    plt.savefig("time_precision.png")

def plot_step_loss(outdir):
    plt.cla()
    plt.xlabel("step")
    plt.ylabel("losses")
    files = glob.glob(outdir + "/*evaluator*")
    cmap = plt.get_cmap('jet')
    colors = cmap(np.linspace(0, 1.0, len(files)))
    plt.yscale('log')
    #plt.xscale('log')
    for i, fname in enumerate(files):
        label = fname.split("/")[-1]
        times, losses, precisions, steps = extract_times_losses_precision(fname)
        plt.plot(steps, losses, linestyle='solid', label=label, color=colors[i])
    plt.legend(loc="upper right", fontsize=8)
    plt.savefig("step_losses.png")

def plot_time_loss(outdir):
    plt.cla()
    plt.xlabel("time (s)")
    plt.ylabel("loss")
    files = glob.glob(outdir + "/*evaluator*")
    cmap = plt.get_cmap('jet')
    colors = cmap(np.linspace(0, 1.0, len(files)))
    plt.yscale('log')
    #plt.xscale('log')
    for i, fname in enumerate(files):
        label = fname.split("/")[-1]
        times, losses, precisions, steps = extract_times_losses_precision(fname)
        plt.plot(times, losses, linestyle='solid', label=label, color=colors[i])
    plt.legend(loc="upper right", fontsize=8)
    plt.savefig("time_loss.png")

def plot_time_step(outdir):
    plt.cla()
    plt.xlabel("time (s)")
    plt.ylabel("step")
    files = glob.glob(outdir + "/*evaluator*")
    cmap = plt.get_cmap('jet')
    colors = cmap(np.linspace(0, 2.0, len(files)))
    for i, fname in enumerate(files):
        label = fname.split("/")[-1]
        times, losses, precisions, steps = extract_times_losses_precision(fname)
        #print(times, losses, precisions, steps)
        plt.plot(times, steps, linestyle='solid', label=label, color=colors[i])
    plt.legend(loc="upper left", fontsize=8)
    plt.savefig("time_step.png")

def plot_time_cdfs(outdir):
    plt.cla()
    plt.xlabel("Time (s)")
    plt.ylabel("P(X >= x)")
    files = glob.glob(outdir + "/*master*")
    cmap = plt.get_cmap('jet')
    colors = cmap(np.linspace(0, 2.0, len(files)))
    for i, fname in enumerate(files):
        label = fname.split("/")[-1]
        compute_times = extract_compute_times(fname)
        compute_times.sort()

        times = []
        probabs = []
        for compute_time in compute_times:
            times.append(compute_time)
            probabs.append(sum([1 if compute_time <= t else 0 for t in compute_times]) / float(len(compute_times)))
        plt.plot(times, probabs, linestyle='solid', label=label, color=colors[i])
    plt.legend(loc="upper right", fontsize=8)
    plt.savefig("time_pdfs.png")

def plot_figs(cfgs, evaluator_file_name="out_evaluator", outdir="result_dir", time_limit=3*60, rerun=True, launch=False, need_shutdown_after_every_run=False):
    print([x["name"] for x in cfgs])
    if rerun:
        if launch:
            shutdown_and_launch(cfgs[0])
        for cfg in cfgs:
            if need_shutdown_after_every_run:
                shutdown_and_launch(cfg)
            run_tf_and_download_files(time_limit, cfg, evaluator_file_name=evaluator_file_name, outdir=outdir)

    plot_time_loss(outdir)
    plot_time_step(outdir)
    plot_time_precision(outdir)
    plot_step_loss(outdir)
    plot_time_cdfs(outdir)

if __name__ == "__main__":
    print("Usage: python benchmark.py [use_dir dir|select_files cfg1 cfg2...] ")
    cfgs = []
    if len(sys.argv) >= 2:
        if sys.argv[1] == "use_dir":
            cfg_dir = sys.argv[2]
            cfg_filenames = glob.glob(cfg_dir + "/*")
            cfgs = [str(x) for x in cfg_filenames]
            cfgs = [load_cfg_from_file(x) for x in cfgs]
        elif sys.argv[1] == "select_files":
            cfgs = [load_cfg_from_file(x) for x in sys.argv[2:]]
    plot_figs(cfgs)
