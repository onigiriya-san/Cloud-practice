# Cloud-practice
クラウド環境のお試し

## stock-assist
`stock-assist/index.html` をブラウザで開くだけで動く株売買支援画面の試作。
銘柄ごとにシグナル（買い/売り/様子見）と根拠ルール（5日・25日移動平均のクロス、RSI14）を表示し、
買い/売りボタンで売買記録を localStorage に保存する。価格はダミーデータで、実際の発注はしない。

### 実データのシグナルを表示する
`python3 stock-assist/build_data.py <J-Quants日次CSVのディレクトリ>` で `stock-assist/data.js` を再生成する
（`signals/price_signals.py` の買い見送り・個別急落・相場急落を使用）。
