"""Feedback Data Latency model for PQSC, SHF- and HDAWG systems.

Typical usage example:
```python
model = QCCSFeedbackModel(
    description=get_feedback_system_description(
        generator_type=SGType.HDAWG,
        analyzer_type=QAType.SHFQA,
        trigger_source=TriggerSource.ZSYNC,
        pqsc_mode=PQSCMode.DECODER
    )
)
```
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import IntEnum

import numpy as np


class SGType(IntEnum):
    """Different signal generator types used in a QCCS setup."""

    HDAWG = 1
    SHFSG = 2
    SHFQC = 3


class QAType(IntEnum):
    """Different quantum analyzer types used in a QCCS setup."""

    SHFQA = 1
    SHFQC = 2


class PQSCMode(IntEnum):
    """Different handling of feedback data from the PQSC."""

    REGISTER_FORWARD = 1
    DECODER = 2


class TriggerSource(IntEnum):
    """Different trigger sources for the QA and SG channels."""

    ZSYNC = 1
    INTERNAL = 2


class FeedbackPath(IntEnum):
    """Different handling of feedback data from the PQSC.

    .. versionadded:: 0.3
    """

    ZSYNC = 1
    INTERNAL = 3


MINIMUM_SAMPLES_INTEGRATION_LENGTH = 4
MINIMUM_SAMPLES_INTEGRATION_DELAY = 16
MINIMUM_SAMPLES_UNTIL_READOUT_COMPLETE = (
    MINIMUM_SAMPLES_INTEGRATION_LENGTH + MINIMUM_SAMPLES_INTEGRATION_DELAY
)


@dataclass
class QCCSSystemDescription:
    """Describe the behavior of a QCCS system with respect to feedback latency."""

    initial_latency_cycles: int
    """[clock cycles] Minimum latency for the smallest amount of
    integration length."""
    initial_steps: int
    """[steps] Integration length increment steps, until the
    first latency increment."""
    pattern: list[tuple[int, int]]
    """[(clock cycles, steps),...] The pattern of periodic
    latency increments with respect to integration length increments """
    period_steps: int = 50
    """[steps] Period of the latency increment pattern."""
    latency_in_period_cycles: int = 25
    """[clock cycles] Latency increment for a full period."""
    rtlogger_correction: int = 0
    """[clock cycles] Correction needed on top of the RTLogger recorded
    latency, to match the latency seen by the sequencer"""


def get_feedback_system_description(  # noqa: C901, PLR0912
    generator_type: SGType,
    analyzer_type: QAType,
    pqsc_mode: PQSCMode | None = None,
    trigger_source: TriggerSource = TriggerSource.ZSYNC,
    feedback_path: FeedbackPath = FeedbackPath.ZSYNC,
) -> QCCSSystemDescription:
    """Returns a QCCSSysDescription object for a given configuration.

    Args:
      generator_type: Signal generator used (SHFSG/HDAWG).
      analyzer_type: Quantum analyzer used.
      pqsc_mode: Mode of operation for the PQSC.
      trigger_source: Select between ZSync via PQSC or internal trigger for the SHFQC.
      feedback_path: Used only when the generator type is SHFQC to select
                     between local feedback or through PQSC

    Returns:
      A QCCS system description object to be used in a `QCCSFeedbackModel` object.

    Raises:
      ValueError: Incorrect values for 'generator_type', 'analyzer_type',
                  'pqsc_mode' or 'feedback_path'.

    .. versionchanged:: 0.3

        Added `feedback_path` argument.
    """
    if analyzer_type not in [QAType.SHFQA, QAType.SHFQC]:
        msg = f"Unknown quantum analyzer type ({analyzer_type})"
        raise ValueError(msg)

    if pqsc_mode in [PQSCMode.DECODER, PQSCMode.REGISTER_FORWARD] and (
        feedback_path is FeedbackPath.INTERNAL
        or trigger_source is TriggerSource.INTERNAL
    ):
        msg = (
            f"PQSC mode ({pqsc_mode.name}) incompatible with "
            f"selected feedback path ({feedback_path.name}) "
            f"and/or trigger source ({trigger_source.name})"
        )
        raise ValueError(msg)

    if generator_type is SGType.HDAWG:
        if feedback_path == FeedbackPath.INTERNAL:
            msg = "Internal Feedback can only be used with generator=SGType.SHFQC"
            raise ValueError(msg)
        if trigger_source == TriggerSource.INTERNAL:
            msg = "Internal trigger can only be used with generator=SGType.SHFQC"
            raise ValueError(msg)
        if pqsc_mode is PQSCMode.REGISTER_FORWARD:
            return QCCSSystemDescription(
                initial_latency_cycles=100,
                initial_steps=7,
                pattern=[(4, 8), (5, 8), (4, 9), (4, 8), (4, 8), (4, 9)],
                rtlogger_correction=2,
            )
        if pqsc_mode is PQSCMode.DECODER:
            return QCCSSystemDescription(
                initial_latency_cycles=104,
                initial_steps=8,
                pattern=[(5, 9), (4, 8), (4, 8), (4, 9), (4, 8), (4, 8)],
                rtlogger_correction=2,
            )
        msg = f"Unknown PQSC mode ({pqsc_mode})"
        raise ValueError(msg)

    if generator_type in [SGType.SHFSG, SGType.SHFQC]:
        if feedback_path is FeedbackPath.INTERNAL:
            if generator_type != SGType.SHFQC:
                msg = "Internal Feedback can only be used with generator=SGType.SHFQC"
                raise ValueError(msg)
            if analyzer_type != QAType.SHFQC:
                msg = "Internal Feedback can only be used with analyzer=QAType.SHFQC"
                raise ValueError(msg)
            if pqsc_mode is not None:
                msg = (
                    f"Internal Feedback can't be used with "
                    f"the selected pqsc mode ({pqsc_mode})"
                )

                raise ValueError(msg)
            if (
                trigger_source is TriggerSource.ZSYNC
            ):  # internal feedback with ZSync trigger
                return QCCSSystemDescription(
                    initial_latency_cycles=30,
                    initial_steps=1,
                    pattern=[(1, 2)] * 25,
                    rtlogger_correction=2,
                )

            # internal feedback with internal trigger
            return QCCSSystemDescription(
                initial_latency_cycles=27,
                initial_steps=1,
                pattern=[(1, 2)] * 25,
            )

        if pqsc_mode is PQSCMode.REGISTER_FORWARD:
            return QCCSSystemDescription(
                initial_latency_cycles=95,
                initial_steps=7,
                pattern=[(5, 8), (5, 8), (3, 9), (5, 8), (5, 8), (2, 9)],
                rtlogger_correction=2,
            )
        if pqsc_mode is PQSCMode.DECODER:
            return QCCSSystemDescription(
                initial_latency_cycles=100,
                initial_steps=8,
                pattern=[(5, 9), (3, 8), (5, 8), (5, 9), (2, 8), (5, 8)],
                rtlogger_correction=2,
            )
        msg = f"Unknown PQSC mode ({pqsc_mode})"
        raise ValueError(msg)

    msg = f"Unknown signal generator type ({generator_type})"
    raise ValueError(msg)


@dataclass
class QCCSFeedbackModel:
    """A model that calculates the latency of feedback data.

    Estimates are provided for the selected Signal Generator.
    The 'start trigger' from the PQSC is used as starting point for
    the latency estimate.

    Args:
      description: The QCCS system configuration description as returned
                   from get_feedback_system_description()
    """

    description: QCCSSystemDescription

    def get_latency(
        self,
        samples: int = 20,
        length: int | None = None,
    ) -> int:
        """Provide the expected latency relative to the integration length.

        Args:
            samples:
              The number of samples from the trigger to the completion of the
              integration. This includes the samples up to the `startQA()`
              command, plus the integration length and delay.
            length: Deprecated

        Returns:
          The expected latency in AWG clock cycles
        """
        if samples is None:
            samples = length
            if length is not None:
                msg = (
                    "'length' is a deprecated argument.",
                    " User 'samples_until_integration_complete' instead",
                )
                warnings.warn(msg, category=DeprecationWarning, stacklevel=1)
        if samples < MINIMUM_SAMPLES_UNTIL_READOUT_COMPLETE:
            msg = "samples_until_integration_complete must be at least 20"
            raise ValueError(msg)

        # before the periodic pattern
        model = np.array(
            [self.description.initial_latency_cycles] * self.description.initial_steps,
            dtype=np.int64,
        )

        # build the periodic pattern
        periodic_mdl = np.array([], dtype=np.int64)
        acc = 0
        for lat_inc, int_steps in self.description.pattern:
            acc += lat_inc
            periodic_mdl = np.concatenate(
                (periodic_mdl, np.array([acc] * int_steps, dtype=np.int64)),
                dtype=np.int64,
            )

        # from integration samples to generator cc
        def f_calculate_cycles() -> int:
            index = (samples - MINIMUM_SAMPLES_INTEGRATION_DELAY) // 4
            if index <= self.description.initial_steps:
                return int(model[index - 1])

            index -= self.description.initial_steps + 1
            lat_full_periods = (
                index // self.description.period_steps
            ) * self.description.latency_in_period_cycles  # latency from full periods
            index = (
                index % self.description.period_steps
            )  # remainder within the periodic pattern
            # total latency
            return int(
                self.description.initial_latency_cycles
                + periodic_mdl[index]
                + lat_full_periods,
            )

        latency_clk = f_calculate_cycles()

        return int(latency_clk + self.description.rtlogger_correction)
