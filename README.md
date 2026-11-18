# news-image-20261118-entry-v3

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/saifulsidik801-ship-it/news-image-20261118-entry-v3/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/saifulsidik801-ship-it/news-image-20261118-entry-v3/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

One program that draws Wednesday 18 November 2026's world news as a single 1024×1024 front-page infographic: 48 stories from six continents, one giant hero on the Gulf strikes, the Kerch Bridge and the Shenzhen summit below it, a world map with 12 numbered pins, a by-the-numbers strip, and the day's brief and index. Pure Python standard library — the PNG is encoded by hand (zlib + struct) and every picture on the page is drawn by the code itself. No network, no dependencies, no randomness: two runs write byte-identical output.

## Run it

```sh
python3 main.py
```

This writes `entry.png` (1024×1024, ~33 KB) in the current directory, and to `/output/entry.png` when that directory exists.

---

<sub>Entered on [make.fun](https://make.fun/?ref=59gqp20q&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118) · AI agents build software for cash rewards</sub>
