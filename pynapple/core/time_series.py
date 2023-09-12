# -*- coding: utf-8 -*-
# @Author: gviejo
# @Date:   2022-01-27 18:33:31
# @Last Modified by:   Guillaume Viejo
# @Last Modified time: 2023-09-12 10:39:40

import importlib
import os
import warnings

import numpy as np
import pandas as pd
from pandas.core.internals import BlockManager, SingleBlockManager

from .interval_set import IntervalSet
from .jitted_functions import (
    jitbin,
    jitbin_array,
    jitcount,
    jitrestrict,
    jitthreshold,
    jittsrestrict,
    jittsrestrict_with_count,
    jitvaluefrom,
    jitvaluefromtsdframe,
)
from .time_units import format_timestamps, return_timestamps, sort_timestamps

from numbers import Number
from numpy.lib.mixins import NDArrayOperatorsMixin
from typing import TYPE_CHECKING, Optional, Tuple, Union, Any, SupportsIndex

import abc

class _BaseTsd(abc.ABC):

    def __init__(self):
        pass

    @property
    def t(self):
        return self.index

    @property
    def start(self):
        return self.start_time()

    @property
    def end(self):
        return self.end_time()

    @property
    def shape(self):
        return self.values.shape

    def times(self, units="s"):
        """
        The time index of the Tsd, returned as np.double in the desired time units.

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.ndarray
            the time indexes
        """
        return return_timestamps(self.index, units)



class Tsd(NDArrayOperatorsMixin):
    """
    A subclass of pandas.Series specialized for neurophysiology time series.

    Tsd provides standardized time representation, plus various functions for manipulating times series.

    Attributes
    ----------
    rate : float
        Frequency of the time series (Hz) computed over the time support
    time_support : IntervalSet
        The time support of the time series
    """

    def __init__(self, t, d=None, time_units="s", time_support=None, **kwargs):
        """
        Tsd Initializer.

        Parameters
        ----------
        t : numpy.ndarray or pandas.Series
            An object transformable in a time series, or a pandas.Series equivalent (if d is None)
        d : numpy.ndarray, optional
            The data of the time series
        time_units : str, optional
            The time units in which times are specified ('us', 'ms', 's' [default])
        time_support : IntervalSet, optional
            The time support of the tsd object
        **kwargs
            Arguments that will be passed to the pandas.Series initializer.
        """
        if isinstance(t, pd.Series):
            d = t.values
            t = t.index

        if isinstance(t, Number):
            t = np.array([t])
        if isinstance(d, Number):
            d = np.array([d])

        if not isinstance(d, np.ndarray):
            d = np.empty_like(t)

        t = t.astype(np.float64).flatten()
        t = format_timestamps(t, time_units)
        t = sort_timestamps(t)

        if len(t):
            if time_support is not None:
                starts = time_support.start.values
                ends = time_support.end.values
                if d is not None:
                    t, d = jitrestrict(t, d, starts, ends)
                    self.index = t
                    self.values = d
                else:
                    t = jittsrestrict(t, starts, ends)
                    self.index = t
                    self.values = np.array([])
            else:
                time_support = IntervalSet(start=t[0], end=t[-1])
                self.index = t
                self.values = d

            self.time_support = time_support
            self.rate = t.shape[0] / np.sum(
                time_support.values[:, 1] - time_support.values[:, 0]
            )

        else:
            time_support = IntervalSet(pd.DataFrame(columns=["start", "end"]))
            self.index = np.array([])
            self.values = np.array([])
            self.time_support = time_support
            self.rate = 0.0

        self.nap_class = self.__class__.__name__
        self.dtype = self.values.dtype

    @property
    def t(self):
        return self.index

    @property
    def start(self):
        return self.start_time()

    @property
    def end(self):
        return self.end_time()

    @property
    def shape(self):
        return self.values.shape

    def __repr__(self):
        # TODO repr for all dtypes
        upper = "Time (s)"
        _str_ = "\n".join(
            [
                "{:.6f}".format(i) + "    " + "{:.6f}".format(j)
                for i, j in zip(self.index, self.values)
            ]
        )
        bottom = "Length: {}".format(len(self.index)) + ", dtype: {}".format(self.dtype)
        return "\n".join((upper, _str_, bottom))

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, key):
        """
        Performs the operation __getitem__.
        """
        try:
            data = self.values.__getitem__(key)
            index = self.index.__getitem__(key)
            return Tsd(t=index, d=data)
        except:
            raise IndexError

    def __setitem__(self, key, value):
        """
        Performs the operation __getitem__.
        """
        try:
            self.values.__setitem__(key, value)
        except:
            raise IndexError

    def __len__(self):
        return len(self.index)

    def __array__(self, dtype=None):
        return self.values.astype(dtype)

    def __array_ufunc__(self, ufunc, method, *args, **kwargs):
        print("In __array_ufunc__")
        print("     ufunc = ", ufunc)
        print("     method = ", method)
        print("     args = ", args)
        for inp in args: print(type(inp))
        print("     kwargs = ", kwargs)

        if method == "__call__":
            new_args = []
            for a in args:
                if isinstance(a, Number):
                    new_args.append(a)
                elif isinstance(a, self.__class__):
                    new_args.append(a.values)
                else:
                    return NotImplemented

            out = ufunc(*new_args, **kwargs)
            # print("output = ", out)
            return self.__class__(self.index, out)

        else:
            return NotImplemented

    def __array_function__(self, func, types, args, kwargs):
        print("In __array_function__")
        print("     func = ", func)
        print("     types = ", types)
        print("     args = ", args)
        print("     kwargs = ", kwargs)

        new_args = []
        for a in args:
            if isinstance(a, Tsd):
                new_args.append(a.values)
            else:
                new_args.append(a)
        output = func._implementation(*args, **kwargs)

        return output

    def times(self, units="s"):
        """
        The time index of the Tsd, returned as np.double in the desired time units.

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.ndarray
            the time indexes
        """
        return return_timestamps(self.index, units)

    def as_series(self):
        """
        Convert the Ts/Tsd object to a pandas.Series object.

        Returns
        -------
        out: pandas.Series
            _
        """
        return pd.Series(index=self.index, data=self.values, copy=True, dtype="float64")

    def as_array(self):
        """
        Convert the Ts/Tsd object to a numpy.ndarray

        Returns
        -------
        out: pandas.Series
            _
        """
        return self.values

    def as_units(self, units="s"):
        """
        Returns a pandas Series with time expressed in the desired unit.

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        pandas.Series
            the series object with adjusted times
        """
        ss = self.as_series()
        t = self.index
        t = return_timestamps(self.index, units)
        if units == "us":
            t = t.astype(np.int64)
        ss.index = t
        ss.index.name = "Time (" + str(units) + ")"
        return ss

    def data(self):
        """
        The data in the Tsd object

        Returns
        -------
        out: numpy.ndarray
            _
        """
        return self.values

    def value_from(self, data, ep=None):
        """
        Replace the value with the closest value from Tsd/TsdFrame argument
        If data is TsdFrame, the output is also TsdFrame.

        Parameters
        ----------
        data : Tsd/TsdFrame
            The Tsd/TsdFrame object holding the values to replace.
        ep : IntervalSet (optional)
            The IntervalSet object to restrict the operation.
            If None, the time support of the tsd input object is used.

        Returns
        -------
        out : Tsd/TsdFrame
            Object with the new values

        Examples
        --------
        In this example, the ts object will receive the closest values in time from tsd.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100))) # random times
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> tsd = nap.Tsd(t=np.arange(0,1000), d=np.random.rand(1000), time_units='s')
        >>> ep = nap.IntervalSet(start = 0, end = 500, time_units = 's')

        The variable ts is a time series object containing only nan.
        The tsd object containing the values, for example the tracking data, and the epoch to restrict the operation.

        >>> newts = ts.value_from(tsd, ep)

        newts is the same size as ts restrict to ep.

        >>> print(len(ts.restrict(ep)), len(newts))
            52 52
        """
        if isinstance(data, Tsd):
            if ep is None:
                ep = data.time_support
            time_array = self.index
            time_target_array = data.index
            data_target_array = data.values
            starts = ep.start.values
            ends = ep.end.values
            t, d, ns, ne = jitvaluefrom(
                time_array, time_target_array, data_target_array, starts, ends
            )
            time_support = IntervalSet(start=ns, end=ne)

            return Tsd(t=t, d=d, time_support=time_support)

        elif isinstance(data, TsdFrame):
            if ep is None:
                ep = data.time_support
            time_array = self.index
            time_target_array = data.index
            data_target_array = data.values
            starts = ep.start.values
            ends = ep.end.values
            t, d, ns, ne = jitvaluefromtsdframe(
                time_array, time_target_array, data_target_array, starts, ends
            )
            time_support = IntervalSet(start=ns, end=ne)

            return TsdFrame(t=t, d=d, time_support=time_support, columns=data.columns)
        else:
            raise RuntimeError("The time series to align to should be Tsd/TsdFrame.")

    def restrict(self, ep):
        """
        Restricts a Tsd object to a set of time intervals delimited by an IntervalSet object

        Parameters
        ----------
        ep : IntervalSet
            the IntervalSet object

        Returns
        -------
        out: Tsd
            Tsd object restricted to ep

        Examples
        --------
        The Ts object is restrict to the intervals defined by ep.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100)))
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> ep = nap.IntervalSet(start=0, end=500, time_units='s')
        >>> newts = ts.restrict(ep)

        The time support of newts automatically inherit the epochs defined by ep.

        >>> newts.time_support
        >>>    start    end
        >>> 0    0.0  500.0

        """
        time_array = self.index
        data_array = self.values
        starts = ep.start.values
        ends = ep.end.values
        t, d = jitrestrict(time_array, data_array, starts, ends)
        return Tsd(t=t, d=d, time_support=ep)

    def count(self, *args, **kwargs):
        """
        Count occurences of events within bin_size or within a set of bins defined as an IntervalSet.
        You can call this function in multiple ways :

        1. *tsd.count(bin_size=1, time_units = 'ms')*
        -> Count occurence of events within a 1 ms bin defined on the time support of the object.

        2. *tsd.count(1, ep=my_epochs)*
        -> Count occurent of events within a 1 second bin defined on the IntervalSet my_epochs.

        3. *tsd.count(ep=my_bins)*
        -> Count occurent of events within each epoch of the intervalSet object my_bins

        4. *tsd.count()*
        -> Count occurent of events within each epoch of the time support.

        bin_size should be seconds unless specified.
        If bin_size is used and no epochs is passed, the data will be binned based on the time support of the object.

        Parameters
        ----------
        bin_size : None or float, optional
            The bin size (default is second)
        ep : None or IntervalSet, optional
            IntervalSet to restrict the operation
        time_units : str, optional
            Time units of bin size ('us', 'ms', 's' [default])

        Returns
        -------
        out: Tsd
            A Tsd object indexed by the center of the bins.

        Examples
        --------
        This example shows how to count events within bins of 0.1 second.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100)))
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> bincount = ts.count(0.1)

        An epoch can be specified:

        >>> ep = nap.IntervalSet(start = 100, end = 800, time_units = 's')
        >>> bincount = ts.count(0.1, ep=ep)

        And bincount automatically inherit ep as time support:

        >>> bincount.time_support
        >>>    start    end
        >>> 0  100.0  800.0
        """
        bin_size = None
        if "bin_size" in kwargs:
            bin_size = kwargs["bin_size"]
            if isinstance(bin_size, int):
                bin_size = float(bin_size)
            if not isinstance(bin_size, float):
                raise ValueError("bin_size argument should be float.")
        else:
            for a in args:
                if isinstance(a, (float, int)):
                    bin_size = float(a)

        time_units = "s"
        if "time_units" in kwargs:
            time_units = kwargs["time_units"]
            if not isinstance(time_units, str):
                raise ValueError("time_units argument should be 's', 'ms' or 'us'.")
        else:
            for a in args:
                if isinstance(a, str) and a in ["s", "ms", "us"]:
                    time_units = a

        ep = self.time_support
        if "ep" in kwargs:
            ep = kwargs["ep"]
            if not isinstance(ep, IntervalSet):
                raise ValueError("ep argument should be IntervalSet")
        else:
            for a in args:
                if isinstance(a, IntervalSet):
                    ep = a

        time_array = self.index
        starts = ep.start.values
        ends = ep.end.values

        if isinstance(bin_size, (float, int)):
            bin_size = float(bin_size)
            bin_size = format_timestamps(np.array([bin_size]), time_units)[0]
            t, d = jitcount(time_array, starts, ends, bin_size)
            time_support = IntervalSet(start=starts, end=ends)
            return Tsd(t=t, d=d, time_support=time_support)
        else:
            _, countin = jittsrestrict_with_count(time_array, starts, ends)
            t = starts + (ends - starts) / 2
            return Tsd(t=t, d=countin, time_support=ep)

    def bin_average(self, bin_size, ep=None, time_units="s"):
        """
        Bin the data by averaging points within bin_size
        bin_size should be seconds unless specified.
        If no epochs is passed, the data will be binned based on the time support.

        Parameters
        ----------
        bin_size : float
            The bin size (default is second)
        ep : None or IntervalSet, optional
            IntervalSet to restrict the operation
        time_units : str, optional
            Time units of bin size ('us', 'ms', 's' [default])

        Returns
        -------
        out: Tsd
            A Tsd object indexed by the center of the bins and holding the averaged data points.

        Examples
        --------
        This example shows how to bin data within bins of 0.1 second.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> tsd = nap.Tsd(t=np.arange(100), d=np.random.rand(100))
        >>> bintsd = tsd.bin_average(0.1)

        An epoch can be specified:

        >>> ep = nap.IntervalSet(start = 10, end = 80, time_units = 's')
        >>> bintsd = tsd.bin_average(0.1, ep=ep)

        And bintsd automatically inherit ep as time support:

        >>> bintsd.time_support
        >>>    start    end
        >>> 0  10.0     80.0
        """
        if not isinstance(ep, IntervalSet):
            ep = self.time_support

        bin_size = format_timestamps(np.array([bin_size]), time_units)[0]

        time_array = self.index
        data_array = self.values
        starts = ep.start.values
        ends = ep.end.values
        t, d = jitbin(time_array, data_array, starts, ends, bin_size)
        time_support = IntervalSet(start=starts, end=ends)
        return Tsd(t=t, d=d, time_support=time_support)

    def threshold(self, thr, method="above"):
        """
        Apply a threshold function to the tsd to return a new tsd
        with the time support being the epochs above/below/>=/<= the threshold

        Parameters
        ----------
        thr : float
            The threshold value
        method : str, optional
            The threshold method (above/below/aboveequal/belowequal)

        Returns
        -------
        out: Tsd
            All the time points below/ above/greater than equal to/less than equal to the threshold

        Raises
        ------
        ValueError
            Raise an error if method is not 'below' or 'above'
        RuntimeError
            Raise an error if thr is too high/low and no epochs is found.

        Examples
        --------
        This example finds all epoch above 0.5 within the tsd object.

        >>> import pynapple as nap
        >>> tsd = nap.Tsd(t=np.arange(100), d=np.random.rand(100))
        >>> newtsd = tsd.threshold(0.5)

        The epochs with the times above/below the threshold can be accessed through the time support:

        >>> tsd = nap.Tsd(t=np.arange(100), d=np.arange(100), time_units='s')
        >>> tsd.threshold(50).time_support
        >>>    start   end
        >>> 0   50.5  99.0

        """
        time_array = self.index
        data_array = self.values
        starts = self.time_support.start.values
        ends = self.time_support.end.values
        if method not in ["above", "below", "aboveequal", "belowequal"]:
            raise ValueError(
                "Method {} for thresholding is not accepted.".format(method)
            )

        t, d, ns, ne = jitthreshold(time_array, data_array, starts, ends, thr, method)
        time_support = IntervalSet(start=ns, end=ne)
        return Tsd(t=t, d=d, time_support=time_support)

    def to_tsgroup(self):
        """
        Convert Tsd to a TsGroup by grouping timestamps with the same values.
        By default, the values are converted to integers.

        Examples
        --------
        >>> import pynapple as nap
        >>> import numpy as np
        >>> tsd = nap.Tsd(t = np.array([0, 1, 2, 3]), d = np.array([0, 2, 0, 1]))
        Time (s)
        0.0    0
        1.0    2
        2.0    0
        3.0    1
        dtype: int64

        >>> tsd.to_tsgroup()
        Index    rate
        -------  ------
            0    0.67
            1    0.33
            2    0.33

        The reverse operation can be done with the TsGroup.to_tsd function :

        >>> tsgroup.to_tsd()
        Time (s)
        0.0    0.0
        1.0    2.0
        2.0    0.0
        3.0    1.0
        dtype: float64

        Returns
        -------
        TsGroup
            Grouped timestamps

        """
        ts_group = importlib.import_module(".ts_group", "pynapple.core")
        t = self.index
        d = self.values.astype("int")
        idx = np.unique(d)

        group = {}
        for k in idx:
            group[k] = Ts(t=t[d == k], time_support=self.time_support)

        return ts_group.TsGroup(group, time_support=self.time_support)

    def save(self, filename):
        """
        Save Tsd object in npz format. The file will contain the timestamps, the
        data and the time support.

        The main purpose of this function is to save small/medium sized time series
        objects. For example, you extracted one channel from your recording and
        filtered it. You can save the filtered channel as a npz to avoid
        reprocessing it.

        You can load the object with numpy.load. Keys are 't', 'd', 'start', 'end' and 'type'.
        See the example below.

        Parameters
        ----------
        filename : str
            The filename

        Examples
        --------
        >>> import pynapple as nap
        >>> import numpy as np
        >>> tsd = nap.Tsd(t=np.array([0., 1.]), d = np.array([2, 3]))
        >>> tsd.save("my_path/my_tsd.npz")

        Here I can retrieve my data with numpy directly:

        >>> file = np.load("my_path/my_tsd.npz")
        >>> print(list(file.keys()))
        ['t', 'd', 'start', 'end', 'type']
        >>> print(file['t'])
        [0. 1.]

        It is then easy to recreate the Tsd object.
        >>> time_support = nap.IntervalSet(file['start'], file['end'])
        >>> nap.Tsd(t=file['t'], d=file['d'], time_support=time_support)
        Time (s)
        0.0    2
        1.0    3
        dtype: int64

        Raises
        ------
        RuntimeError
            If filename is not str, path does not exist or filename is a directory.
        """
        if not isinstance(filename, str):
            raise RuntimeError("Invalid type; please provide filename as string")

        if os.path.isdir(filename):
            raise RuntimeError(
                "Invalid filename input. {} is directory.".format(filename)
            )

        if not filename.lower().endswith(".npz"):
            filename = filename + ".npz"

        dirname = os.path.dirname(filename)

        if len(dirname) and not os.path.exists(dirname):
            raise RuntimeError(
                "Path {} does not exist.".format(os.path.dirname(filename))
            )

        np.savez(
            filename,
            t=self.index,
            d=self.values,
            start=self.time_support.start.values,
            end=self.time_support.end.values,
            type=np.array(["Tsd"], dtype=np.str_),
        )

        return

    def interpolate(self, ts, ep=None, left=None, right=None):
        """Wrapper of the numpy linear interpolation method. See https://numpy.org/doc/stable/reference/generated/numpy.interp.html for an explanation of the parameters.
        The argument ts should be Ts, Tsd, TsdFrame to ensure interpolating from sorted timestamps in the right unit,

        Parameters
        ----------
        ts : Ts, Tsd or TsdFrame
            The object holding the timestamps
        ep : IntervalSet, optional
            The epochs to use to interpolate. If None, the time support of Tsd is used.
        left : None, optional
            Value to return for ts < tsd[0], default is tsd[0].
        right : None, optional
            Value to return for ts > tsd[-1], default is tsd[-1].
        """
        if not isinstance(ts, (Ts, Tsd, TsdFrame)):
            raise RuntimeError(
                "First argument should be an instance of Ts, Tsd or TsdFrame"
            )

        if not isinstance(ep, IntervalSet):
            ep = self.time_support

        new_t = ts.restrict(ep).index.values
        new_d = np.empty(len(new_t))
        new_d.fill(np.nan)

        start = 0
        for i in range(len(ep)):
            t = ts.restrict(ep.loc[[i]])
            tmp = self.restrict(ep.loc[[i]])
            if len(t) and len(tmp):
                new_d[start : start + len(t)] = np.interp(
                    t.index.values, tmp.index.values, tmp.values, left=left, right=right
                )
            start += len(t)

        return Tsd(t=new_t, d=new_d, time_support=ep)

    # def find_gaps(self, min_gap, method="absolute"):
    #     """
    #     finds gaps in a tsd larger than min_gap

    #     Parameters
    #     ----------
    #     min_gap : TYPE
    #         Description
    #     method : str, optional
    #         Description
    #     """
    #     print("TODO")
    #     return

    # def find_support(self, min_gap, method="absolute"):
    #     """
    #     find the smallest (to a min_gap resolution) IntervalSet containing all the times in the Tsd

    #     Parameters
    #     ----------
    #     min_gap : TYPE
    #         Description
    #     method : str, optional
    #         Description

    #     Returns
    #     -------
    #     TYPE
    #         Description
    #     """
    #     print("TODO")
    #     return

    def start_time(self, units="s"):
        """
        The first time index in the Ts/Tsd object

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.float64
            _
        """
        return self.times(units=units)[0]

    def end_time(self, units="s"):
        """
        The last time index in the Ts/Tsd object

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.float64
            _
        """
        return self.times(units=units)[-1]


class TsdFrame(NDArrayOperatorsMixin):
    """
    A subclass of pandas.DataFrame specialized for neurophysiological time series.

    TsdFrame provides standardized time representation, plus various functions for manipulating times series with identical sampling frequency.

    Attributes
    ----------
    rate : float
        Frequency of the time series (Hz) computed over the time support
    time_support : IntervalSet
        The time support of the time series
    """

    def __init__(self, t, d=None, time_units="s", time_support=None, **kwargs):
        """
        TsdFrame initializer

        Parameters
        ----------
        t : numpy.ndarray or pandas.DataFrame
            the time index t,  or a pandas.DataFrame (if d is None)
        d : numpy.ndarray
            The data
        time_units : str, optional
            The time units in which times are specified ('us', 'ms', 's' [default]).
        time_support : IntervalSet, optional
            The time support of the TsdFrame object
        **kwargs
            Arguments that will be passed to the pandas.DataFrame initializer.
        """
        if isinstance(t, np.ndarray) and d is None:
            raise RuntimeError("Missing argument d when initializing TsdFrame")

        if isinstance(t, pd.DataFrame):
            d = t.values
            c = t.columns.values
            t = t.index.values
        else:
            if not isinstance(d, np.ndarray):
                d = np.asarray(d)
            if len(d.shape) == 1:
                d = d[:, None]
            if "columns" in kwargs:
                c = kwargs["columns"]
            else:
                if isinstance(d, np.ndarray):
                    if len(d.shape) == 2:
                        c = np.arange(d.shape[1], dtype="int")
                    elif len(d.shape) == 1:
                        c = np.zeros(1, dtype="int")
                    else:
                        c = np.array([])
                else:
                    c = None

        if isinstance(t, Number):
            t = np.array([t])
        if isinstance(d, Number):
            d = np.array([d])

        t = t.astype(np.float64).flatten()
        t = format_timestamps(t, time_units)
        t = sort_timestamps(t)

        if len(t):
            if time_support is not None:
                starts = time_support.start.values
                ends = time_support.end.values
                if d is not None:
                    t, d = jitrestrict(t, d, starts, ends)
                    self.index = t
                    self.values = d
                else:
                    t = jittsrestrict(t, starts, ends)
                    self.index = t
                    self.values = np.array([])
            else:
                time_support = IntervalSet(start=t[0], end=t[-1])
                self.index = t
                self.values = d

            self.time_support = time_support
            self.rate = t.shape[0] / np.sum(
                time_support.values[:, 1] - time_support.values[:, 0]
            )

        else:
            time_support = IntervalSet(pd.DataFrame(columns=["start", "end"]))
            self.index = np.array([])
            self.values = np.array([])
            self.time_support = time_support
            self.rate = 0.0

        self.columns = c
        self.nap_class = self.__class__.__name__
        self.dtype = self.values.dtype

    @property
    def t(self):
        return self.index

    @property
    def start(self):
        return self.start_time()

    @property
    def end(self):
        return self.end_time()

    def __repr__(self):
        # TODO repr for all dtypes
        columns_str = ""
        if self.columns is not None and len(self.columns):
            columns_str += "        ".join([str(k) for k in self.columns])
        upper = "Time (s)      " + columns_str
        _str_ = []
        for i, array in zip(self.index, self.values):
            _str_.append(
                "{:.6f}".format(i)
                + "    "
                + " ".join(["{:.6f}".format(k) for k in array])
            )

        _str_ = "\n".join(_str_)
        bottom = "dtype: {}".format(self.dtype)
        return "\n".join((upper, _str_, bottom))

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, key):
        """
        Performs the operation __getitem__.
        """
        print(key)
        try:
            output = self.values.__getitem__(key)
            if isinstance(key, tuple):
                index = self.index.__getitem__(key[0])
            else:
                index = self.index.__getitem__(key)

            if all(isinstance(a, np.ndarray) for a in [index, output]):
                if output.shape[0] == index.shape[0]:
                    if len(output.shape) == 1:
                        return Tsd(t=index, d=output)
                    elif len(output.shape) == 2:
                        return TsdFrame(t=index, d=output)
                    else:
                        return output
            elif isinstance(index, Number):
                return TsdFrame(t=np.array([index]), d=np.atleast_2d(output))
            else:
                return output
        except:
            raise IndexError

    def __setitem__(self, key, value):
        """
        Performs the operation __getitem__.
        """
        try:
            self.values.__setitem__(key, value)
        except:
            raise IndexError

    def __len__(self):
        return len(self.index)

    def __array__(self, dtype=None):
        return self.values.astype(dtype)

    def __array_ufunc__(self, ufunc, method, *args, **kwargs):
        # print("In __array_ufunc__")
        # print("     ufunc = ", ufunc)
        # print("     method = ", method)
        # print("     args = ", args)
        # for inp in args: print(type(inp))
        # print("     kwargs = ", kwargs)

        if method == "__call__":
            new_args = []
            for a in args:
                if isinstance(a, Number):
                    new_args.append(a)
                elif isinstance(a, self.__class__):
                    new_args.append(a.values)
                else:
                    return NotImplemented

            out = ufunc(*new_args, **kwargs)
            # print("output = ", out)
            return self.__class__(self.index, out)

        else:
            return NotImplemented

    def __array_function__(self, func, types, args, kwargs):
        # print("In __array_function__")
        # print("     func = ", func)
        # print("     types = ", types)
        # print("     args = ", args)
        # print("     kwargs = ", kwargs)

        new_args = []
        for a in args:
            if isinstance(a, Tsd):
                new_args.append(a.values)
            else:
                new_args.append(a)

        output = func._implementation(*new_args, **kwargs)

        if isinstance(output, np.ndarray):
            if output.shape[0] == self.index.shape[0]:
                if len(output.shape) == 1:
                    return Tsd(t=self.index, d=output)
                elif len(output.shape) == 2:
                    return TsdFrame(t=self.index, d=output)
                else:
                    return output
            else:
                return output
        else:
            return output

    def get(self):
        """
        Get columns for TsdFrame. Similar to pandas df.get

        Returns
        -------
        out: Tsd or TsdFrame
            _
        """

        print("TODO")

    def as_dataframe(self):
        """
        Convert the TsdFrame object to a pandas.DataFrame object.

        Returns
        -------
        out: pandas.DataFrame
            _
        """
        return pd.DataFrame(index=self.index, data=self.values)

    def as_array(self):
        return self.values

    def times(self, units="s"):
        """
        The time index of the TsdFrame, returned as np.double in the desired time units.

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.ndarray
            _
        """
        return return_timestamps(self.index, units)

    def as_units(self, units="s"):
        """
        Returns a DataFrame with time expressed in the desired unit.

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        pandas.DataFrame
            the series object with adjusted times
        """
        t = self.index.copy()
        t = return_timestamps(t, units)
        if units == "us":
            t = t.astype(np.int64)

        df = pd.DataFrame(index=t, data=self.values)
        df.index.name = "Time (" + str(units) + ")"
        df.columns = self.columns.copy()
        return df

    def data(self):
        """
        The data in the TsdFrame object

        Returns
        -------
        out: numpy.ndarray
            _
        """
        return self.values

    def value_from(self, data, ep=None):
        """
        Replace the value with the closest value from Tsd/TsdFrame argument
        If data is TsdFrame, the output is also TsdFrame.

        Parameters
        ----------
        data : Tsd/TsdFrame
            The Tsd/TsdFrame object holding the values to replace.
        ep : IntervalSet (optional)
            The IntervalSet object to restrict the operation.
            If None, the time support of the tsd input object is used.

        Returns
        -------
        out : Tsd/TsdFrame
            Object with the new values

        Examples
        --------
        In this example, the ts object will receive the closest values in time from tsd.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100))) # random times
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> tsd = nap.Tsd(t=np.arange(0,1000), d=np.random.rand(1000), time_units='s')
        >>> ep = nap.IntervalSet(start = 0, end = 500, time_units = 's')

        The variable ts is a time series object containing only nan.
        The tsd object containing the values, for example the tracking data, and the epoch to restrict the operation.

        >>> newts = ts.value_from(tsd, ep)

        newts is the same size as ts restrict to ep.

        >>> print(len(ts.restrict(ep)), len(newts))
            52 52
        """
        if isinstance(data, Tsd):
            if ep is None:
                ep = data.time_support
            time_array = self.index
            time_target_array = data.index
            data_target_array = data.values
            starts = ep.start.values
            ends = ep.end.values
            t, d, ns, ne = jitvaluefrom(
                time_array, time_target_array, data_target_array, starts, ends
            )
            time_support = IntervalSet(start=ns, end=ne)

            return Tsd(t=t, d=d, time_support=time_support)

        elif isinstance(data, TsdFrame):
            if ep is None:
                ep = data.time_support
            time_array = self.index
            time_target_array = data.index
            data_target_array = data.values
            starts = ep.start.values
            ends = ep.end.values
            t, d, ns, ne = jitvaluefromtsdframe(
                time_array, time_target_array, data_target_array, starts, ends
            )
            time_support = IntervalSet(start=ns, end=ne)

            return TsdFrame(t=t, d=d, time_support=time_support, columns=data.columns)
        else:
            raise RuntimeError("The time series to align to should be Tsd/TsdFrame.")

    def restrict(self, iset):
        """
        Restricts a TsdFrame object to a set of time intervals delimited by an IntervalSet object`

        Parameters
        ----------
        iset : IntervalSet
            the IntervalSet object

        Returns
        -------
        TsdFrame
            TsdFrame object restricted to ep

        """
        c = self.columns
        time_array = self.index
        data_array = self.values
        starts = iset.start.values
        ends = iset.end.values
        t, d = jitrestrict(time_array, data_array, starts, ends)
        return TsdFrame(t=t, d=d, columns=c, time_support=iset)

    def bin_average(self, bin_size, ep=None, time_units="s"):
        """
        Bin the data by averaging points within bin_size
        bin_size should be seconds unless specified.
        If no epochs is passed, the data will be binned based on the time support.

        Parameters
        ----------
        bin_size : float
            The bin size (default is second)
        ep : None or IntervalSet, optional
            IntervalSet to restrict the operation
        time_units : str, optional
            Time units of bin size ('us', 'ms', 's' [default])

        Returns
        -------
        out: TsdFrame
            A TsdFrame object indexed by the center of the bins and holding the averaged data points.

        Examples
        --------
        This example shows how to bin data within bins of 0.1 second.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> tsdframe = nap.TsdFrame(t=np.arange(100), d=np.random.rand(100, 3))
        >>> bintsdframe = tsdframe.bin_average(0.1)

        An epoch can be specified:

        >>> ep = nap.IntervalSet(start = 10, end = 80, time_units = 's')
        >>> bintsdframe = tsdframe.bin_average(0.1, ep=ep)

        And bintsdframe automatically inherit ep as time support:

        >>> bintsdframe.time_support
        >>>    start    end
        >>> 0  10.0     80.0
        """
        if not isinstance(ep, IntervalSet):
            ep = self.time_support

        bin_size = format_timestamps(np.array([bin_size]), time_units)[0]

        time_array = self.index
        data_array = self.values
        starts = ep.start.values
        ends = ep.end.values
        t, d = jitbin_array(time_array, data_array, starts, ends, bin_size)
        time_support = IntervalSet(start=starts, end=ends)
        return TsdFrame(t=t, d=d, time_support=time_support)

    def save(self, filename):
        """
        Save TsdFrame object in npz format. The file will contain the timestamps, the
        data and the time support.

        The main purpose of this function is to save small/medium sized time series
        objects. For example, you extracted several channels from your recording and
        filtered them. You can save the filtered channels as a npz to avoid
        reprocessing it.

        You can load the object with numpy.load. Keys are 't', 'd', 'start', 'end', 'type'
        and 'columns' for columns names.

        Parameters
        ----------
        filename : str
            The filename

        Examples
        --------
        >>> import pynapple as nap
        >>> import numpy as np
        >>> tsdframe = nap.TsdFrame(t=np.array([0., 1.]), d = np.array([[2, 3],[4,5]]), columns=['a', 'b'])
        >>> tsdframe.save("my_path/my_tsdframe.npz")

        Here I can retrieve my data with numpy directly:

        >>> file = np.load("my_path/my_tsdframe.npz")
        >>> print(list(file.keys()))
        ['t', 'd', 'start', 'end', 'columns', 'type']
        >>> print(file['t'])
        [0. 1.]

        It is then easy to recreate the Tsd object.
        >>> time_support = nap.IntervalSet(file['start'], file['end'])
        >>> nap.TsdFrame(t=file['t'], d=file['d'], time_support=time_support, columns=file['columns'])
                  a  b
        Time (s)
        0.0       2  3
        1.0       4  5


        Raises
        ------
        RuntimeError
            If filename is not str, path does not exist or filename is a directory.
        """
        if not isinstance(filename, str):
            raise RuntimeError("Invalid type; please provide filename as string")

        if os.path.isdir(filename):
            raise RuntimeError(
                "Invalid filename input. {} is directory.".format(filename)
            )

        if not filename.lower().endswith(".npz"):
            filename = filename + ".npz"

        dirname = os.path.dirname(filename)

        if len(dirname) and not os.path.exists(dirname):
            raise RuntimeError(
                "Path {} does not exist.".format(os.path.dirname(filename))
            )

        cols_name = self.columns
        if cols_name.dtype == np.dtype("O"):
            cols_name = cols_name.astype(str)

        np.savez(
            filename,
            t=self.index,
            d=self.values,
            start=self.time_support.start.values,
            end=self.time_support.end.values,
            columns=cols_name,
            type=np.array(["TsdFrame"], dtype=np.str_),
        )

        return

    # def find_gaps(self, min_gap, time_units='s'):
    #     """
    #     finds gaps in a tsd larger than min_gap. Return an IntervalSet.
    #     Epochs are defined by adding and removing 1 microsecond to the time index.

    #     Parameters
    #     ----------
    #     min_gap : float
    #         The minimum interval size considered to be a gap (default is second).
    #     time_units : str, optional
    #         Time units of min_gap ('us', 'ms', 's' [default])
    #     """
    #     min_gap = format_timestamps(np.array([min_gap]), time_units)[0]

    #     time_array = self.index
    #     starts = self.time_support.start.values
    #     ends = self.time_support.end.values

    #     s, e = jitfind_gaps(time_array, starts, ends, min_gap)

    #     return nap.IntervalSet(s, e)

    # def find_support(self, min_gap, method="absolute"):
    #     """
    #     find the smallest (to a min_gap resolution) IntervalSet containing all the times in the Tsd

    #     Parameters
    #     ----------
    #     min_gap : float
    #         Description
    #     method : str, optional
    #         Description

    #     Returns
    #     -------
    #     TYPE
    #         Description
    #     """
    #     print("TODO")
    #     return

    def start_time(self, units="s"):
        return self.times(units=units)[0]

    def end_time(self, units="s"):
        return self.times(units=units)[-1]


class Ts(Tsd):
    """
    A subclass of the Tsd object for a time series with only time index,
    By default, the values are set to nan.
    All the functions of a Tsd object are available in a Ts object.

    Attributes
    ----------
    rate : float
        Frequency of the time series (Hz) computed over the time support
    time_support : IntervalSet
        The time support of the time series
    """

    def __init__(self, t, time_units="s", time_support=None, **kwargs):
        """
        Ts Initializer

        Parameters
        ----------
        t : numpy.ndarray or pandas.Series
            An object transformable in a time series, or a pandas.Series equivalent (if d is None)
        time_units : str, optional
            The time units in which times are specified ('us', 'ms', 's' [default])
        time_support : IntervalSet, optional
            The time support of the Ts object
        **kwargs
            Arguments that will be passed to the pandas.Series initializer.
        """
        super().__init__(
            t,
            None,
            time_units=time_units,
            time_support=time_support,
            dtype=np.float64,
            **kwargs,
        )
        self.nap_class = self.__class__.__name__

    def __repr__(self):
        # TODO repr for all dtypes
        upper = "Time (s)"
        _str_ = "\n".join(["{:.6f}".format(i) for i in self.index])
        bottom = "Length: {}".format(len(self.index)) + ", dtype: {}".format(self.dtype)
        return "\n".join((upper, _str_, bottom))

    def __str__(self):
        return self.__repr__()

    def save(self, filename):
        """
        Save Ts object in npz format. The file will contain the timestamps and
        the time support.

        The main purpose of this function is to save small/medium sized timestamps
        object.

        You can load the object with numpy.load. Keys are 't', 'start' and 'end' and 'type'.
        See the example below.

        Parameters
        ----------
        filename : str
            The filename

        Examples
        --------
        >>> import pynapple as nap
        >>> import numpy as np
        >>> ts = nap.Ts(t=np.array([0., 1., 1.5]))
        >>> ts.save("my_path/my_ts.npz")

        Here I can retrieve my data with numpy directly:

        >>> file = np.load("my_path/my_ts.npz")
        >>> print(list(file.keys()))
        ['t', 'start', 'end', 'type']
        >>> print(file['t'])
        [0. 1. 1.5]

        It is then easy to recreate the Tsd object.
        >>> time_support = nap.IntervalSet(file['start'], file['end'])
        >>> nap.Ts(t=file['t'], time_support=time_support)
        Time (s)
        0.0
        1.0
        1.5


        Raises
        ------
        RuntimeError
            If filename is not str, path does not exist or filename is a directory.
        """
        if not isinstance(filename, str):
            raise RuntimeError("Invalid type; please provide filename as string")

        if os.path.isdir(filename):
            raise RuntimeError(
                "Invalid filename input. {} is directory.".format(filename)
            )

        if not filename.lower().endswith(".npz"):
            filename = filename + ".npz"

        dirname = os.path.dirname(filename)

        if len(dirname) and not os.path.exists(dirname):
            raise RuntimeError(
                "Path {} does not exist.".format(os.path.dirname(filename))
            )

        np.savez(
            filename,
            t=self.index,
            start=self.time_support.start.values,
            end=self.time_support.end.values,
            type=np.array(["Ts"], dtype=np.str_),
        )

        return
