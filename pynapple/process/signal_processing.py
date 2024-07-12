"""
Signal processing tools for Pynapple.

Contains functionality for signal processing pynapple object; fourier transforms and wavelet decomposition.
"""

from itertools import repeat
from math import ceil, floor

import numpy as np
import pandas as pd
from scipy.signal import welch

import pynapple as nap


def compute_spectogram(sig, fs=None, ep=None, full_range=False):
    """
    Performs numpy fft on sig, returns output

    ----------
    sig : pynapple.Tsd or pynapple.TsdFrame
        Time series.
    fs : float, optional
        Sampling rate, in Hz. If None, will be calculated from the given signal
    ep : pynapple.IntervalSet or None, optional
        The epoch to calculate the fft on. Must be length 1.
    full_range : bool, optional
        If true, will return full fft frequency range, otherwise will return only positive values
    """
    if not isinstance(sig, (nap.Tsd, nap.TsdFrame)):
        raise TypeError(
            "Currently compute_spectogram is only implemented for Tsd or TsdFrame"
        )
    if not (ep is None or isinstance(ep, nap.IntervalSet)):
        raise TypeError("ep param must be a pynapple IntervalSet object, or None")
    if ep is None:
        ep = sig.time_support
    if len(ep) != 1:
        raise ValueError("Given epoch (or signal time_support) must have length 1")
    if fs is None:
        fs = sig.index.shape[0] / (sig.index.max() - sig.index.min())
    fft_result = np.fft.fft(sig.restrict(ep).values, axis=0)
    fft_freq = np.fft.fftfreq(len(sig.restrict(ep).values), 1 / fs)
    ret = pd.DataFrame(fft_result, fft_freq)
    ret.sort_index(inplace=True)
    if not full_range:
        return ret.loc[ret.index >= 0]
    return ret

def compute_welch_spectogram(sig, fs=None):
    """
    Performs scipy Welch's decomposition on sig, returns output.
    Estimates the power spectral density of a signal by segmenting it into overlapping sections, applying a
    window function to each segment, computing their FFTs, and averaging the resulting periodograms to reduce noise.

    ..todo: remove this or add binsize parameter
    ..todo: be careful of border artifacts

    Parameters
    ----------
    sig : pynapple.Tsd or pynapple.TsdFrame
        Time series.
    fs : float, optional
        Sampling rate, in Hz. If None, will be calculated from the given signal
    """
    if not isinstance(sig, (nap.Tsd, nap.TsdFrame)):
        raise TypeError(
            "Currently compute_welch_spectogram is only implemented for Tsd or TsdFrame"
        )
    if fs is None:
        fs = sig.index.shape[0] / (sig.index.max() - sig.index.min())
    freqs, spectogram = welch(sig.values, fs=fs, axis=0)
    return pd.DataFrame(spectogram, freqs)


def _morlet(M=1024, ncycles=1.5, scaling=1.0, precision=8):
    """
    Defines the complex Morlet wavelet kernel

    Parameters
    ----------
    M : int
        Length of the wavelet
    ncycles : float
        number of wavelet cycles to use. Default is 1.5
    scaling: float
        Scaling factor. Default is 1.0
    precision: int
        Precision of wavelet to use

    Returns
    -------
    np.ndarray
        Morelet wavelet kernel
    """
    x = np.linspace(-precision, precision, M)
    return (
        ((np.pi * ncycles) ** (-0.25))
        * np.exp(-(x**2) / ncycles)
        * np.exp(1j * 2 * np.pi * scaling * x)
    )


def _check_n_cycles(n_cycles, len_cycles=None):
    """
    Check an input as a number of cycles, and make it iterable.

    Parameters
    ----------
    n_cycles : float or list
        Definition of number of cycles to check. If a single value, the same number of cycles is used for each
        frequency value. If a list or list_like, then should be a n_cycles corresponding to each frequency.
    len_cycles: int, optional
        What the length of `n_cycles` should be, if it's a list.

    Returns
    -------
    iter
        An iterable version of the number of cycles.
    """
    if isinstance(n_cycles, (int, float, np.number)):
        if n_cycles <= 0:
            raise ValueError("Number of cycles must be a positive number.")
        n_cycles = repeat(n_cycles)
    elif isinstance(n_cycles, (tuple, list, np.ndarray)):
        for cycle in n_cycles:
            if cycle <= 0:
                raise ValueError("Each number of cycles must be a positive number.")
        if len_cycles and len(n_cycles) != len_cycles:
            raise ValueError(
                "The length of number of cycles does not match other inputs."
            )
        n_cycles = iter(n_cycles)
    return n_cycles


def _create_freqs(freq_start, freq_stop, freq_step=1):
    """
    Creates an array of frequencies.

    ..todo:: Implement log scaling

    Parameters
    ----------
    freq_start : float
        Starting value for the frequency definition.
    freq_stop: float
        Stopping value for the frequency definition, inclusive.
    freq_step: float, optional
        Step value, for linearly spaced values between start and stop.

    Returns
    -------
    freqs: 1d array
        Frequency indices.
    """
    return np.arange(freq_start, freq_stop + freq_step, freq_step)


def compute_wavelet_transform(sig, freqs, fs=None, n_cycles=1.5, scaling=1.0, precision=10, norm=None):
    """
    Compute the time-frequency representation of a signal using morlet wavelets.

    Parameters
    ----------
    sig : pynapple.Tsd or pynapple.TsdFrame
        Time series.
    freqs : 1d array or list of float
        If array, frequency values to estimate with morlet wavelets.
        If list, define the frequency range, as [freq_start, freq_stop, freq_step].
        The `freq_step` is optional, and defaults to 1. Range is inclusive of `freq_stop` value.
    fs : float or None
        Sampling rate, in Hz. Defaults to sig.rate if None is given
    n_cycles : float or 1d array
        Length of the filter, as the number of cycles for each frequency.
        If 1d array, this defines n_cycles for each frequency.
    scaling : float
        Scaling factor.
    norm : {None, 'sss', 'amp'}, optional
        Normalization method:

        * None - no normalization
        * 'sss' - divide by the square root of the sum of squares
        * 'amp' - divide by the sum of amplitudes

    Returns
    -------
    mwt : 2d array
        Time frequency representation of the input signal.

    Notes
    -----
    This computes the continuous wavelet transform at specified frequencies across time.
    """
    if not isinstance(sig, (nap.Tsd, nap.TsdFrame, nap.TsdTensor)):
        raise TypeError("`sig` must be instance of Tsd, TsdFrame, or TsdTensor")
    if isinstance(freqs, (tuple, list)):
        freqs = _create_freqs(*freqs)
    if fs is None:
        fs = sig.rate
    # n_cycles = _check_n_cycles(n_cycles, len(freqs))
    if isinstance(sig, nap.Tsd):
        sig = sig.reshape((sig.shape[0], 1))
        output_shape = (sig.shape[0], len(freqs))
    else:
        output_shape = (sig.shape[0], len(freqs), *sig.shape[1:])
        sig = sig.reshape((sig.shape[0], np.prod(sig.shape[1:])))
    mwt = np.zeros(
        [sig.values.shape[0], len(freqs), sig.values.shape[1]], dtype=complex
    )

    filter_bank = _generate_morelet_filterbank(freqs, fs, n_cycles, scaling, precision)
    #
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    plt.clf()
    for f in filter_bank:
        plt.plot(f)
    plt.show()
    conv = np.convolve(sig, filter_bank)

    for channel_i in range(sig.values.shape[1]):
        for ind, (freq, n_cycle) in enumerate(zip(freqs, n_cycles)):
            mwt[:, ind, channel_i] = _convolve_wavelet(
                sig[:, channel_i], fs, freq, n_cycle, scaling, precision=precision, norm=norm
            )
    if len(output_shape) == 2:
        return nap.TsdFrame(
            t=sig.index, d=mwt.reshape(output_shape), time_support=sig.time_support
        )
    return nap.TsdTensor(
        t=sig.index, d=mwt.reshape(output_shape), time_support=sig.time_support
    )

def _generate_morelet_filterbank(freqs, fs, n_cycles, scaling, precision):
    """
    Make docsting #..todo:
    
    :param freqs: 
    :param n_cycles: 
    :param scaling: 
    :param precision: 
    :return: 
    """
    filter_bank = []
    morlet_f = _morlet(int(2 ** precision), ncycles=n_cycles, scaling=scaling)
    x = np.linspace(-8, 8, int(2 ** precision))
    int_psi = np.conj(_integrate(morlet_f, x[1] - x[0]))
    for freq in freqs:
        scale = scaling / (freq / fs)
        j = np.arange(scale * (x[-1] - x[0]) + 1) / (scale * (x[1] - x[0]))
        j = j.astype(int)  # floor
        if j[-1] >= int_psi.size:
            j = np.extract(j < int_psi.size, j)
        int_psi_scale = int_psi[j][::-1]
        filter_bank.append(int_psi_scale)
    return filter_bank


def _convolve_wavelet(
    sig, fs, freq, n_cycles=1.5, scaling=1.0, precision=10, norm=None
):
    """
    Convolve a signal with a complex wavelet.

    Parameters
    ----------
    sig : pynapple.Tsd
        Time series to filter.
    fs : float
        Sampling rate, in Hz.
    freq : float
        Center frequency of bandpass filter.
    n_cycles : float, optional, default: 7
        Length of the filter, as the number of cycles of the oscillation with specified frequency.
    scaling : float, optional, default: 0.5
        Scaling factor for the morlet wavelet.
    precision: int, optional, defaul: 10
        Precision of wavelet - higher number will lead to higher resolution wavelet (i.e. a longer filter bank
        to be convolved with the signal)
    norm : {'sss', 'amp', None}, optional
        Normalization method:

        * 'sss' - divide by the square root of the sum of squares
        * 'amp' - divide by the sum of amplitudes
        * None - no normalization

    Returns
    -------
    array
        Complex-valued time series.

    Notes
    -----

    * The real part of the returned array is the filtered signal.
    * Taking np.abs() of output gives the analytic amplitude.
    * Taking np.angle() of output gives the analytic phase.
    """
    if norm not in ["sss", "amp", None]:
        raise ValueError("Given `norm` must be None, `sss` or `amp`")
    morlet_f = _morlet(int(2**precision), ncycles=n_cycles, scaling=scaling)
    x = np.linspace(-8, 8, int(2**precision))
    int_psi = np.conj(_integrate(morlet_f, x[1] - x[0]))

    scale = scaling / (freq / fs)
    j = np.arange(scale * (x[-1] - x[0]) + 1) / (scale * (x[1] - x[0]))
    j = j.astype(int)  # floor
    if j[-1] >= int_psi.size:
        j = np.extract(j < int_psi.size, j)
    int_psi_scale = int_psi[j][::-1]
    print(len(int_psi_scale))

    conv = np.convolve(sig, int_psi_scale)
    if norm  == "sss":
        coef = -np.sqrt(scale) * np.diff(conv, axis=-1)
    elif norm == "amp":
        coef = -scale * np.diff(conv, axis=-1)
    else:
        coef = np.diff(conv, axis=-1) #No normalization seems to be most effective... take others out? Why scale? ..todo

    # transform axis is always -1 due to the data reshape above
    d = (coef.shape[-1] - sig.shape[-1]) / 2.0
    if d > 0:
        coef = coef[..., floor(d) : -ceil(d)]
    elif d < 0:
        raise ValueError(f"Selected scale of {scale} too small.")
    return coef


def _integrate(arr, step):
    """
    Integrates an array with respect to some step param. Used for integrating complex wavelets.

    Parameters
    ----------
    arr : np.ndarray
        wave function to be integrated
    step : float
        Step size of vgiven wave function array

    Returns
    -------
    array
        Complex-valued integrated wavelet

    """
    integral = np.cumsum(arr)
    integral *= step
    return integral
