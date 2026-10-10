"""signals/price_signals.py の結果を stock-assist/data.js に書き出す。

使い方: python3 stock-assist/build_data.py <日次CSVのディレクトリ>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from signals.price_signals import (buy_blocked, load_prices, market_crash,  # noqa: E402
                                   market_index, shock_alert)

HIST = 60      # カードに載せる株価の日数
TOP_CAP = 10   # シグナルが無くても載せる時価総額上位の銘柄数


def main(src):
    df = load_prices(src)
    last_date = df.Date.max()
    last = df[df.Date == last_date].set_index("Code")
    # 最終日に取引の無い銘柄(上場廃止・売買停止)は、古い最終行から判定されるので除く
    blocked = buy_blocked(df)
    blocked = blocked[blocked.index.isin(last.index)]
    shocks = shock_alert(df)
    shocks = shocks[shocks.index.isin(last.index)]

    # 市場全体: 加重騰落率の累積と最終日の判定
    mkt = market_crash(df)
    idx = market_index(df).tail(HIST)
    index_line = ((1 + idx.ret).cumprod() * 100).round(2).tolist()

    codes = list(dict.fromkeys(
        list(shocks.index) + list(blocked.index)
        + list(last.MktCap.dropna().sort_values(ascending=False).index[:TOP_CAP])))
    stocks = []
    for c in codes:
        h = df[(df.Code == c) & df.AdjC.notna()].tail(HIST)
        row = last.loc[c]
        prev = h.AdjC.iloc[-2] if len(h) > 1 else None
        stocks.append({
            "code": c[:4],
            "price": None if row.AdjC != row.AdjC else float(row.AdjC),
            "chg": None if prev is None or row.AdjC != row.AdjC else float(row.AdjC / prev - 1),
            "mktcap": None if row.MktCap != row.MktCap else float(row.MktCap),  # 百万円(推定)
            "prices": h.AdjC.round(1).tolist(),
            "shock": c in shocks.index,
            "shock_ret": float(shocks.loc[c, "ret"]) if c in shocks.index else None,
            "blocked": blocked.loc[c, "reason"] if c in blocked.index else None,
        })

    data = {
        "asOf": last_date.strftime("%Y-%m-%d"),
        "days": int(df.Date.nunique()),
        "market": {"level": mkt["level"], "cum": mkt["cum_return"], "vaRatio": mkt["va_ratio"],
                   "line": index_line},
        "counts": {"blocked": len(blocked), "shock": len(shocks), "universe": int(last.shape[0])},
        "stocks": stocks,
    }
    out = Path(__file__).with_name("data.js")
    out.write_text("window.SIGNAL_DATA = " + json.dumps(data, ensure_ascii=False, allow_nan=False) + ";\n")
    print(out, len(stocks), "stocks", mkt["level"])


if __name__ == "__main__":
    main(sys.argv[1])
