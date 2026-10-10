"""株価・出来高だけで判定するシグナル (docs/signal_spec.md の S2〜S4)。

入力は J-Quants 日次CSV (1日1ファイル) を結合した DataFrame。
閾値は spec の【推測】値で、引数で変えられる。
"""
from pathlib import Path

import pandas as pd

COLS = ["Date", "Code", "AdjC", "AdjVo", "Va", "UL", "LL", "MktCap"]


def load_prices(src) -> pd.DataFrame:
    """ディレクトリ(*.csv)またはファイルのリストを日付順に結合する。"""
    if isinstance(src, (str, Path)) and Path(src).is_dir():
        src = sorted(Path(src).glob("*.csv"))
    frames = [pd.read_csv(f, usecols=COLS, dtype={"Code": str}) for f in src]
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values(["Code", "Date"]).reset_index(drop=True)


def _last_per_code(df: pd.DataFrame, g) -> pd.DataFrame:
    return df.assign(**g).groupby("Code", sort=False).tail(1).set_index("Code")


def buy_blocked(df, vol_short=20, vol_long=120, vol_ratio=2.0,
                high_window=60, high_ratio=0.95) -> pd.DataFrame:
    """S2: 最終日に買い見送りとなる銘柄を返す (列: reason)。

    - 出来高急増 (短期平均/長期平均 > vol_ratio) かつ 高値圏 (終値 >= 直近高値 x high_ratio)
    - ストップ高 (UL=1)
    履歴が vol_long 日に満たない銘柄は出来高条件を判定しない。
    """
    g = df.groupby("Code", sort=False)
    vs = g["AdjVo"].transform(lambda s: s.rolling(vol_short).mean())
    vl = g["AdjVo"].transform(lambda s: s.rolling(vol_long).mean())
    hi = g["AdjC"].transform(lambda s: s.rolling(high_window).max())
    last = _last_per_code(df, {"vs": vs, "vl": vl, "hi": hi})
    surge = (last.vs / last.vl > vol_ratio) & (last.AdjC >= last.hi * high_ratio)
    limit_up = last.UL == 1
    out = last.assign(reason=surge.map({True: "volume_surge_at_high"}).where(~limit_up, "limit_up"))
    return out.loc[out.reason.notna(), ["reason"]]


def shock_alert(df, codes=None, drop=-0.15, vol_mult=3.0, vol_window=20) -> pd.DataFrame:
    """S3: 最終日の個別急落。前日比が drop 以下かつ出来高が平均の vol_mult 倍以上、またはストップ安。

    codes を渡すと保有・ウォッチリストに絞る。割安さの再判定(BUY_ZONE)は財務データが要るため含まない。
    """
    if codes is not None:
        df = df[df.Code.isin(codes)]
    g = df.groupby("Code", sort=False)
    ret = g["AdjC"].pct_change()
    vavg = g["AdjVo"].transform(lambda s: s.shift(1).rolling(vol_window).mean())
    last = _last_per_code(df, {"ret": ret, "vavg": vavg})
    hit = ((last.ret <= drop) & (last.AdjVo >= last.vavg * vol_mult)) | (last.LL == 1)
    return last.loc[hit, ["ret"]]


def market_index(df) -> pd.DataFrame:
    """TOPIX代替: 前日時価総額で加重した全銘柄の日次騰落率と、全市場の売買代金。"""
    d = df.sort_values(["Code", "Date"]).copy()
    g = d.groupby("Code", sort=False)
    d["ret"] = g["AdjC"].pct_change()
    d["w"] = g["MktCap"].shift(1)
    d = d.dropna(subset=["ret", "w"])
    d = d[d.w > 0]
    idx = d.groupby("Date").apply(lambda x: (x.ret * x.w).sum() / x.w.sum(), include_groups=False)
    va = df.groupby("Date")["Va"].sum()
    return pd.DataFrame({"ret": idx, "Va": va}).dropna().sort_index()


def market_crash(df, days=5, drop=-0.10, va_window=60, va_mult=2.0) -> dict:
    """S4: 最終日時点の相場急落判定。売りシグナルではなく買い場アラート。"""
    m = market_index(df)
    if len(m) < days:
        return {"alert": False, "reason": "insufficient_history"}
    cum = (1 + m.ret.tail(days)).prod() - 1
    base = m.Va.shift(1).rolling(va_window, min_periods=1).mean().iloc[-1]
    va_ratio = m.Va.iloc[-1] / base if base == base and base > 0 else float("nan")
    return {"alert": bool(cum <= drop and va_ratio >= va_mult),
            "cum_return": float(cum), "va_ratio": float(va_ratio),
            "date": m.index[-1]}
