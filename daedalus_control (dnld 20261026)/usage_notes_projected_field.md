---
title:  Daedalus Calibrations and Usage
author: Joseph Mittelstaedt
geometry: margin=2cm
---

# Calibrations & Usage of the Daedalus Projected Field Magnet

The methodology used in getting the requested field for the projected field
magnet is arcane so we explain it here.

The most recent calibration was ran in February 2019.

## Determining Field Orientation

- The field center cross on the setup is
always kept along the central axis of the magnet, defined as the line normal to
the plane of the magnet with the GMW sticker on it. We call this axis the y axis
since when phi=0 this is along the y axis of the Newport motion stage.
- There is a particular calibration for the X and Y coordinates of the motion
stage which sets the "center" of the magnet at the field center on the setup.
- When the magnet is in this position, the field produced at the cross is
entirely in-plane and the azimuthal angle phi can be set by rotating the magnet.
- To set an out-of-plane polar angle, the magnet is moved along the y axis which
causes the fringing part of the field to create an out-of-plane component of
the magnetic field. There is a calibration which gives the radial distance
you must move the magnet out to get the desired polar angle.
- Moving in the positive y direction creates a field with a downwards
out-of-plane component, and by symmetry moving in the negative y direction
creates a field flipped across the xy-plane (mostly).
- In the calibration, the polar angle is defined such that a completely
in-plane field has a polar angle of zero and an upwards directed field
completely out-of-plane has a polar angle of 90 deg.

### Negative Fields and Angles

- For a positive field, assuming phi=0, moving in +y yields
a B vector pointing downwards (towards the magnet) and moving in -y produces a
B vector pointing upwards (away from the magnet) as expected by symmetry.
- If a negative field is requested, the magnet moves to the same physical
position as it would if a positive field was being requested but runs current
in the opposite direction. Therefore, with a negative field strength the
magnetic field's polar angle will effectively change sign and its azimuthal
angle will rotate by 180 deg.
- If a negative polar angle with a positive field is requested, the magnet moves
(about) the same radial distance it would for the corresponding positive polar angle
but in the opposite direction. This keeps the azimuthal angle in the expected
direction.

## Determining Field Strength

There are two steps to determining the amount of current to supply to the magnet
to get a desired field strength.

1. The base voltage calibration directly returns
the voltage output from the DAQ (which controlls the magnet's power supply) as
a function of desired field strength, assuming the magnet is centered on the
mark
on the setup (i.e. magnetic field completely in-plane).
2. If an out-of-plane field is requested there is another calibration, a
function of the magnitude of the radial distance moved, which gives a
correction to the voltage. The voltage from the base calibration is divided by
this correction to give the appropriate voltage to give the desired field
strength.

### Strength Limitations

Because our control voltage to the power supply cannot exceed 10V, there is a
limit to the total magnetic field strength which depends on the radial distance
moved. Because the radial distance moved also affects the polar angle of the
field, there is a somewhat complicated dependence on the maximum in-plane and
out-of-plane field we can apply as a function of the polar angle requested.
A plot summarizing the limit with the most recent calibrations is shown below.

![Maximum magnetic field calibration](./daedalus_field_limits.png)

A more detailed look at the field strength calibrations, as well as how to
use these calibrations, is shown in the Jupyter notebook
`calibration_example.ipynb`.

## Usage Notes

Some tips for programming the magnet effectively:

- Moving the magnet is very time consuming in experiments. So, it is usually
better to have anything dealing with moving the magnet as the "outermost loop"
of your measurements. So if you are doing an STFMR measurement and want to sweep
dc bias, frequency, and azimuthal angle the angle sweep should be the "outer
loop."
- If you want to sweep the out of plane field and have an in-plane component
be static, the best way to do this is to keep the field sign positive always
and return negative polar angles. The in-plane component of the field will be
change the least in this way.

### Working with (or Against) the ESP300 Motion Controller

The Newport ESP300 motion controller has a difficult time dealing with GPIB
commands. We have enumerated some tips to keep in mind if you ever need to
write control code for it:

- Motion not done when it says it is, add extra delay
- Frequently gives PCIe timeout, should catch and re-try instead of having
whole application crash
- Should check that you've gotten to the expected position, sometimes does not
actually go where it says it has. Noticed mostly with phi axis.
- Check for errors often to clear the error buffer.
- Prepare for non-int error return codes
- Should try not to send commands too quickly, it can get confused

# Limitations of the Current Calibration

As it stands, the calibration has some limitations when it comes to applying an
out-of-plane field. To achieve a completely out-of-plane field, the magnet must
move a radial distance of 14.4 mm from the center of the calibration. However,
the center of the calibration is at (12.25,13.54) so clearly there will be
some azimuthal angles at which this will not work. Although for a completely
out-of-plane field this would not be an issue, for angles with a large polar
angle this could be a problem. With the current calibration, the largest polar
angle we can apply and have a full range of movement in the azimuthal direction
is 81 deg. We have supplied a sketch of the setup showing the problem. The
circle in the diagram represents the circle we would need to move around to
produce a completely out-of-plane field. All measurements are in mm.

![Sketch of Daedalus showing OOP field limitations](./daedalus_motion_limits.png)

NOTE: this sketch was done with the old calibration, the new calibration has
the field center at (12.02,14.425), and the radial distance to polar angle
calibration has changed. The current maximum polar angle which will work for
all azimuthal angles is 80 deg.

# Fixing the Motion Controller when Things Go Wrong

The Newport ESP300 is a hot pile of garbage and can get stuck easily. Here
is a list of ways we have seen things go quite wrong and how we can fix them

## Center Calibration Seems Wrong

Whenever the ESP300 is power-cycled, wherever the XY stages are when the
instrument is powered back on is where it will set the software zero. Since we
assume that zero is at the negative hardware limits of the motion stages, the
magnet will move to the wrong position. Instructions for fixing this are
given below. Values are given consistent with the most recent calibration.

Before starting any measurements, you should check that the magnet is:
in about the right position. There are two things to check:

- Check that the reading on the screen of the Newport is X=12.02, Y=14.425
- Check that the platform is actually in the right position. The X and Y stage
of the magnet's motion controller are each made of two plates, one base plate on
the bottom and another movable plate on top. When the magnet is appropriately
zeroed, these two plates should be right on top of one another. If something
is wrong they will probably be off by ~1cm.

If either of these things are wrong, you must reset the magnet. instructions for
that are below.

### Re-zeroing the magnet

1. Open the Anaconda prompt
2. type `python` to open a Python interpereter
3. Type the following commands in the interpreter:
```
from pymeasure.instruments.newport import ESP300
a = ESP300(10)
a.x.position = -100
a.y.position = -100
```
after this, wait for the Newport to stop moving. It should beep to let you
know that the X and Y stages have reached their negative hardware limits.
4. Now set the proper software zero:
```
a.x.zero()
a.y.zero()
a.x.position = 12.02
a.y.position = 14.425
quit()
```
6. Wait for the Newport to stop moving before doing any experiments.

## Motion Controller Stops Communicating

Another error that sometimes comes up is that the magnet will stop
communicating with the computer all together. Fixing this is a bit more
involved. Instructions are given below:

1. Restart the magnet by pressing the black power button twice. Wait for it
to finish restarting. All of the axes will probably be disabled, noted by
`off` being next to their readings on the controller.
2. open the Anaconda prompt
3. type `python` to open a Python interpereter
4. Type the following commands in the interpreter:
```
from pymeasure.instruments.newport import ESP300
a = ESP300(10)
a.enable()
```
5. Check that all of the axes are properly enabled, noted by `on` being next
to their measurements on the controller. If any are not on, try pressing the
white buttons next to the axis which should turn them on. If that doesn't work,
try running `a.enable()` again on the interpereter. If all else fails, restart
the controller again.
6. We now need to re-zero the controller again. To do this, continuing from
where we were on the interpereter before:
```
a.x.position = -100
a.y.position = -100
```
after this, wait for the Newport to stop moving. It should beep to let you
know that the X and Y stages have reached their negative hardware limits.
7. Now set the proper software zero:
```
a.x.zero()
a.y.zero()
a.x.position = 12.02
a.y.position = 14.425
quit()
```
8. Wait for the Newport to stop moving before doing any experiments.

## Motion Stages Stops Moving, Won't Respond

This happens sometimes, and the error which is returned is usually a
tracking error. When this happens, it will not attempt to move and will
probably be stuck at the positive hardware limit. Instructions to fix this
are given below, assuming that the y axis is stuck:

1. Using your hand, *slightly* turn the screw controlling the y axis. We just
want to get it back on track, so if it has moved too far positive twist the
screw in the "-" direction, and vice versa for the other way. It should only
move around 0.1 mm and may be quite hard to turn.
2. Follow the instructions for re-zeroing the magnet, although you may only
need to run the steps for the affected axis. Use your judgment.
