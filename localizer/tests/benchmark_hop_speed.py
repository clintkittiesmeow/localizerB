from subprocess import call
import os
from localizer.wifi import get_first_interface
import timeit

DN = open(os.devnull, 'w')

num_loops = 500
default_hop_interval = 0.1

iface = get_first_interface()
channels = range(11)
curr_channel = 0


def change_channel():
    global curr_channel
    call(['iwconfig', iface, 'channel', str(channels[curr_channel])], stdout=DN, stderr=DN)
    curr_channel = (curr_channel + 1) % 11

total_time = timeit.timeit(change_channel, number=num_loops)
print("Average time: {} ({:.2f}x shorter than default_hop_interval)"
      .format(total_time/num_loops, default_hop_interval/(total_time/num_loops)))
