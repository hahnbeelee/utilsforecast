# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/preprocessing.ipynb.

# %% auto 0
__all__ = ['fill_gaps']

# %% ../nbs/preprocessing.ipynb 2
import warnings
from typing import Union

import numpy as np
import pandas as pd

# %% ../nbs/preprocessing.ipynb 4
def _determine_bound(bound, freq, times_by_id, agg) -> np.ndarray:
    if bound == "per_serie":
        out = times_by_id[agg].values
    else:
        # the following return a scalar
        if bound == "global":
            val = getattr(times_by_id[agg].values, agg)()
            if isinstance(freq, str):
                val = np.datetime64(val)
        else:
            if isinstance(freq, str):
                # this raises a nice error message if it isn't a valid datetime
                val = np.datetime64(bound)
            else:
                val = bound
        out = np.full(times_by_id.shape[0], val)
    if isinstance(freq, str):
        out = out.astype(f"datetime64[{freq}]")
    return out

# %% ../nbs/preprocessing.ipynb 5
def fill_gaps(
    df: pd.DataFrame,
    freq: Union[str, int],
    start: Union[str, int] = "per_serie",
    end: Union[str, int] = "global",
    id_col: str = "unique_id",
    time_col: str = "ds",
) -> pd.DataFrame:
    """Enforce start and end datetimes for dataframe.

    Parameters
    ----------
    df : pandas DataFrame
        Input data
    freq : str or int
        Series' frequency
    start : str
        Initial timestamp for the series.
            * 'per_serie' uses each serie's first timestamp
            * 'global' uses the first timestamp seen in the data
            * Can also be a specific timestamp or integer, e.g. '2000-01-01' or 2000
    end : str
        Initial timestamp for the series.
            * 'per_serie' uses each serie's last timestamp
            * 'global' uses the last timestamp seen in the data
            * Can also be a specific timestamp or integer, e.g. '2000-01-01' or 2000
    id_col : str (default='unique_id')
        Column that identifies each serie.
    time_col : str (default='ds')
        Column that identifies each timestamp.

    Returns
    -------
    filled_df : pandas DataFrame
        Dataframe with gaps filled.
    """
    if isinstance(freq, str):
        offset = pd.tseries.frequencies.to_offset(freq)
        if "min" in freq:
            # minutes are represented as 'm' in numpy
            freq = freq.replace("min", "m")
        elif "B" in freq:
            # business day
            if freq != "B":
                raise NotImplementedError("Multiple of a business day")
            freq = "D"
        if offset.n > 1:
            freq = freq.replace(str(offset.n), "")
        if not hasattr(offset, "delta"):
            # irregular freq, try using first letter of abbreviation
            # such as MS = 'Month Start' -> 'M', YS = 'Year Start' -> 'Y'
            freq = freq[0]
        delta: Union[np.timedelta64, int] = np.timedelta64(offset.n, freq)
    else:
        delta = freq
    times_by_id = df.groupby(id_col, observed=True)[time_col].agg(["min", "max"])
    starts = _determine_bound(start, freq, times_by_id, "min")
    ends = _determine_bound(end, freq, times_by_id, "max") + delta
    sizes = ((ends - starts) / delta).astype(np.int64)
    times = np.hstack(
        [np.arange(start, end, delta) for start, end in zip(starts, ends)]
    )
    uids = np.repeat(times_by_id.index, sizes)
    if isinstance(freq, str):
        if offset.base.name == "B":
            # data was generated daily, we need to keep only business days
            bdays = np.is_busday(times)
            uids = uids[bdays]
            times = times[bdays]
        times = pd.Index(times.astype("datetime64[ns]", copy=False))
        first_time = np.datetime64(df.iloc[0][time_col])
        was_truncated = first_time != first_time.astype(f"datetime64[{freq}]")
        if was_truncated:
            times += offset.base
    idx = pd.MultiIndex.from_arrays([uids, times], names=[id_col, time_col])
    res = df.set_index([id_col, time_col]).reindex(idx).reset_index()
    extra_cols = df.columns.drop([id_col, time_col]).tolist()
    if extra_cols:
        check_col = extra_cols[0]
        if res[check_col].count() < df[check_col].count():
            warnings.warn(
                "Some values were lost during filling, "
                "please make sure that all your times meet the specified frequency.\n"
                "For example if you have 'W-TUE' as your frequency, "
                "make sure that all your times are actually Tuesdays."
            )
    return res
