import numpy as np
import scipy
import pandas as pd
import os
import pyhydrophone as pyhy
import pypam
import xarray as xr

from pypam._event import Event
import matplotlib.pyplot as plt

from tests import skip_unless_with_plots

test_dir = os.path.dirname(__file__)
pile_driving_dir = f"{test_dir}\\test_data\\impulsive_data"
plt.rcParams.update(plt.rcParamsDefault)

name = "AMAR 1"
model = "Geospectrum"
serial_number = 247
sensitivity = -166.6
preamp_gain = 0
Vpp = 2

AMAR = pyhy.amar.AmarG3(
    name, model, serial_number, sensitivity, preamp_gain, Vpp
)

wav_file = os.path.join(pile_driving_dir, "pileDriving_excerpt.wav")
acu_file = pypam.AcuFile(wav_file, AMAR, 1.0)


def load_benchmark_data():
    """load benchmark data, which was calculated in matlab independently, to a dataframe."""
    mat = scipy.io.loadmat(
        os.path.join(pile_driving_dir, "pileDriving_results_benchmark")
    )

    df_val = pd.DataFrame(
        {
            "startTime": [],
            "peak": [],
            "rms90": [],
            "sel": [],
            "tau": [],
            "kurtosis": [],
        }
    )
    for result in mat["BrdBnd_Results"]:
        # print(result)
        results = {
            "startTime": result[0],
            "peak": result[1],
            f"rms90": result[3]
            + 10
            * np.log10(
                0.9
            ),  # correct slight expected difference (non-ISO definition)
            f"sel": result[2],
            "tau": result[4],
            "kurtosis": 0,
        }
        df_val.loc[len(df_val)] = results

    return df_val


def simplePeaks(
    acu_file: pypam.AcuFile,
    threshold,
    eventSeparation_s,
    buffer_s,
    units="Pa",
):
    """very simple detection algorithm"""
    eventSeparation_samples = acu_file.fs * eventSeparation_s
    sig = acu_file.signal(units=units)
    peaks, properties = scipy.signal.find_peaks(
        sig, height=threshold, distance=eventSeparation_samples
    )

    # apply buffer
    peaks = peaks - int(buffer_s * acu_file.fs)

    return peaks


def get_events():
    event_separation_s = 1.0
    buffer_s = 0.2
    locations = simplePeaks(acu_file, 25, event_separation_s, buffer_s)

    events = []
    signal, fs = acu_file.signal(units="upa"), acu_file.fs
    for i in range(len(locations) - 1):
        events.append(
            Event(signal, fs, start=locations[i], end=locations[i + 1])
        )
    return events


def test_do_analysis():
    """perform analysis on pile driving data, save metrics"""
    events = get_events()

    results_df = pd.DataFrame(
        {
            "startTime": [],
            "peak": [],
            "rms90": [],
            "sel": [],
            "tau": [],
            "kurtosis": [],
        }
    )

    for event in events:

        results = event.analyze(impulsive=True)
        results_df.loc[len(results_df)] = results

    results_df.to_csv(
        os.path.join(pile_driving_dir, "pileDriving_results_pypam.csv")
    )
    assert isinstance(results_df, pd.DataFrame)


def test_verify_results():
    """compare results here with benchmark"""

    def calc_diff(df1, df2, key):
        max_diff = np.max(np.abs(df1[key].values - df2[key].values[0:39]))
        median_diff = np.abs(
            np.median(df1[key].values) - np.median(df2[key].values[0:39])
        )
        return max_diff, median_diff

    # accept 0.1, 0.5 dB median and maximum differences, respectively
    tol_median = 0.1
    tol_max = 0.5
    tol_pulse_width = 0.01  # s
    # read data calculated here and from matlab benchmark
    df = pd.read_csv(
        os.path.join(pile_driving_dir, "pileDriving_results_pypam.csv")
    )
    df_bm = load_benchmark_data()

    peak_diff = calc_diff(df, df_bm, "peak")
    rms_diff = calc_diff(df, df_bm, "rms90")
    sel_diff = calc_diff(df, df_bm, "sel")
    tau_diff = calc_diff(df, df_bm, "tau")

    assert peak_diff[0] < tol_max
    assert peak_diff[1] < tol_median
    assert rms_diff[0] < tol_max
    assert rms_diff[1] < tol_median
    assert sel_diff[0] < tol_max
    assert sel_diff[1] < tol_median
    assert tau_diff[1] < tol_pulse_width


def test_kurtosis_over_file():
    """test acu_file implementation of kurtosis (i.e. _apply_multiple)"""
    # calculate 0.1 s kurtosis
    ds = acu_file.kurtosis(binsize=0.1)
    ds.attrs["dc_subtract"] = str(ds.attrs["dc_subtract"])
    ds.to_netcdf(os.path.join(pile_driving_dir, "kurtosis_result.nc"))
    assert isinstance(ds, xr.Dataset)


@skip_unless_with_plots()
def test_plot_kurtosis():
    """plot results from above test"""
    ds = xr.load_dataset(os.path.join(pile_driving_dir, "kurtosis_result.nc"))
    fig, ax = plt.subplots()
    ax.plot(ds.datetime, ds.kurtosis)
    ax.set_ylabel(f"{ds.kurtosis.standard_name} ({ds.kurtosis.units})")
    fig.suptitle("test_plot_kurtosis in test_impulsive_metrics.py")
    plt.show()


@skip_unless_with_plots()
def test_plot_metrics():
    """
    plot pile driving metrics against benchmark, disagreement (~10%) in pulse width assumed to be detector
    related as energy_window testing confirms that methodology
    """
    df = pd.read_csv(
        os.path.join(pile_driving_dir, "pileDriving_results_pypam.csv")
    )
    df_bm = load_benchmark_data()

    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(10, 7))
    metrics = {
        "peak": "Peak SPL",
        "rms90": "SPL RMS 90",
        "sel": "SEL",
        "tau": "90% pulse width (s)",
    }
    for metric, ax in zip(metrics.keys(), axes):
        ax.plot(df_bm[metric], marker="o", linestyle="none", label="benchmark")
        ax.plot(df[metric], marker="o", linestyle="none", label="pypam")
        ax.set_ylabel(f"{metrics[metric]} (dB)")
        ax.legend()
    axes[3].set_xlabel("detection index")
    fig.suptitle("Comparison of pypam/external pile driving analysis")
    plt.show()


def sum_spec(L):
    """sum decidecade spectra to compute broadband level"""
    I = 0
    L = L[np.isfinite(L)]
    for l in L:
        I = I + 10 ** (l / 10)
    return 10 * np.log10(I)


@skip_unless_with_plots()
def test_decidecade_sel():
    """plot decidecade sel spectra and compare results against directly computed sel and a benchmark spectra
    calculated separately with an established/validated method"""
    # get reference spectra (Denes et al. 2016, Kake, AK)
    filename = "pile_driving_decidecade_benchmark.csv"
    raw_data = np.loadtxt(
        f"{test_dir}\\test_data\\impulsive_data\\{filename}", delimiter=","
    )
    fdec_benchmark, sel_benchmark = raw_data[:, 0], raw_data[:, 1]

    # get events and initiate figure
    events = get_events()
    fig, (ax_spectra, ax_bb) = plt.subplots(
        2, 1, figsize=(8, 8), height_ratios=[0.67, 0.33]
    )
    # broadband sel to be computed from decidecade spectra
    sel_bb = np.zeros(
        (
            len(
                events,
            )
        )
    )
    for i, event in enumerate(events):
        f, psd = scipy.signal.periodogram(event.signal, fs=event.fs)
        ax_spectra.semilogx(f, 10 * np.log10(psd))
        fdec, sel = event.decidecade_sel()
        ax_spectra.semilogx(fdec, sel, marker="o", linestyle="--")
        sel_bb[i] = sum_spec(sel)
    ax_spectra.set_xlim([5, 35e3])
    ax_spectra.set_ylim([0, 150])
    ax_spectra.set_xlabel("frequency (hz)")
    ax_spectra.set_ylabel("Energy Spectral Density, SEL")
    # plot benchmark
    ax_spectra.semilogx(
        fdec_benchmark,
        sel_benchmark,
        marker="d",
        linestyle="--",
        label="benchmark",
        markeredgecolor="w",
    )
    ax_spectra.legend()

    # get directly computed metrics and compare
    df = pd.read_csv(
        os.path.join(pile_driving_dir, "pileDriving_results_pypam.csv")
    )
    ax_bb.plot(
        df["sel"].values,
        marker="d",
        linestyle="none",
        label="directly computed",
    )
    ax_bb.plot(
        sel_bb, marker="o", linestyle="none", label="decidecade broadband"
    )
    ax_bb.set_ylabel("SEL (dB)")
    ax_bb.set_xlabel("event")
    ax_bb.legend()
    fig.suptitle("test_decidecade_sel in test_impulsive_metrics.py")
    plt.show()

    diff = np.abs(df["sel"] - sel_bb)
    assert np.max(diff) < 0.05  # accept max of 0.05 dB error
