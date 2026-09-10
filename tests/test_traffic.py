import random

import pytest

from src.traffic_control import Phase, TrafficController


def controller(clock):
    return TrafficController(
        min_green_s=2,
        min_yellow_s=1,
        min_red_s=1,
        animal_crossing_hold_s=2,
        clear_s=1,
        max_crossing_s=5,
        clock=clock.monotonic,
    )


def green(clock, tc):
    tc.update(False)
    clock.advance(2)
    assert tc.update(False).phase == Phase.GREEN


def test_no_abrupt_stop_and_no_shortened_clearances(clock):
    tc = controller(clock)
    green(clock, tc)
    clock.advance(0.1)
    assert tc.update(True).phase == Phase.GREEN
    clock.advance(1.9)
    assert tc.update(True).phase == Phase.YELLOW
    clock.advance(0.9)
    assert tc.update(True, emergency_vehicle=True).phase == Phase.YELLOW
    clock.advance(0.2)
    assert tc.update(True).phase == Phase.RED
    clock.advance(0.9)
    assert tc.update(True).phase == Phase.RED
    clock.advance(0.2)
    assert tc.update(True).phase == Phase.ANIMAL_CROSSING


def test_continued_presence_never_releases_traffic(clock):
    tc = controller(clock)
    for _ in range(50):
        clock.advance(1)
        assert tc.update(True, emergency_vehicle=True).phase != Phase.GREEN
    assert tc.state.occupancy_overdue


def test_hold_restarts_after_last_seen(clock):
    tc = controller(clock)
    tc.update(True)
    clock.advance(1)
    tc.update(True)
    clock.advance(20)
    tc.update(True)
    clock.advance(0.5)
    assert tc.update(False).phase == Phase.ANIMAL_CROSSING
    clock.advance(1)
    assert tc.update(False).phase == Phase.RED
    clock.advance(1)
    assert tc.update(False).phase == Phase.GREEN


def test_emergency_cannot_bypass_fault_or_yellow(clock):
    tc = controller(clock)
    green(clock, tc)
    clock.advance(2)
    assert tc.update(False, healthy=False).phase == Phase.YELLOW
    clock.advance(0.5)
    assert tc.update(False, emergency_vehicle=True).phase == Phase.YELLOW
    clock.advance(0.5)
    assert tc.update(False, healthy=False).phase == Phase.RED
    clock.advance(1)
    assert tc.update(False, healthy=False, emergency_vehicle=True).phase == Phase.FAULT
    clock.advance(10)
    assert tc.update(False, healthy=False, emergency_vehicle=True).phase == Phase.FAULT


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_invalid_timing_rejected(bad):
    with pytest.raises(ValueError):
        TrafficController(min_yellow_s=bad)


def test_independent_clocks_and_instances(clock):
    first = controller(clock)
    clock.advance(100)
    second = controller(clock)
    assert first.state.last_change_s == 0
    assert second.state.last_change_s == 100


@pytest.mark.parametrize("seed", range(10))
def test_random_fault_sequences_preserve_phase_invariants(clock, seed):
    rng = random.Random(seed)
    tc = controller(clock)
    allowed = {
        Phase.GREEN: {Phase.GREEN, Phase.YELLOW},
        Phase.YELLOW: {Phase.YELLOW, Phase.RED},
        Phase.RED: {Phase.RED, Phase.GREEN, Phase.FAULT, Phase.ANIMAL_CROSSING},
        Phase.FAULT: {Phase.FAULT, Phase.RED},
        Phase.ANIMAL_CROSSING: {Phase.ANIMAL_CROSSING, Phase.FAULT, Phase.RED},
    }
    for _ in range(1000):
        previous = tc.state.phase
        changed = tc.state.last_change_s
        clock.advance(rng.uniform(0.01, 2))
        animal, healthy, held = (rng.random() < 0.4, rng.random() > 0.2, rng.random() < 0.1)
        state = tc.update(animal, healthy=healthy, manual_hold=held, emergency_vehicle=True)
        assert state.phase in allowed[previous]
        if previous != state.phase:
            if previous == Phase.GREEN:
                assert clock.t - changed >= 2
            if previous in (Phase.YELLOW, Phase.RED):
                assert clock.t - changed >= 1
        if state.phase == Phase.GREEN and previous != Phase.GREEN:
            assert healthy and not animal and not held
