from queue import Queue
from threading import Event
from localizer.antenna import AntennaStepperThread

degrees = 360
bearing = 0
durations = [1, 5, 30, 60, 120]
actual = []

queue_command = Queue()
queue_response = Queue()
flag = Event()

thread = AntennaStepperThread(queue_command, queue_response, flag)
thread.start()

for i in range(0, len(durations)):
    # Set up command
    command = (durations[1], degrees, bearing)
    queue_command.put(command)

    # Execute thread
    flag.set()
    queue_command.join()

    # Get results
    loop_start_time, loop_stop_time, loop_expected_time, loop_average_time = queue_response.get()
    actual.append((loop_average_time-loop_expected_time)/loop_expected_time)
    queue_response.task_done()

    # Print results
    print("Duration: {:>6}s - Response Time: {:>.2%}".format(durations[i], actual[i]))
