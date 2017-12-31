import pigpio

pi = pigpio.pi('192.168.137.68', 8888)
GPIO = 18
pi.set_mode(18, pigpio.OUTPUT)




def generate_ramp(ramp):
    """Generate ramp wave forms.
    ramp:  List of [Frequency, Steps]
    """
    pi.wave_clear()     # clear existing waves
    length = len(ramp)  # number of ramp levels
    wid = [-1] * length

    # Generate a wave per ramp level
    for i in range(length):
        frequency = ramp[i][0]
        micros = int(1000000 / frequency)
        wf = []
        wf.append(pigpio.pulse(1 << GPIO, 0, micros))  # pulse on
        wf.append(pigpio.pulse(0, 1 << GPIO, micros))  # pulse off
        pi.wave_add_generic(wf)
        wid[i] = pi.wave_create()

    # Generate a chain of waves
    chain = []
    for i in range(length):
        steps = ramp[i][1]
        x = steps & 255
        y = steps >> 8
        chain += [255, 0, wid[i], 255, 1, x, y]

    pi.wave_chain(chain)  # Transmit chain.

# Ramp up
generate_ramp([[320, 200],
	       [500, 400],
	       [800, 500],
	       [1000, 700],
	       [1600, 900],
	       [2000, 10000]])