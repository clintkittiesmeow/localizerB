from queue import Queue
from threading import Event

from localizer.antenna import AntennaStepperThread

degrees = 360
bearing = 0
durations = [1, 5, 30, 60, 120]
actual = []

queue_response = Queue()
flag = Event()

for i in range(0, len(durations)):
    # Set up thread
    thread = AntennaStepperThread(queue_response, flag, durations[i], degrees, bearing, False)
    thread.start()

    # Execute thread
    flag.set()
    flag.clear()

    # Get results
    loop_start_time, loop_stop_time, loop_expected_time, loop_average_time = queue_response.get()
    actual.append((loop_average_time-loop_expected_time)/loop_expected_time)
    queue_response.task_done()
    thread.join()

    # Print results
    print("Duration: {:>6}s - Response Time: {:>.2%}".format(durations[i], actual[i]))
