# -*- coding: utf-8 -*-
# @Author: gviejo
# @Date:   2022-01-30 22:59:00
# @Last Modified by:   Guillaume Viejo
# @Last Modified time: 2023-11-20 12:08:15

import numpy as np
from scipy.linalg import hankel

from .. import core as nap


def _align_tsd(tsd, tref, window, time_support):
    """
    Helper function compiled with numba for aligning times.
    See compute_perievent for using this function

    Parameters
    ----------
    times : numpy.ndarray
        The timestamps to align
    data : numpy.ndarray
        The data to align
    tref : numpy.ndarray
        The reference times
    windowsize : tuple
        Start and end of the window size around tref

    Returns
    -------
    list
        The align times and data
    """
    lbounds = np.searchsorted(tsd.index, tref.index - window[0])
    rbounds = np.searchsorted(tsd.index, tref.index + window[1])

    group = {}

    if isinstance(tsd, nap.Ts):
        for i in range(len(tref)):
            tmp = tsd.index[lbounds[i] : rbounds[i]] - tref.index[i]
            group[i] = nap.Ts(t=tmp, time_support=time_support)
    else:
        for i in range(len(tref)):
            tmp = tsd.index[lbounds[i] : rbounds[i]] - tref.index[i]
            tmp2 = tsd.values[lbounds[i] : rbounds[i]]
            group[i] = nap.Tsd(t=tmp, d=tmp2, time_support=time_support)

    group = nap.TsGroup(group, time_support=time_support, bypass_check=True)
    group.set_info(ref_times=tref.index)

    return group


def compute_perievent(data, tref, minmax, time_unit="s"):
    """
    Center ts/tsd/tsgroup object around the timestamps given by the tref argument.
    minmax indicates the start and end of the window.

    Parameters
    ----------
    data : Ts/Tsd/TsGroup
        The data to align to tref.
        If Ts/Tsd, returns a TsGroup.
        If TsGroup, returns a dictionnary of TsGroup
    tref : Ts/Tsd
        The timestamps of the event to align to
    minmax : tuple or int or float
        The window size. Can be unequal on each side i.e. (-500, 1000).
    time_unit : str, optional
        Time units of the minmax ('s' [default], 'ms', 'us').

    Returns
    -------
    dict
        A TsGroup if data is a Ts/Tsd or
        a dictionnary of TsGroup if data is a TsGroup.

    Raises
    ------
    RuntimeError
        if tref is not a Ts/Tsd object or if data is not a Ts/Tsd or TsGroup
    """
    if not isinstance(tref, (nap.Ts, nap.Tsd)):
        raise RuntimeError("tref should be a Tsd object.")

    if isinstance(minmax, float) or isinstance(minmax, int):
        minmax = np.array([minmax, minmax], dtype=np.float64)

    window = np.abs(nap.TsIndex.format_timestamps(np.array(minmax), time_unit))

    time_support = nap.IntervalSet(start=-window[0], end=window[1])

    if isinstance(data, nap.TsGroup):
        toreturn = {}

        for n in data.index:
            toreturn[n] = _align_tsd(data[n], tref, window, time_support)

        return toreturn

    elif isinstance(data, (nap.Ts, nap.Tsd)):
        return _align_tsd(data, tref, window, time_support)

    else:
        raise RuntimeError("Unknown format for data")


def compute_event_trigger_average(
    group, feature, binsize, windowsize, ep, time_units="s"
):
    """
    Bin the spike train in binsize and compute the Spike Trigger Average (STA) within windowsize.
    If C is the spike count matrix and feature is a Tsd array, the function computes
    the Hankel matrix H from windowsize=(-t1,+t2) by offseting the Tsd array.

    The STA is then defined as the dot product between H and C divided by the number of spikes.

    Parameters
    ----------
    group : TsGroup
        The group of Ts/Tsd objects that hold the trigger time.
    feature : Tsd
        The 1-dimensional feature to average. Can be a TsdFrame with one column only.
    binsize : float
        The bin size. Default is second.
        If different, specify with the parameter time_units ('s' [default], 'ms', 'us').
    windowsize : tuple or list of float
        The window size. Default is second. For example (-1, 1).
        If different, specify with the parameter time_units ('s' [default], 'ms', 'us').
    ep : IntervalSet
        The epoch on which STA are computed
    time_units : str, optional
        The time units of the parameters. They have to be consistent for binsize and windowsize.
        ('s' [default], 'ms', 'us').

    Returns
    -------
    TsdFrame
        A TsdFrame of Spike-Trigger Average. Each column is an element from the group.

    Raises
    ------
    RuntimeError
        if group is not a Ts/Tsd or TsGroup
    """
    if type(group) is not nap.TsGroup:
        raise RuntimeError("Unknown format for group")

    if isinstance(feature, nap.TsdFrame):
        if feature.shape[1] == 1:
            feature = feature[:, 0]

    if type(feature) is not nap.Tsd:
        raise RuntimeError("Feature should be a Tsd or a TsdFrame with one column")

    binsize = nap.TsIndex.format_timestamps(
        np.array([binsize], dtype=np.float64), time_units
    )[0]
    start = np.abs(
        nap.TsIndex.format_timestamps(
            np.array([windowsize[0]], dtype=np.float64), time_units
        )[0]
    )
    end = np.abs(
        nap.TsIndex.format_timestamps(
            np.array([windowsize[1]], dtype=np.float64), time_units
        )[0]
    )
    idx1 = -np.arange(0, start + binsize, binsize)[::-1][:-1]
    idx2 = np.arange(0, end + binsize, binsize)[1:]
    time_idx = np.hstack((idx1, np.zeros(1), idx2))

    count = group.count(binsize, ep)

    tmp = feature.bin_average(binsize, ep)

    # Check for any NaNs in feature
    if np.any(np.isnan(tmp)):
        tmp = tmp.dropna()
        count = count.restrict(tmp.time_support)

    # Build the Hankel matrix
    n_p = len(idx1)
    n_f = len(idx2)
    pad_tmp = np.pad(tmp, (n_p, n_f))
    offset_tmp = hankel(pad_tmp, pad_tmp[-(n_p + n_f + 1) :])[0 : len(tmp)]

    sta = np.dot(offset_tmp.T, count.values)

    sta = sta / np.sum(count, 0)

    sta = nap.TsdFrame(t=time_idx, d=sta, columns=group.index)

    return sta
