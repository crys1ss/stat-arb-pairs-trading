"""Unit tests for signal generation state machine using hand-built z sequences."""

import numpy as np
import pandas as pd
import pytest
from src.signals import generate_signals


def test_long_and_short_entries():
    # Long entry: z drops to -2.1 (<= -2.0)
    z_long = pd.Series([-0.5, -1.0, -2.1, -1.8])
    sig_long = generate_signals(z_long, entry_z=2.0, exit_z=0.5, max_hold_days=30)
    assert bool(sig_long.loc[2, "entry_flag"]) is True
    assert sig_long.loc[2, "state"] == 1
    assert sig_long.loc[2, "days_held"] == 1

    # Short entry: z spikes to +2.3 (>= 2.0)
    z_short = pd.Series([0.2, 1.2, 2.3, 1.9])
    sig_short = generate_signals(z_short, entry_z=2.0, exit_z=0.5, max_hold_days=30)
    assert bool(sig_short.loc[2, "entry_flag"]) is True
    assert sig_short.loc[2, "state"] == -1
    assert sig_short.loc[2, "days_held"] == 1


def test_mean_revert_exit_standard_and_jump_through_zero():
    # Case 1: Standard convergence
    # Bar 0: Enter short (z = 2.2)
    # Bar 1: Convergence to exit threshold (z = 0.4 <= 0.5)
    z_std = pd.Series([2.2, 0.4])
    sig_std = generate_signals(z_std, entry_z=2.0, exit_z=0.5, max_hold_days=30)
    assert bool(sig_std.loc[0, "entry_flag"]) is True
    assert sig_std.loc[0, "state"] == -1
    assert bool(sig_std.loc[1, "exit_flag"]) is True
    assert sig_std.loc[1, "exit_reason"] == "mean_revert"
    assert sig_std.loc[1, "state"] == 0

    # Case 2: Jump straight through zero
    # Long entered at z = -2.5 (Bar 0)
    # Next day z jumps directly to +0.8 (Bar 1, >= -0.5)
    z_jump = pd.Series([-2.5, 0.8])
    sig_jump = generate_signals(z_jump, entry_z=2.0, exit_z=0.5, max_hold_days=30)
    assert bool(sig_jump.loc[0, "entry_flag"]) is True
    assert sig_jump.loc[0, "state"] == 1
    assert bool(sig_jump.loc[1, "exit_flag"]) is True
    assert sig_jump.loc[1, "exit_reason"] == "mean_revert"
    assert sig_jump.loc[1, "state"] == 0


def test_max_hold_exit():
    # Enter long at bar 0, z oscillates between -1.5 and -0.8 (never >= -0.5)
    # With max_hold_days = 3:
    # Bar 0: days_held = 1
    # Bar 1: days_held = 2
    # Bar 2: days_held = 3 -> exits on max_hold!
    z_seq = pd.Series([-2.2, -1.5, -0.8, -0.6])
    sig = generate_signals(z_seq, entry_z=2.0, exit_z=0.5, max_hold_days=3)

    assert bool(sig.loc[0, "entry_flag"]) is True
    assert sig.loc[0, "state"] == 1
    assert sig.loc[0, "days_held"] == 1

    assert sig.loc[1, "state"] == 1
    assert sig.loc[1, "days_held"] == 2
    assert bool(sig.loc[1, "exit_flag"]) is False

    assert bool(sig.loc[2, "exit_flag"]) is True
    assert sig.loc[2, "exit_reason"] == "max_hold"
    assert sig.loc[2, "days_held"] == 3
    assert sig.loc[2, "state"] == 0


def test_no_reentry_on_exit_bar():
    # Bar 0: Enter short (z = 2.4)
    # Bar 1: z violently collapses to -2.8 (<= 0.5 triggers short exit, but also <= -2.0)
    # Invariant: NO re-entry on exit bar
    z_seq = pd.Series([2.4, -2.8, -2.8])
    sig = generate_signals(z_seq, entry_z=2.0, exit_z=0.5, max_hold_days=30)

    # Bar 0: entry short
    assert bool(sig.loc[0, "entry_flag"]) is True
    assert sig.loc[0, "state"] == -1

    # Bar 1: exit short, no entry long on same bar
    assert bool(sig.loc[1, "exit_flag"]) is True
    assert sig.loc[1, "exit_reason"] == "mean_revert"
    assert bool(sig.loc[1, "entry_flag"]) is False
    assert sig.loc[1, "state"] == 0

    # Bar 2: can now enter long on subsequent bar
    assert bool(sig.loc[2, "entry_flag"]) is True
    assert sig.loc[2, "state"] == 1


def test_nan_handling():
    # Bar 0: NaN while flat -> remains flat
    # Bar 1: Enter long (z = -2.1)
    # Bar 2: NaN while holding -> existing position is held
    # Bar 3: Mean revert (z = 0.0)
    z_seq = pd.Series([np.nan, -2.1, np.nan, 0.0])
    sig = generate_signals(z_seq, entry_z=2.0, exit_z=0.5, max_hold_days=30)

    # Bar 0: flat
    assert sig.loc[0, "state"] == 0
    assert bool(sig.loc[0, "entry_flag"]) is False

    # Bar 1: long entry
    assert bool(sig.loc[1, "entry_flag"]) is True
    assert sig.loc[1, "state"] == 1
    assert sig.loc[1, "days_held"] == 1

    # Bar 2: held through NaN
    assert sig.loc[2, "state"] == 1
    assert bool(sig.loc[2, "entry_flag"]) is False
    assert bool(sig.loc[2, "exit_flag"]) is False
    assert sig.loc[2, "days_held"] == 2

    # Bar 3: exit
    assert bool(sig.loc[3, "exit_flag"]) is True
    assert sig.loc[3, "state"] == 0


def test_stop_loss():
    # Long entered at z = -2.1
    # Next bar divergence accelerates to z = -3.8 (stop_z = 3.5)
    z_seq = pd.Series([-2.1, -3.8])
    sig = generate_signals(z_seq, entry_z=2.0, exit_z=0.5, max_hold_days=30, stop_z=3.5)

    assert bool(sig.loc[0, "entry_flag"]) is True
    assert sig.loc[0, "state"] == 1
    assert bool(sig.loc[1, "exit_flag"]) is True
    assert sig.loc[1, "exit_reason"] == "stop"
    assert sig.loc[1, "state"] == 0


def test_causality_invariant():
    # Truncating the input at bar t MUST leave every state up to t strictly unchanged
    rng = np.random.default_rng(42)
    n = 50
    # Create realistic z-score sequence with entries, exits, stops, NaNs
    raw_z = rng.standard_normal(n) * 1.5
    raw_z[10] = -2.5
    raw_z[15] = 0.0
    raw_z[20] = 2.4
    raw_z[23] = np.nan
    raw_z[28] = 0.2

    full_sig = generate_signals(raw_z, entry_z=2.0, exit_z=0.5, max_hold_days=10, stop_z=3.0)

    # Test causality for every truncation point t
    for t in [5, 12, 22, 35, 45]:
        truncated_z = raw_z[:t]
        trunc_sig = generate_signals(truncated_z, entry_z=2.0, exit_z=0.5, max_hold_days=10, stop_z=3.0)

        # Invariant: states and flags up to t must match full output exactly
        np.testing.assert_array_equal(trunc_sig["state"].values, full_sig["state"].values[:t])
        np.testing.assert_array_equal(trunc_sig["entry_flag"].values, full_sig["entry_flag"].values[:t])
        np.testing.assert_array_equal(trunc_sig["exit_flag"].values, full_sig["exit_flag"].values[:t])
        np.testing.assert_array_equal(trunc_sig["days_held"].values, full_sig["days_held"].values[:t])
