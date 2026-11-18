# 曲DB 設計（ロリポップ MySQL）

2026-11-13 作成。音ゲー曲のマスタデータを [楽曲情報API（reiwa.f5.si）](https://reiwa.f5.si/api.html) のJSONから作る。

## データ元と利用条件
- 利用規約上、データの利用は問題なし（確認済み）。
- **ジャケット画像・ロゴ画像は SEGA の権利物なので注意**。そのためDBには画像キー（JSONの `img`）を入れていない。アプリの画像は YouTube のサムネイル等を使う想定。
- サイトの注意事項: 営利目的は不可（広告収入も営利扱い）／データの正確性は保証なし／仕様は予告なく変わる／過度なリクエストをしない（取り込みスクリプトは1回の実行で6ファイル、1秒間隔で取得するだけ）。

## 使うJSON（3機種）
| 機種 | 楽曲 | バージョン一覧 |
|---|---|---|
| CHUNITHM | `chunirec_all.json` | `chunithm_versions.json` |
| maimai でらっくす | `maimai_all.json` | `maimai_versions.json` |
| オンゲキ | `ongeki_all.json` | `ongeki_versions.json` |

3つとも「1曲1オブジェクト・共通に近い形式」で、毎日更新されている（maintained）もの。

### 使わないもの（除外理由）
- 古い・更新停止: `ongeki_const_all.json`（削除予定）、`ongeki_unprocessed_record.json`（中間生成物）、`chunithm_sun_plus` 〜 `chunithm_x_verse_x.json`（過去バージョン終了時点のコピー）
- 海外版のみ: `chunithm_international_songs.json`、`chunithm_intl_versions.json`、`chunithm_intl_official.json`
- 重複（同じ内容の別形式）: `*_record.json`（譜面単位に並べ替えただけ）、`*_official.json`（公式サイトのデータそのまま。`*_all` に統合済み）
- 権利表記: `chunithm_right.json`、`maimai_right.json`（今は不要。権利表記を画面に出す必要が出たら検討）
- BPM: 不要なので取り込まない

## テーブル構成
```
games ─┬─ game_versions
       └─ game_songs ──┬── charts
            │          
songs ──────┘  （songs 1 : N game_songs）
```

| テーブル | 中身 | 件数（2026-11-13 時点） |
|---|---|---|
| `games` | 機種（1=CHUNITHM, 2=オンゲキ, 3=maimai） | 3 |
| `game_versions` | 機種のバージョンと稼働開始日 | 62 |
| `songs` | **機種をまたいだ楽曲**。アプリの再生・プレイリストはこれを使う | 3,133 |
| `game_songs` | 機種ごとの収録曲（曲名表記・ジャンル・収録日・バージョン） | 4,336 |
| `charts` | 難易度ごとの譜面（レベル・譜面定数） | 17,704 |

列の詳細は `db/schema.sql` のコメントを参照。

### songs（機種横断の楽曲）
- 「千本桜」のように複数機種に収録されている曲を1行にまとめる。2機種以上に収録: 852曲、3機種すべて: 283曲。
- 同一曲の判定は「曲名 + アーティスト」を正規化して比較（全角/半角・大文字/小文字・空白を無視、アーティストの「作品名」部分を除去）。
- 表記ゆれで別の曲として登録されてしまう例がある（例: `NOMA` と `ノマ`、`feat.` の有無）。気づいたら `game_songs.song_id` を手で付け替えて統合する（再取り込みしても `song_id` は上書きされない）。
- アプリ用の列（取り込みでは触らない）
  - `youtube_video_id`: 再生するYouTube動画ID
  - `chorus_start_sec`: サビ開始位置（秒）。ショート再生の開始位置。計測方法は未定（company-review.md のTODO）

### game_songs（機種ごとの収録曲）
- `release_date`: その機種への収録日。新曲・最近の追加曲の抽出に使える。
- `version_id`: 収録日から推定した収録バージョン（収録日以前で最新のバージョン）。
- `is_available`: 最新の取り込みで元データに存在したか。元データから消えた（削除曲）ものは 0 になる。
- CHUNITHM の WORLD'S END は元データで「曲名【字】」の別エントリなので別行（`is_worlds_end = 1`）。`song_id` は元の曲と同じ songs 行につなぐ。
- オンゲキの LUNATIC は元データで同じIDの別エントリだが、1行にまとめて `charts` に LUN として入れる（`added_date` は LUNATIC の追加日）。

### charts（譜面）
- `chart_type`: maimai の STD（スタンダード）/ DX（でらっくす）。他機種は常に STD。
- `difficulty`: BAS / ADV / EXP / MAS が共通。ULT（ULTIMA）・WE（WORLD'S END）は CHUNITHM、LUN（LUNATIC）はオンゲキ、REMAS（Re:MASTER）は maimai。
- `level` は元データの値のまま。小数部があれば「+」の意味（CHUNITHM は .5、maimai は .6、オンゲキは .7 → 例: 13.5 = 13+）。WORLD'S END はレベル・定数が無いので NULL。

## 取り込み手順
1. 初回のみ: phpMyAdmin で `db/schema.sql` をインポート（テーブル作成）。
2. 取り込みSQLを作る:
   ```bash
   python3 db/import/generate_import_sql.py
   ```
   JSONを `db/import/raw/` に保存し、`db/import/import.sql` を出力する。保存済みJSONから作り直すだけなら `--offline` を付ける。
3. phpMyAdmin で `db/import/import.sql` をインポート。
   - 何度流しても重複しない（既存の行は上書き更新）。`songs` の既存行と `youtube_video_id` / `chorus_start_sec` は変更されない。
   - ファイルは約2MB。アップロード上限に引っかかる場合は zip に圧縮してインポートできる。
   - 実行中だけ作業用テーブル `import_*` を作り、最後に削除する。

ローカルの MySQL 8.4 で「スキーマ作成 → 取り込み2回」を実行し、件数が元データと一致すること・2回目で重複しないこと・アプリ用の列が消えないことを確認済み（2026-11-13）。ロリポップ側の MySQL のバージョンは未確認だが、5.7 / 8.0 どちらでも動く書き方にしている。

## 今後の検討
- 取り込みの自動化（ロリポップの cron + PHP で毎日取り込む等）。
- 表記ゆれの手動統合を再取り込み後も保つ仕組み（現状は `song_id` を上書きしないことで対応）。
- Android から使う API（PHP）の設計。
