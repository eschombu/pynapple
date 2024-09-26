"""Tests of correlograms for `pynapple` package."""

import pynapple as nap
import numpy as np
import pandas as pd
import pytest
from itertools import combinations

def test_cross_correlogram():
    t1 = np.array([0])
    t2 = np.array([1])
    cc, bincenter = nap.process.correlograms._cross_correlogram(t1, t2, 1, 100)
    np.testing.assert_approx_equal(cc[101], 1.0)

    cc, bincenter = nap.process.correlograms._cross_correlogram(t2, t1, 1, 100)
    np.testing.assert_approx_equal(cc[99], 1.0)

    t1 = np.array([0])
    t2 = np.array([100])
    cc, bincenter = nap.process.correlograms._cross_correlogram(t1, t2, 1, 100)
    np.testing.assert_approx_equal(cc[200], 1.0)

    t1 = np.array([0, 10])
    cc, bincenter = nap.process.correlograms._cross_correlogram(t1, t1, 1, 100)
    np.testing.assert_approx_equal(cc[100], 1.0)
    np.testing.assert_approx_equal(cc[90], 0.5)
    np.testing.assert_approx_equal(cc[110], 0.5)

    np.testing.assert_array_almost_equal(bincenter, np.arange(-100, 101))

    for t in [100, 200, 1000]:
        np.testing.assert_array_almost_equal(
            nap.process.correlograms._cross_correlogram(
                np.arange(0, t), np.arange(0, t), 1, t
            )[0],
            np.hstack(
                (np.arange(0, 1, 1 / t), np.ones(1), np.arange(0, 1, 1 / t)[::-1])
            ),
        )


#############################
# Type Error
#############################
def get_group():
    return nap.TsGroup(
        {
            0: nap.Ts(t=np.arange(0, 100)),
            # 1: nap.Ts(t=np.arange(0, 100)),
            # 2: nap.Ts(t=np.array([0, 10])),
            # 3: nap.Ts(t=np.arange(0, 200)),
        },
        time_support=nap.IntervalSet(0, 100),
    )


def get_ep():
    return nap.IntervalSet(start=0, end=100)


def get_event():
    return nap.Ts(t=np.arange(0, 100), time_support=nap.IntervalSet(0, 100))


@pytest.mark.parametrize(
    "func",
    [
        # nap.compute_autocorrelogram,
        # nap.compute_crosscorrelogram,
        nap.compute_eventcorrelogram
    ],
)
@pytest.mark.parametrize(
    "group, binsize, windowsize, ep, norm, time_units, msg",
    [
        (
            get_group(),
            "a",
            10,
            get_ep(),
            True,
            "s",
            "Invalid type. Parameter binsize must be of type <class 'numbers.Number'>.",
        ),
        (
            get_group(),
            1,
            "a",
            get_ep(),
            True,
            "s",
            "Invalid type. Parameter windowsize must be of type <class 'numbers.Number'>.",
        ),
        (
            get_group(),
            1,
            10,
            "a",
            True,
            "s",
            "Invalid type. Parameter ep must be of type <class 'pynapple.core.interval_set.IntervalSet'>.",
        ),
        (
            get_group(),
            1,
            10,
            get_ep(),
            "a",
            "s",
            "Invalid type. Parameter norm must be of type <class 'bool'>.",
        ),
        (
            get_group(),
            1,
            10,
            get_ep(),
            True,
            1,
            "Invalid type. Parameter time_units must be of type <class 'str'>.",
        ),
    ],
)
def test_correlograms_type_errors(
    func, group, binsize, windowsize, ep, norm, time_units, msg
):
    with pytest.raises(TypeError, match=msg):
        func(
            group=group,
            binsize=binsize,
            windowsize=windowsize,
            ep=ep,
            norm=norm,
            time_units=time_units,
        )


@pytest.mark.parametrize(
    "func, args, msg",
    [
        (
            nap.compute_autocorrelogram,
            ([1, 2, 3], 1, 1),
            "Invalid type. Parameter group must be of type TsGroup",
        ),
        (
            nap.compute_crosscorrelogram,
            ([1, 2, 3], 1, 1),
            r"Invalid type. Parameter group must be of type TsGroup or a tuple\/list of \(TsGroup, TsGroup\).",
        ),
        (
            nap.compute_crosscorrelogram,
            (([1, 2, 3]), 1, 1),
            r"Invalid type. Parameter group must be of type TsGroup or a tuple\/list of \(TsGroup, TsGroup\).",
        ),
        (
            nap.compute_crosscorrelogram,
            ((get_group(), [1, 2, 3]), 1, 1),
            r"Invalid type. Parameter group must be of type TsGroup or a tuple\/list of \(TsGroup, TsGroup\).",
        ),
        (
            nap.compute_crosscorrelogram,
            ((get_group(), get_group(), get_group()), 1, 1),
            r"Invalid type. Parameter group must be of type TsGroup or a tuple\/list of \(TsGroup, TsGroup\).",
        ),
        (
            nap.compute_eventcorrelogram,
            ([1, 2, 3], 1, 1),
            "Invalid type. Parameter group must be of type TsGroup",
        ),
    ],
)
def test_correlograms_type_errors_group(func, args, msg):
    with pytest.raises(TypeError, match=msg):
        func(*args)


@pytest.mark.parametrize(
    "func, args, msg",
    [
        (
            nap.compute_eventcorrelogram,
            (get_group(), [1, 2, 3], 1, 1),
            "Invalid type. Parameter event must be of type \(<class 'pynapple.core.time_series.Ts'>, <class 'pynapple.core.time_series.Tsd'>\).",
        ),
    ],
)
def test_correlograms_type_errors_event(func, args, msg):
    with pytest.raises(TypeError, match=msg):
        func(*args)


#################################################
# Normal tests
#################################################


@pytest.mark.parametrize(
    "group, binsize, windowsize, kwargs, expected",
    [
        (
            get_group(),
            1,
            100,
            {},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.zeros(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            1,
            100,
            {"norm": False},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.zeros(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            nap.TsGroup({1: nap.Ts(t=np.array([0, 10]))}),
            1,
            100,
            {"norm": False},
            np.hstack(
                (
                    np.zeros(90),
                    np.array([0.5]),
                    np.zeros((19)),
                    np.array([0.5]),
                    np.zeros((90)),
                )
            )[:, np.newaxis],
        ),
        (
            get_group(),
            1,
            100,
            {"ep": get_ep()},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.zeros(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            1,
            100,
            {"time_units": "s"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.zeros(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            1 * 1e3,
            100 * 1e3,
            {"time_units": "ms"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.zeros(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            1 * 1e6,
            100 * 1e6,
            {"time_units": "us"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.zeros(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
    ],
)
def test_autocorrelogram(group, binsize, windowsize, kwargs, expected):
    cc = nap.compute_autocorrelogram(group, binsize, windowsize, **kwargs)
    assert isinstance(cc, pd.DataFrame)
    assert list(cc.keys()) == list(group.keys())
    if "time_units" in kwargs:
        if kwargs["time_units"] == "ms":
            np.testing.assert_array_almost_equal(
                cc.index.values * 1e3,
                np.arange(-windowsize, windowsize + binsize, binsize),
            )
        if kwargs["time_units"] == "us":
            np.testing.assert_array_almost_equal(
                cc.index.values * 1e6,
                np.arange(-windowsize, windowsize + binsize, binsize),
            )
        if kwargs["time_units"] == "s":
            np.testing.assert_array_almost_equal(
                cc.index.values, np.arange(-windowsize, windowsize + binsize, binsize)
            )
    else:
        np.testing.assert_array_almost_equal(
            cc.index.values, np.arange(-windowsize, windowsize + binsize, binsize)
        )
    np.testing.assert_array_almost_equal(cc.values, expected)


@pytest.mark.parametrize(
    "group, event, binsize, windowsize, kwargs, expected",
    [
        (
            get_group(),
            get_event(),
            1,
            100,
            {},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            get_event(),
            1,
            100,
            {"norm": False},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            get_event(),
            1,
            100,
            {"ep": get_ep()},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            get_event(),
            1,
            100,
            {"time_units": "s"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            get_event(),
            1 * 1e3,
            100 * 1e3,
            {"time_units": "ms"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group(),
            get_event(),
            1 * 1e6,
            100 * 1e6,
            {"time_units": "us"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
    ],
)
def test_eventcorrelogram(group, event, binsize, windowsize, kwargs, expected):
    cc = nap.compute_eventcorrelogram(group, event, binsize, windowsize, **kwargs)
    assert isinstance(cc, pd.DataFrame)
    assert list(cc.keys()) == list(group.keys())
    if "time_units" in kwargs:
        if kwargs["time_units"] == "ms":
            np.testing.assert_array_almost_equal(
                cc.index.values * 1e3,
                np.arange(-windowsize, windowsize + binsize, binsize),
            )
        if kwargs["time_units"] == "us":
            np.testing.assert_array_almost_equal(
                cc.index.values * 1e6,
                np.arange(-windowsize, windowsize + binsize, binsize),
            )
        if kwargs["time_units"] == "s":
            np.testing.assert_array_almost_equal(
                cc.index.values, np.arange(-windowsize, windowsize + binsize, binsize)
            )
    else:
        np.testing.assert_array_almost_equal(
            cc.index.values, np.arange(-windowsize, windowsize + binsize, binsize)
        )
    np.testing.assert_array_almost_equal(cc.values, expected)


def get_group2():
    return nap.TsGroup(
        {
            0: nap.Ts(t=np.arange(0, 100)),
            1: nap.Ts(t=np.arange(0, 100)),
            # 2: nap.Ts(t=np.array([0, 10])),
            # 3: nap.Ts(t=np.arange(0, 200)),
        },
        time_support=nap.IntervalSet(0, 100),
    )


@pytest.mark.parametrize(
    "group, binsize, windowsize, kwargs, expected",
    [
        (
            get_group2(),
            1,
            100,
            {},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group2(),
            1,
            100,
            {"norm": False},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            (get_group(), get_group()),
            1,
            100,
            {},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group2(),
            1,
            100,
            {"ep": get_ep()},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            (get_group(), get_group()),
            1,
            100,
            {"ep": get_ep()},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            (get_group(), get_group()),
            1,
            100,
            {"norm": False},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group2(),
            1,
            100,
            {"time_units": "s"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group2(),
            1 * 1e3,
            100 * 1e3,
            {"time_units": "ms"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
        (
            get_group2(),
            1 * 1e6,
            100 * 1e6,
            {"time_units": "us"},
            np.hstack(
                (np.arange(0, 1, 1 / 100), np.ones(1), np.arange(0, 1, 1 / 100)[::-1])
            )[:, np.newaxis],
        ),
    ],
)
def test_crosscorrelogram(group, binsize, windowsize, kwargs, expected):
    cc = nap.compute_crosscorrelogram(group, binsize, windowsize, **kwargs)
    assert isinstance(cc, pd.DataFrame)
    if isinstance(group, nap.TsGroup):
        assert list(cc.keys()) == list(combinations(group.keys(), 2))
    else:
        assert list(cc.keys()) == [(0, 0)]
    if "time_units" in kwargs:
        if kwargs["time_units"] == "ms":
            np.testing.assert_array_almost_equal(
                cc.index.values * 1e3,
                np.arange(-windowsize, windowsize + binsize, binsize),
            )
        if kwargs["time_units"] == "us":
            np.testing.assert_array_almost_equal(
                cc.index.values * 1e6,
                np.arange(-windowsize, windowsize + binsize, binsize),
            )
        if kwargs["time_units"] == "s":
            np.testing.assert_array_almost_equal(
                cc.index.values, np.arange(-windowsize, windowsize + binsize, binsize)
            )
    else:
        np.testing.assert_array_almost_equal(
            cc.index.values, np.arange(-windowsize, windowsize + binsize, binsize)
        )
    np.testing.assert_array_almost_equal(cc.values, expected)


def test_crosscorrelogram_reverse():
    cc = nap.compute_crosscorrelogram(get_group2(), 1, 100, reverse=True)
    assert isinstance(cc, pd.DataFrame)
    assert list(cc.keys()) == [(1, 0)]
