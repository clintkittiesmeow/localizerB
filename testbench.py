import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

enable_pin = 18
coil_A_1_blk = 4
coil_A_2_grn = 17
coil_B_1_red = 23
coil_B_2_blu = 24

GPIO.setup(enable_pin, GPIO.OUT)
GPIO.setup(coil_A_1_blk, GPIO.OUT)
GPIO.setup(coil_A_2_grn, GPIO.OUT)
GPIO.setup(coil_B_1_red, GPIO.OUT)
GPIO.setup(coil_B_2_blu, GPIO.OUT)

GPIO.output(enable_pin, 1)

seq = [[1,1,0,0],
       [0,1,1,0],
       [0,0,1,1],
       [1,0,0,1]]

seq_position = 0

def move(delay, steps):
    global seq_position

    if steps < 0:
        direction = -1
        steps = -steps
    else:
        direction = 1

    for step in range(0, steps):
        GPIO.output(coil_A_1_blk, step[0])
        GPIO.output(coil_B_1_red, step[1])
        GPIO.output(coil_A_2_grn, step[2])
        GPIO.output(coil_B_2_blu, step[3])

        seq_position = (seq_position + direction) % 4
        time.sleep(delay)


if __name__ == "__main__":
    while True:
        rpm = input("How quickly would you like to rotate? (RPMs) ")
        delay = int(rpm) * 400/60
        degrees = input("How many degrees? ")
        steps = round(int(degrees) / .9)



