# Sagnac 1 slow phi rotation: diagnostic handoff

Prepared: October 26, 2026  
Status: code and documentation inspection completed; no instrument connection or motion tests performed.

## Task for the receiving AI

Determine why Sagnac 1 rotates its magnet about phi much more slowly than the similar Daedalus setup. Establish whether the difference comes from controller settings, stage hardware/load, software overhead, or a combination. Explain any legitimate reason for the slow setting and recommend a specific next step supported by measurements and the correct stage documentation.

The user reports that Daedalus has fast phi rotation but slower magnetic-field-magnitude ramping than Sagnac 1. Treat these as separate observations; do not assume one is a necessary tradeoff for the other.

The user explicitly identified this Sagnac entry point:

`MinimalSagnac/sagnacMultitool/aparatus/sagnac1.py`

Current authorization was to inspect code and documentation, followed by preparation of this report. The user offered the possibility of connecting to the instrument computer later. This report does not authorize motion, field changes, homing, resetting, enabling motors, or controller-setting changes. When continuing on an instrument computer, start with an inspection of the existing session and read-only queries. Coordinate any subsequent physical tests with the user.

## Main conclusion so far

No explicit slow-phi rate setting was found in the inspected application code. Both implementations issue a direct absolute-position request for phi. Neither application initializes phi velocity, acceleration, deceleration, or trajectory mode. Different controller configurations or attached stages could therefore produce different physical speeds from essentially the same motion request.

MinimalSagnac adds blocking completion waits, but the inspected Daedalus scan procedure also waits for completion. This does not by itself explain much slower sustained physical rotation. Controller settings are the first useful thing to compare, followed by the rotation-stage model and its operating limits.

This is a hypothesis supported by the code structure, not a confirmed diagnosis. No live settings, actual slew speeds, or stage identities have been obtained.

## Repository locations and scope

Paths on the inspection computer:

```text
Sagnac repository:
/Users/orion/Documents/GitHub/SagnacOperatingSys

Downloaded Daedalus repository:
/Users/orion/Documents/GitHub/daedalus_control (dnld 20261026)
```

The parenthesized suffix is part of the actual Daedalus directory name. The shorter path `/Users/orion/Documents/GitHub/daedalus_control` did not exist on that computer.

Sagnac repository HEAD during inspection:

```text
45dab29f285a61c9cfaabf092091274c428afd49
```

Paths and installed packages on the instrument computer may differ. Confirm the actual running code before relying on these line numbers. There are several similarly named magnet drivers in the Sagnac repository; the entry point above imports `custom_instruments1.py`, not `custom_instruments.py` and not a vector-magnet driver.

## Evidence from the code

Line numbers below refer to the inspected files. Sagnac paths are relative to the Sagnac repository; Daedalus paths are relative to the downloaded Daedalus repository.

### 1. Actual Sagnac 1 import and instrument address

File: `MinimalSagnac/sagnacMultitool/aparatus/sagnac1.py`, lines 41–47.

```python
from .drivers.custom_instruments1 import daedalusProjField
from pymeasure.adapters import DAQmxAdapter

magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']), "GPIB::10")
magnet.load_calibration_params(calib_file)
```

Its calibration-file prefix is hardcoded to a Windows path under `SagnacOperatingSys/sagnac_control/calibrations/sagnac`.

The same apparatus module also constructs a separate `delayStage = ESP300(11)` at line 119. **The delay-stage controller is not the magnet controller.** Identify the magnet connection using the existing `magnet.motion_inst` object and the actual resource configuration.

### 2. Phi is sent as one absolute-position request

Sagnac driver: `MinimalSagnac/sagnacMultitool/aparatus/drivers/custom_instruments1.py`:

- Lines 144–148: `setPhi()` calls `set_vector_field(self._field, phi, self._theta)` and waits.
- Lines 306–334: `set_vector_field()` computes targets and assigns `self.motion_inst.phi.position = phi` if the cached angle differs.
- Lines 199–209: initialization enables axes, sets X/Y units to millimeters and phi units to degrees, and reads phi software limits. It does not configure motion speed or acceleration.

Daedalus driver: `daedalus/custom_instruments/daedalusProjField.py`:

- Lines 52–55: `setPhi()` calls `set_vector_field()`; it also applies `modular_range_bidirectional(phi, [-360., 360.])`.
- Lines 95–131: initialization similarly sets units and reads limits without configuring speed or acceleration.
- Lines 197–221: `set_vector_field()` directly assigns `self.motion_inst.phi.position = phi`.

Repository PyMeasure driver: `pymeasureMod/pymeasure/instruments/newport/esp300.py`:

- Lines 136–143: position read/write commands are `TP` and `PA%g`.
- Lines 188–194: the axis number prefixes each command.
- Lines 258–260: default axes are X = 1, Y = 2, phi = 3.

Thus this local driver turns a phi target into `3PA<angle>`. Neither magnet application subdivides a phi move into tiny Python-generated steps. Confirm the installed ESP300 implementation on each instrument computer; its source has not yet been inspected.

The absolute-target approach also means angle wraparound deserves attention if only some moves are unusually long. Do not assume an automatic shortest-path rotation. The Sagnac phi setter has a commented-out modular-range line. Do not add wrapping without checking physical travel, cable routing, and the intended angle convention.

### 3. Completion waits differ, but both scan paths wait

Sagnac driver locations:

- `setVolts()`, lines 117–128: ends with `wait_for_operation()`.
- `set_vector_field()`, lines 306–334: calls the voltage setter, then waits again.
- `setPhi()`, lines 144–148: waits again after `set_vector_field()` returns.
- `in_motion`, lines 178–183: checks completion of phi, X, and Y.
- `wait_for_operation()`, lines 397–401: polls motion status, sleeps 0.1 seconds while moving, then reads/logs errors.

The later waits are mostly redundant status and error queries once the first wait finishes. They add overhead and could expose communication problems, but do not instruct the motor to rotate more slowly.

Daedalus's driver does not contain these same blocking waits, but its `daedalus/procedures/AMRProcedure.py`, lines 109–115, explicitly waits for `magnet.in_motion` to become false, logs errors, then sleeps for experiment equilibration. Do not compare setter-return times as though they were physical move times.

The downloaded `usage_notes_projected_field.md`, lines 95–108, records historical ESP300 communication/completion problems, including timeouts, unreliable completion/position behavior, and problems when commands arrive too quickly. These are local operational observations, not a demonstrated reason for Sagnac's low physical slew speed.

### 4. A phi operation can include X/Y motion and voltage handling

Sagnac `angle_calibration()`, lines 276–286, computes:

```python
radial_dist = 0 if theta == 0 else self.radial_polar_calib(theta)
xloc = -radial_dist * np.sin(phi * np.pi / 180.) + self.centerX
yloc =  radial_dist * np.cos(phi * np.pi / 180.) + self.centerY
```

Daedalus uses the same form. At nonzero theta, changing phi can move X/Y as well as rotate the magnet. Sagnac waits for all axes, so the slowest axis can determine operation time. At theta zero, X/Y targets remain at the calibrated center; an initial recentering move may still be needed.

Both applications also invoke voltage handling during `set_vector_field()`, including a nominal phi-only change. At fixed B and theta the calculated voltage should remain the same, but a readback discrepancy can still trigger voltage steps. This is a possible source of extra operation time, not an established cause of slow physical rotation.

### 5. Magnetic-field ramping is a separate software path

Both magnet drivers initialize:

```python
self._voltage_step = 0.01
self._delay = 0.005
```

This corresponds to a nominal 2 V/s before task creation, device writes, scheduling, and other overhead. It is a command-voltage ramp, not a measured magnetic-field slew rate.

Sagnac uses `PyDAQmx` and creates/starts/stops/clears a task for each output increment. Daedalus's DAQ implementation uses `nidaqmx` task contexts for each increment. Daedalus also provides a Yokogawa voltage-source implementation. Confirm which implementation and any runtime overrides are actually in use before diagnosing the reported field-ramp difference.

Several downloaded Daedalus procedures, including `daedalus/procedures/Hall2HarmProcedure.py` around line 304, explicitly comment that the DAQ option is very slow. This supports investigating its voltage-output overhead separately. No code relationship was found requiring slow field ramping in exchange for fast phi rotation.

## Manufacturer documentation

Primary source: [Newport ESP300 Motion Controller/Driver User's Manual, P/N 28187-02 Rev. F](https://www.newport.com.cn/medias/sys_master/images/images/h2f/haa/8797091299358/ESP300-User-Manual.pdf).

Relevant printed sections: command descriptions in §3.6; load capacity and maximum velocity in §§5.2.11–12. `VA` is working velocity, `VU` its configured maximum; `AC`/`AG` set acceleration/deceleration; `AU` sets their maximum; `TJ` selects trajectory mode and `JK` controls S-curve jerk. `ID` reads stage identity. `TP` reads actual position; `TV` reads actual velocity; `MD?` reports motion completion. Speeds use configured displacement units per second.

The manual says usable maximum speed depends on the motion device and driver and discusses dynamic load limits during acceleration. It also notes that default maximum velocity can be conservative. This does not establish that this particular loaded magnet can use a higher setting.

The rotation-stage model could not be identified in the inspected code or notebook text. A defensible numerical phi-speed limit requires that model and its applicable controller/load specifications. Do not substitute specifications from another Newport rotary stage.

## Next diagnostic steps

### A. Identify the existing runtime without initializing apparatus

Use the existing experiment session if available. Record:

- Actual apparatus and magnet-driver source paths.
- Actual PyMeasure version and installed ESP300 source path.
- Magnet controller resource, controller model/firmware, and axis mapping.
- Stage identity/model label, including motor-option suffix, and any known external gearing.
- Whether the observation is slow physical rotation, slow command return, a pause before motion, a pause after motion, or slow point-to-point experiment throughput.
- A representative target-angle change, theta, field magnitude, and approximate observed duration.

**Do not import `aparatus.sagnac1` merely to inspect configuration.** It constructs hardware objects, enables axes through the magnet constructor, sets units, and connects other instruments. Avoid calling shutdown routines: the magnet shutdown method requests a field/position change. Inspect source files without executing them.

### B. Obtain a read-only controller snapshot

Start with the magnet's existing controller object. Confirm that its `ask()` method sends a query and reads the reply. Serialize communication with any running experiment; competing readers can consume each other's replies. Do not open a second competing controller session just to run this snippet.

The following example assumes the correct, already-connected `magnet` object exists. It does not construct an instrument or issue motion/settings commands. Review against the installed driver and firmware before use.

```python
import inspect
import json
import time
from datetime import datetime, timezone
from importlib import metadata

controller = magnet.motion_inst  # Existing magnet controller; not delayStage.

def source_path(cls):
    try:
        return inspect.getfile(cls)
    except (TypeError, OSError):
        return None

try:
    pymeasure_version = metadata.version("pymeasure")
except metadata.PackageNotFoundError:
    pymeasure_version = "distribution metadata unavailable"

snapshot = {
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "magnet_class": f"{type(magnet).__module__}.{type(magnet).__name__}",
    "magnet_source": source_path(type(magnet)),
    "controller_source": source_path(type(controller)),
    "pymeasure_version": pymeasure_version,
    "cached_field": getattr(magnet, "_field", None),
    "cached_theta": getattr(magnet, "_theta", None),
    "queries": [],
}

# Confirm axis mapping in the installed driver first.
commands = ["VE?"]
for axis in (1, 2, 3):
    commands.extend(
        f"{axis}{suffix}"
        for suffix in (
            "ID?", "SN?", "SU?", "VA?", "VU?", "AC?", "AG?",
            "AU?", "TJ?", "JK?", "SL?", "SR?", "TP", "MD?"
        )
    )

for command in commands:
    started = time.perf_counter()
    try:
        reply = controller.ask(command)
    except Exception as exc:
        snapshot["queries"].append({
            "command": command,
            "elapsed_s": time.perf_counter() - started,
            "error": f"{type(exc).__name__}: {exc}",
        })
        break  # Diagnose communication before issuing further queries.
    snapshot["queries"].append({
        "command": command,
        "reply": str(reply).strip(),
        "elapsed_s": time.perf_counter() - started,
    })
    time.sleep(0.2)  # Modest query rate; no motion is commanded.

print(json.dumps(snapshot, indent=2, default=str))
```

Run equivalent snapshots on both setups if possible, or obtain the Daedalus results from its operator. A large query latency is evidence about communication overhead, not directly about motor speed. If an identity query is unavailable, obtain the physical label.

Do not use `magnet.errors`, `clear_errors()`, `TE?`, or `TB?` in the initial snapshot: reading errors consumes entries in the controller's error queue. If error capture becomes relevant, explicitly record that it drains entries and preserve every returned value.

### C. Compare and interpret the evidence

| Evidence | Interpretation to investigate |
|---|---|
| Sagnac has much lower axis-3 `VA` | Direct candidate for slower travel speed; investigate why it was chosen. |
| Sagnac has low `VU` | Configured speed ceiling; this is not proof of the stage's physical maximum. |
| Similar `VA`, much lower `AC`/`AG` | Short moves may spend most of their time accelerating/decelerating. |
| Different `TJ`/`JK` | Trajectory shaping may change move duration, especially for short steps. |
| Different stage model, motor option, gearing, or load | Similar setups may have different physical operating limits. |
| Fast physical phi motion but long operation time | Examine X/Y motion, voltage-ramp work, communication, and settling waits. |
| Slow only at nonzero theta | Check simultaneous translation and which axis finishes last. |
| Slow only across particular angle transitions | Check absolute travel distance and angle-wrap conventions. |
| Normal configuration but unexpectedly low actual velocity | Examine tracking, mechanical load/drag, and relevant recorded errors. |

These are hypotheses for discrimination. Do not report them as observed faults until measured.

### D. Obtain timing evidence only within an agreed physical test

If the user authorizes a motion test, establish an appropriate angle interval, field condition, travel limits, and cable clearance with the operator. Prefer observing an already-planned normal move when possible.

Distinguish these events:

1. Target request issued.
2. Phi starts moving.
3. Actual phi position versus time, with modest-rate `3TP` sampling and optionally `3TV`.
4. Phi completion versus X/Y completion.
5. Voltage work and setter return.
6. Additional experiment equilibration delay.

Do not flood the controller with telemetry. Measure without changing speed first. Relate measured velocity and duration to the reported settings and stage specifications before proposing changes.

## Required outcome from the continuation

Return a concise diagnosis with:

1. Observed stage/controller identities, installed driver paths, and settings from each available setup.
2. Evidence separating physical rotation speed from software waiting and translation/voltage overhead.
3. The relevant stage speed/load specification, with a manufacturer source.
4. A confirmed cause or a ranked explanation with explicit remaining uncertainties.
5. A concrete proposed remedy or reason to retain the existing limit, including any measurements needed to validate it.

If only one setup is accessible, report what can be concluded from that setup and identify the specific missing comparison. Do not assume the faster setup's parameters are appropriate for Sagnac. Preserve the original configuration before any subsequently authorized edits, and distinguish temporary changes from settings saved to controller memory.

## Work already completed

- Traced the user-specified Sagnac 1 apparatus import through the magnet driver and repository ESP300 driver.
- Compared it with the downloaded Daedalus magnet implementation and a representative angular-scan procedure.
- Searched relevant Python, documentation, and notebook source/text for speed settings and rotary-stage identity; neither was found.
- Consulted the Newport ESP300 manual.
- No control code, calibration files, or hardware settings were changed. This handoff document is the only added artifact.
