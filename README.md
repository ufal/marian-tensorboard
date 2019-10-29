# marian-tensorboard parser

A simple script for parsing marian training logs and displaying them as scalars in tensorboard. For visual monitoring and comparison.

## Install

- `virtualenv -p python3 p3`
- `source p3/bin/activate`
- `pip install tensorboardX tensorboard`

## Run

Assume you have a directory containing one or more Marian NMT trainings to compare. They have structure like this:

```
.
├── src-tgt-demo-1
│   └── model
│       └── train.log    # tb_log_parser.py requires train.log created by marian on this path. Other files such as checkpoints and running scripts can be present nearby.
├── src-tgt-demo-2
│   └── model
│       └── train.log    # and similarly here
├── ...                  # there can be more runs
│
├── tb_log_parser.py      
└── tb-monitored-jobs    # tb_log_parser.py requires this in the same directory 
```

If you have active trainings in `src-tgt-demo-1` and `src-tgt-demo-2`, register them for monitoring by including the names into `tb-monitored-jobs` file, so it looks like this:

```
$ cat tb-monitored-jobs 
src-tgt-demo-1
src-tgt-demo-2
```


Then you can run the log parser:

```
$ ./tb_log_parser.py 
update loop src-tgt-demo-1
 current modification time: 1572357911.0 last: 0
last line id: 26122
update loop src-tgt-demo-2
 current modification time: 1572358555.0 last: 0
update loop src-tgt-demo-1
update loop src-tgt-demo-2
update loop src-tgt-demo-1
update loop src-tgt-demo-2
```

It will go through `tb-monitored-jobs`, and for each monitored job, it parses data from the lines of train.log, which newly appeared after last update loop, saves the values in tensorboard-readable format into src-tgt-demo-1/tb directory, together with pickled variables for restoring current parsing state. The logs are revisited every 5 seconds. You can update tb-monitored-jobs meanwhile to add or remove monitored jobs.

Let it running in the terminal window, open new terminal, `source p3/bin/activate`, `tensorboard --logdir=. --port=6006`. Wait until it writes it's ready, then open a webbrowser, go to localhost:6006 and analyze.

## Demo

Install, follow the steps in Run section above and observe some training and validation scalars in tensorboard in your browser. Two sample train.log files are included in this repo.

## FAQ

TODO

There are many points and features to explain. Feel free to ask Dominik :)
